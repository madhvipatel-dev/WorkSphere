
from functools import wraps
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from projects.models import Project

from .forms import ProjectFileForm
from .models import ProjectFile


# ============================================================
# USER ROLES
# ============================================================

def get_user_role(user):
    """
    Return the user's approved WorkSphere role.

    Superusers are treated as Admins.
    Django is_staff alone does not grant Admin access.
    """

    if not user.is_authenticated or not user.is_active:
        return None

    if user.is_superuser:
        return "admin"

    profile = getattr(user, "profile", None)

    if profile is None or not profile.is_approved:
        return None

    role = str(profile.role).strip().lower()

    if role in ("admin", "manager", "employee", "client"):
        return role

    return None


# ============================================================
# FILE ACCESS DECORATOR
# ============================================================

def file_access_required(view_func):
    """
    Admin / Manager / Employee:
        Allowed according to existing file permissions.

    Client:
        Show Access Denied with a Back to
        Client Dashboard button.

    Other unauthorized accounts:
        HTTP 403 Forbidden.
    """

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):

        role = get_user_role(request.user)

        # Client access denied page
        if role == "client":
            return render(
                request,
                "accounts/client_access_denied.html",
                {
                    "module_name": "Files",
                },
                status=403,
            )

        # Other unauthorized accounts
        if role not in ("admin", "manager", "employee"):
            raise PermissionDenied(
                "You do not have permission "
                "to access internal project files."
            )

        return view_func(request, *args, **kwargs)

    return wrapper


# ============================================================
# PROJECT AND FILE ACCESS HELPERS
# ============================================================

def accessible_file_projects(user):
    """
    Projects whose internal files the user may access.

    Superuser:
        All projects.

    Admin / Manager / Employee:
        Owned projects or current project membership.

    Client:
        No internal file access.
    """

    role = get_user_role(user)

    if role not in ("admin", "manager", "employee"):
        return Project.objects.none()

    if user.is_superuser:
        return Project.objects.all()

    return (
        Project.objects.filter(
            Q(owner=user) | Q(members=user)
        )
        .distinct()
    )


def manageable_file_projects(user):
    """
    Projects in which the user may manage
    other people's files.

    Superuser:
        All projects.

    Approved Admin / Manager:
        Projects they own.

    Employee:
        No project-wide management privileges.
    """

    role = get_user_role(user)

    if role not in ("admin", "manager"):
        return Project.objects.none()

    if user.is_superuser:
        return Project.objects.all()

    return Project.objects.filter(owner=user)


def can_access_project_files(user, project):
    """
    Check whether the user currently has access
    to internal files in this project.
    """

    return accessible_file_projects(user).filter(
        pk=project.pk
    ).exists()


def can_manage_project_files(user, project):
    """
    Check project-wide file management permissions.
    """

    return manageable_file_projects(user).filter(
        pk=project.pk
    ).exists()


def can_upload_project_file(user, project):
    """
    Authorized internal users can upload files
    to projects they can access.
    """

    return can_access_project_files(user, project)


def can_edit_project_file(user, project_file):
    """
    Project owner / superuser:
        Can edit any project file.

    Employee or another authorized member:
        Can edit their own uploaded files,
        provided they still belong to the project.
    """

    if not can_access_project_files(
        user,
        project_file.project,
    ):
        return False

    if can_manage_project_files(
        user,
        project_file.project,
    ):
        return True

    return project_file.uploaded_by_id == user.pk


def can_delete_project_file(user, project_file):
    """
    Use the same ownership rules for deletion.
    """

    return can_edit_project_file(user, project_file)


def accessible_files(user):
    """
    Return only files belonging to projects
    the user can currently access.

    Upload history does not grant permanent access.
    """

    projects = accessible_file_projects(user)

    return (
        ProjectFile.objects.filter(
            project__in=projects
        )
        .select_related(
            "project",
            "uploaded_by",
        )
        .order_by("-uploaded_at", "-pk")
    )


def get_accessible_file_or_404(user, file_id):
    """
    Prevent unauthorized file metadata disclosure.

    Files outside the user's authorized projects
    return HTTP 404.
    """

    return get_object_or_404(
        accessible_files(user),
        pk=file_id,
    )


def get_file_permission_context(user, project_file):
    """
    Provide consistent permissions for templates.
    """

    return {
        "can_edit_file": can_edit_project_file(
            user,
            project_file,
        ),
        "can_delete_file": can_delete_project_file(
            user,
            project_file,
        ),
        "can_manage_project_files": (
            can_manage_project_files(
                user,
                project_file.project,
            )
        ),
        "user_role": get_user_role(user),
    }


# ============================================================
# FILE LIST
# ============================================================

@file_access_required
@require_GET
def file_list(request):
    """
    List files from projects the current user
    is authorized to access.
    """

    files = accessible_files(request.user)

    return render(
        request,
        "files/file_list.html",
        {
            "files": files,
            "user_role": get_user_role(request.user),
            "can_upload_file": True,
        },
    )


# ============================================================
# FILE UPLOAD
# ============================================================

@file_access_required
@require_http_methods(["GET", "POST"])
def file_upload(request):
    """
    Upload a file to an accessible project.

    The server verifies the selected project
    independently of form field restrictions.
    """

    if request.method == "POST":
        form = ProjectFileForm(
            request.user,
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            project_file = form.save(commit=False)

            if not can_upload_project_file(
                request.user,
                project_file.project,
            ):
                raise PermissionDenied(
                    "You cannot upload files "
                    "to this project."
                )

            project_file.uploaded_by = request.user

            project_file.full_clean()
            project_file.save()

            messages.success(
                request,
                f'File "{project_file.title}" '
                "was uploaded successfully.",
            )

            return redirect("file_list")

    else:
        form = ProjectFileForm(request.user)

    # Restrict selectable projects.
    if "project" in form.fields:
        form.fields["project"].queryset = (
            accessible_file_projects(request.user)
        )

    return render(
        request,
        "files/file_form.html",
        {
            "form": form,
            "page_title": "Upload File",
            "button_text": "Upload File",
            "user_role": get_user_role(request.user),
        },
    )


# ============================================================
# FILE DETAILS
# ============================================================

@file_access_required
@require_GET
def file_detail(request, file_id):
    """
    Display metadata for an accessible project file.
    """

    project_file = get_accessible_file_or_404(
        request.user,
        file_id,
    )

    context = {
        "project_file": project_file,
    }

    context.update(
        get_file_permission_context(
            request.user,
            project_file,
        )
    )

    return render(
        request,
        "files/file_detail.html",
        context,
    )


# ============================================================
# SECURE FILE DOWNLOAD
# ============================================================

@file_access_required
@require_GET
def file_download(request, file_id):
    """
    Download a project file after verifying
    the user's current project access.

    Important:
    This endpoint does not make MEDIA_URL secure.
    Internal files must not be publicly accessible
    through direct media URLs.
    """

    project_file = get_accessible_file_or_404(
        request.user,
        file_id,
    )

    if not project_file.file:
        raise Http404("File not found.")

    try:
        file_handle = project_file.file.open("rb")
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("File not found.")

    download_name = Path(
        project_file.file.name
    ).name

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=download_name,
    )


# ============================================================
# FILE EDIT
# ============================================================

@file_access_required
@require_http_methods(["GET", "POST"])
def file_edit(request, file_id):
    """
    Edit an existing project file.

    Editing does not permit moving a file
    to another project.

    Only the project owner, superuser,
    or authorized original uploader may edit.
    """

    project_file = get_accessible_file_or_404(
        request.user,
        file_id,
    )

    if not can_edit_project_file(
        request.user,
        project_file,
    ):
        raise PermissionDenied(
            "You do not have permission "
            "to edit this file."
        )

    original_project_id = project_file.project_id

    if request.method == "POST":
        form = ProjectFileForm(
            request.user,
            request.POST,
            request.FILES,
            instance=project_file,
        )

        # Lock project before validation.
        if "project" in form.fields:
            form.fields["project"].queryset = (
                Project.objects.filter(
                    pk=original_project_id
                )
            )
            form.fields["project"].disabled = True

        if form.is_valid():
            updated_file = form.save(commit=False)

            if updated_file.project_id != original_project_id:
                raise PermissionDenied(
                    "Moving files between projects "
                    "is not allowed."
                )

            updated_file.uploaded_by_id = (
                project_file.uploaded_by_id
            )

            updated_file.full_clean()
            updated_file.save()

            messages.success(
                request,
                f'File "{updated_file.title}" '
                "was updated successfully.",
            )

            return redirect(
                "file_detail",
                file_id=updated_file.pk,
            )

    else:
        form = ProjectFileForm(
            request.user,
            instance=project_file,
        )

        if "project" in form.fields:
            form.fields["project"].queryset = (
                Project.objects.filter(
                    pk=original_project_id
                )
            )
            form.fields["project"].disabled = True

    context = {
        "form": form,
        "project_file": project_file,
        "page_title": "Edit File",
        "button_text": "Save Changes",
    }

    context.update(
        get_file_permission_context(
            request.user,
            project_file,
        )
    )

    return render(
        request,
        "files/file_form.html",
        context,
    )


# ============================================================
# FILE DELETE
# ============================================================

@file_access_required
@require_http_methods(["GET", "POST"])
def file_delete(request, file_id):
    """
    Delete an accessible file record.

    The uploaded file is also removed from
    storage after the database transaction commits.
    """

    project_file = get_accessible_file_or_404(
        request.user,
        file_id,
    )

    if not can_delete_project_file(
        request.user,
        project_file,
    ):
        raise PermissionDenied(
            "You do not have permission "
            "to delete this file."
        )

    if request.method == "POST":
        file_title = project_file.title

        storage = project_file.file.storage
        stored_name = project_file.file.name

        with transaction.atomic():
            project_file.delete()

            if stored_name:
                transaction.on_commit(
                    lambda: storage.delete(stored_name)
                )

        messages.success(
            request,
            f'File "{file_title}" '
            "was deleted successfully.",
        )

        return redirect("file_list")

    context = {
        "project_file": project_file,
    }

    context.update(
        get_file_permission_context(
            request.user,
            project_file,
        )
    )

    return render(
        request,
        "files/file_confirm_delete.html",
        context,
    )
