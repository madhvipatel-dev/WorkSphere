
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from projects.models import Project

from .models import (
    ALLOWED_FILE_EXTENSIONS,
    MAX_FILE_SIZE,
    ProjectFile,
)


# ============================================================
# USER ROLE HELPER
# ============================================================

def get_user_role(user):
    """
    Return the approved WorkSphere role.

    Superusers are administrators.
    Django is_staff alone does not grant access.
    """
    if not user.is_authenticated or not user.is_active:
        return None

    if user.is_superuser:
        return "admin"

    profile = getattr(user, "profile", None)

    if profile is None or not profile.is_approved:
        return None

    role = str(profile.role).strip().lower()

    if role in ("admin", "manager", "employee"):
        return role

    return None


# ============================================================
# ACCESSIBLE PROJECTS
# ============================================================

def get_uploadable_projects(user):
    """
    Return projects where this user may upload files.

    Superuser:
        All projects.

    Admin / Manager:
        Owned projects or current memberships.

    Employee:
        Current project memberships only.

    Client / unapproved:
        No projects.
    """
    role = get_user_role(user)

    if role is None:
        return Project.objects.none()

    if user.is_superuser:
        return Project.objects.all()

    if role in ("admin", "manager"):
        return (
            Project.objects.filter(
                Q(owner=user) | Q(members=user)
            )
            .distinct()
        )

    return Project.objects.filter(members=user)


# ============================================================
# PROJECT FILE FORM
# ============================================================

class ProjectFileForm(forms.ModelForm):

    class Meta:
        model = ProjectFile

        fields = [
            "project",
            "title",
            "description",
            "file",
        ]

        widgets = {
            "project": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter file title",
                    "maxlength": "200",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Describe this file...",
                    "rows": 4,
                }
            ),

            "file": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": ",".join(
                        f".{extension}"
                        for extension in ALLOWED_FILE_EXTENSIONS
                    ),
                }
            ),
        }

        labels = {
            "project": "Project",
            "title": "File Title",
            "description": "Description",
            "file": "Choose File",
        }

        help_texts = {
            "file": (
                "Maximum file size: 10 MB. "
                "Only supported document, image and "
                "archive formats are allowed."
            ),
        }

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.user = user

        self.is_editing = bool(
            self.instance and self.instance.pk
        )

        self.original_project_id = (
            self.instance.project_id
            if self.is_editing
            else None
        )

        # Always restrict the available projects.
        allowed_projects = get_uploadable_projects(user)

        if self.is_editing:
            # Project cannot change after file creation.
            self.fields["project"].queryset = (
                allowed_projects.filter(
                    pk=self.original_project_id
                )
            )

            self.fields["project"].disabled = True

            self.fields["project"].help_text = (
                "The project cannot be changed "
                "after the file is uploaded."
            )

            # Existing files can be edited without
            # uploading a replacement.
            self.fields["file"].required = False

        else:
            self.fields["project"].queryset = (
                allowed_projects.order_by("name")
            )

            self.fields["file"].required = True

        self.fields["project"].empty_label = (
            "Select a project"
        )

    # ========================================================
    # PROJECT VALIDATION
    # ========================================================

    def clean_project(self):
        """
        Validate project access on the server.

        Prevent forged project IDs and prevent
        moving existing files to other projects.
        """
        project = self.cleaned_data.get("project")

        if project is None:
            raise ValidationError(
                "Please select a valid project."
            )

        allowed_projects = get_uploadable_projects(
            self.user
        )

        if not allowed_projects.filter(
            pk=project.pk
        ).exists():
            raise ValidationError(
                "You do not have permission "
                "to upload files to this project."
            )

        if self.is_editing:
            if project.pk != self.original_project_id:
                raise ValidationError(
                    "You cannot move a file "
                    "to another project."
                )

        return project

    # ========================================================
    # FILE VALIDATION
    # ========================================================

    def clean_file(self):
        """
        Validate the uploaded file.

        The model also contains file validators,
        providing an additional validation layer.
        """
        uploaded_file = self.cleaned_data.get("file")

        if not uploaded_file:
            if self.is_editing and self.instance.file:
                return self.instance.file

            raise ValidationError(
                "Please select a file to upload."
            )

        # Validate size.
        if uploaded_file.size > MAX_FILE_SIZE:
            raise ValidationError(
                "File size cannot exceed 10 MB."
            )

        # Validate extension.
        filename = uploaded_file.name

        if "." not in filename:
            raise ValidationError(
                "The selected file must have "
                "a supported extension."
            )

        extension = filename.rsplit(".", 1)[-1].lower()

        if extension not in ALLOWED_FILE_EXTENSIONS:
            allowed = ", ".join(
                f".{item}"
                for item in ALLOWED_FILE_EXTENSIONS
            )

            raise ValidationError(
                "Unsupported file type. "
                f"Allowed extensions: {allowed}"
            )

        return uploaded_file

    # ========================================================
    # FORM-LEVEL VALIDATION
    # ========================================================

    def clean(self):
        cleaned_data = super().clean()

        if self.is_editing:
            project = cleaned_data.get("project")

            if (
                project is not None
                and project.pk != self.original_project_id
            ):
                self.add_error(
                    "project",
                    "The project cannot be changed.",
                )

        return cleaned_data
