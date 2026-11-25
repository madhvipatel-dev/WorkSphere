
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import permission_required
from .forms import LoginForm, RegisterForm
from .models import UserProfile
from .permissions import (
    PERMISSION_ICONS,
    PERMISSION_LABELS,
    ROLE_LABELS,
    ROLE_PERMISSIONS,
)

from ws_departments.models import Department


# =========================================================
# ROLE HELPERS
# =========================================================

def user_is_admin(user):
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    try:
        profile = user.profile
        return (
            user.is_active
            and profile.is_approved
            and profile.role == "admin"
        )
    except UserProfile.DoesNotExist:
        return False


def get_user_role(user):
    """Return the user's canonical WorkSphere role."""
    if user.is_superuser or user.is_staff:
        return "admin"

    try:
        role = user.profile.role
    except UserProfile.DoesNotExist:
        return "employee"

    valid_roles = {
        choice[0] for choice in UserProfile.ROLE_CHOICES
    }

    return role if role in valid_roles else "employee"


# =========================================================
# REGISTRATION
# =========================================================

def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            requested_role = form.cleaned_data["requested_role"]

            # Only Employee and Client can register publicly.
            if requested_role not in ("employee", "client"):
                form.add_error(
                    "requested_role",
                    "Invalid registration role."
                )
            else:
                with transaction.atomic():
                    user = form.save(commit=False)

                    # Employee accounts are activated immediately.
                    # Client accounts require admin approval.
                    user.is_active = (
                        requested_role == "employee"
                    )
                    user.save()

                    # update_or_create supports projects that
                    # automatically create profiles using signals.
                    UserProfile.objects.update_or_create(
                        user=user,
                        defaults={
                            "role": requested_role,
                            "requested_role": requested_role,
                            "is_approved": (
                                requested_role == "employee"
                            ),
                        },
                    )

                if requested_role == "employee":
                    login(request, user)

                    messages.success(
                        request,
                        "Your employee account was created "
                        "successfully."
                    )

                    return redirect("dashboard")

                messages.success(
                    request,
                    "Your client account request has been "
                    "submitted. Please wait for administrator "
                    "approval."
                )

                return redirect("login")

    else:
        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form},
    )


# =========================================================
# LOGIN
# =========================================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()

            if not user.is_active:
                messages.error(
                    request,
                    "Your account is inactive or awaiting "
                    "administrator approval."
                )

                return render(
                    request,
                    "accounts/login.html",
                    {"form": form},
                )

            actual_role = get_user_role(user)

            # Check selected role only when the login form
            # explicitly submits a role.
            selected_role = request.POST.get(
                "login_role", ""
            ).strip().lower()

            valid_roles = {
                choice[0] for choice in UserProfile.ROLE_CHOICES
            }

            if selected_role:
                if selected_role not in valid_roles:
                    form.add_error(
                        None,
                        "Invalid login role selected."
                    )

                    return render(
                        request,
                        "accounts/login.html",
                        {"form": form},
                    )

                if selected_role != actual_role:
                    form.add_error(
                        None,
                        "The selected role does not match "
                        "your account."
                    )

                    return render(
                        request,
                        "accounts/login.html",
                        {"form": form},
                    )

            profile, created = (
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "role": "employee",
                        "requested_role": "employee",
                        "is_approved": True,
                    },
                )
            )

            if not profile.is_approved:
                messages.error(
                    request,
                    "Your account is awaiting administrator "
                    "approval."
                )

                return render(
                    request,
                    "accounts/login.html",
                    {"form": form},
                )

            login(request, user)

            messages.success(
                request,
                f"Welcome back, {user.username}!"
            )

            return redirect("dashboard")

    else:
        form = LoginForm()

    return render(
        request,
        "accounts/login.html",
        {"form": form},
    )


# =========================================================
# LOGOUT
# =========================================================

@login_required
def logout_view(request):
    logout(request)

    messages.success(
        request,
        "You have been logged out successfully."
    )

    return redirect("login")


# =========================================================
# USER MANAGEMENT
# =========================================================

@permission_required("users")
def user_management(request):
    users = (
        User.objects
        .select_related(
            "profile",
            "profile__department"
        )
        .all()
        .order_by("username")
    )

    search_query = request.GET.get(
        "search", ""
    ).strip()

    role_filter = request.GET.get(
        "role", ""
    ).strip()

    status_filter = request.GET.get(
        "status", ""
    ).strip()

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(profile__department__name__icontains=search_query)
            | Q(profile__job_title__icontains=search_query)
        )

    valid_roles = {
        "admin",
        "manager",
        "employee",
        "client",
    }

    if role_filter in valid_roles:
        users = users.filter(
            profile__role=role_filter
        )

    if status_filter == "active":
        users = users.filter(is_active=True)

    elif status_filter == "inactive":
        users = users.filter(is_active=False)

    elif status_filter == "pending":
        users = users.filter(
            profile__is_approved=False
        )

    all_users = User.objects.all()

    context = {
        "users": users,
        "search_query": search_query,
        "role_filter": role_filter,
        "status_filter": status_filter,

        "total_users": all_users.count(),

        "active_users": all_users.filter(
            is_active=True
        ).count(),

        "inactive_users": all_users.filter(
            is_active=False
        ).count(),

        "admin_users": UserProfile.objects.filter(
            role="admin"
        ).count(),

        "manager_users": UserProfile.objects.filter(
            role="manager"
        ).count(),

        "employee_users": UserProfile.objects.filter(
            role="employee"
        ).count(),

        "client_users": UserProfile.objects.filter(
            role="client"
        ).count(),

        "pending_users": UserProfile.objects.filter(
            is_approved=False
        ).count(),
    }

    return render(
        request,
        "accounts/user_management.html",
        context,
    )


# =========================================================
# UPDATE USER ROLE / APPROVE ACCOUNT
# =========================================================

@permission_required("users")
@require_POST
def update_user_role(request, user_id):
    # Role assignment is restricted to administrators.
    if not user_is_admin(request.user):
        messages.error(
            request,
            "Only administrators can change user roles."
        )
        return redirect("user_management")

    user = get_object_or_404(
        User,
        id=user_id
    )

    if user == request.user:
        messages.error(
            request,
            "You cannot change your own administrator role."
        )
        return redirect("user_management")

    if user.is_superuser or user.is_staff:
        messages.error(
            request,
            "Staff and superuser accounts cannot "
            "be changed here."
        )
        return redirect("user_management")

    selected_role = request.POST.get(
        "role", ""
    ).strip().lower()

    valid_roles = {
        choice[0] for choice in UserProfile.ROLE_CHOICES
    }

    if selected_role not in valid_roles:
        messages.error(
            request,
            "Invalid role selected."
        )
        return redirect("user_management")

    with transaction.atomic():
        profile, created = (
            UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "role": "employee",
                    "requested_role": "employee",
                    "is_approved": False,
                },
            )
        )

        old_role = profile.get_role_display()

        profile.role = selected_role
        profile.requested_role = selected_role
        profile.is_approved = True

        profile.save(
            update_fields=[
                "role",
                "requested_role",
                "is_approved",
            ]
        )

        # Activate approved accounts.
        if not user.is_active:
            user.is_active = True
            user.save(
                update_fields=["is_active"]
            )

    messages.success(
        request,
        f"{user.username}'s role was changed from "
        f"{old_role} to {profile.get_role_display()}. "
        "The account is approved and active."
    )

    return redirect("user_management")


# =========================================================
# EMPLOYEE MANAGEMENT
# =========================================================

@permission_required("employees")
def employee_management(request):
    employees = (
        User.objects
        .filter(profile__role="employee")
        .select_related(
            "profile",
            "profile__department"
        )
        .order_by("username")
    )

    search_query = request.GET.get(
        "search", ""
    ).strip()

    department_filter = request.GET.get(
        "department", ""
    ).strip()

    status_filter = request.GET.get(
        "status", ""
    ).strip()

    if search_query:
        employees = employees.filter(
            Q(username__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(profile__job_title__icontains=search_query)
            | Q(profile__department__name__icontains=search_query)
        )

    if department_filter:
        employees = employees.filter(
            profile__department_id=department_filter
        )

    if status_filter == "active":
        employees = employees.filter(
            is_active=True
        )

    elif status_filter == "inactive":
        employees = employees.filter(
            is_active=False
        )

    departments = Department.objects.filter(
        is_active=True
    ).order_by("name")

    context = {
        "employees": employees,
        "departments": departments,
        "search_query": search_query,
        "department_filter": department_filter,
        "status_filter": status_filter,

        "total_employees": User.objects.filter(
            profile__role="employee"
        ).count(),

        "active_employees": User.objects.filter(
            profile__role="employee",
            is_active=True,
        ).count(),

        "inactive_employees": User.objects.filter(
            profile__role="employee",
            is_active=False,
        ).count(),

        "assigned_employees": UserProfile.objects.filter(
            role="employee",
            department__isnull=False,
        ).count(),
    }

    return render(
        request,
        "accounts/employee_management.html",
        context,
    )


# =========================================================
# EDIT EMPLOYEE
# =========================================================

@permission_required("employees")
def employee_edit(request, user_id):
    employee = get_object_or_404(
        User.objects.select_related(
            "profile",
            "profile__department",
        ),
        id=user_id,
        profile__role="employee",
    )

    profile, created = (
        UserProfile.objects.get_or_create(
            user=employee,
            defaults={
                "role": "employee",
                "requested_role": "employee",
                "is_approved": True,
            },
        )
    )

    departments = Department.objects.filter(
        is_active=True
    ).order_by("name")

    if request.method == "POST":
        first_name = request.POST.get(
            "first_name", ""
        ).strip()

        last_name = request.POST.get(
            "last_name", ""
        ).strip()

        email = request.POST.get(
            "email", ""
        ).strip()

        phone = request.POST.get(
            "phone", ""
        ).strip()

        job_title = request.POST.get(
            "job_title", ""
        ).strip()

        department_id = request.POST.get(
            "department"
        )

        is_active = (
            request.POST.get("is_active") == "on"
        )

        if not email:
            messages.error(
                request,
                "Email address is required."
            )

            return render(
                request,
                "accounts/employee_form.html",
                {
                    "employee": employee,
                    "profile": profile,
                    "departments": departments,
                },
            )

        if User.objects.filter(
            email__iexact=email
        ).exclude(
            id=employee.id
        ).exists():

            messages.error(
                request,
                "Another user already uses this email address."
            )

            return render(
                request,
                "accounts/employee_form.html",
                {
                    "employee": employee,
                    "profile": profile,
                    "departments": departments,
                },
            )

        department = None

        if department_id:
            department = get_object_or_404(
                Department,
                id=department_id,
                is_active=True,
            )

        employee.first_name = first_name
        employee.last_name = last_name
        employee.email = email
        employee.is_active = is_active
        employee.save()

        profile.role = "employee"
        profile.requested_role = "employee"
        profile.phone = phone
        profile.job_title = job_title
        profile.department = department
        profile.save()

        messages.success(
            request,
            f"{employee.username}'s employee profile "
            "was updated successfully."
        )

        return redirect("employee_management")

    return render(
        request,
        "accounts/employee_form.html",
        {
            "employee": employee,
            "profile": profile,
            "departments": departments,
        },
    )


# =========================================================
# ROLE PERMISSIONS
# =========================================================

@permission_required("departments")
def role_permissions(request):
    if not user_is_admin(request.user):
        messages.error(
            request,
            "You do not have permission to manage "
            "roles and permissions."
        )

        return redirect("dashboard")

    permissions = []

    for permission_key, label in PERMISSION_LABELS.items():
        permissions.append({
            "key": permission_key,
            "label": label,

            "icon": PERMISSION_ICONS.get(
                permission_key,
                "fa-solid fa-shield-halved",
            ),

            "admin": ROLE_PERMISSIONS.get(
                "admin", {}
            ).get(permission_key, False),

            "manager": ROLE_PERMISSIONS.get(
                "manager", {}
            ).get(permission_key, False),

            "employee": ROLE_PERMISSIONS.get(
                "employee", {}
            ).get(permission_key, False),

            "client": ROLE_PERMISSIONS.get(
                "client", {}
            ).get(permission_key, False),
        })

    role_summary = []

    for role_key, role_label in ROLE_LABELS.items():
        role_permissions_map = (
            ROLE_PERMISSIONS.get(role_key, {})
        )

        enabled_permissions = sum(
            1
            for value in role_permissions_map.values()
            if value
        )

        role_summary.append({
            "key": role_key,
            "label": role_label,
            "enabled_permissions": enabled_permissions,
            "total_permissions": len(
                role_permissions_map
            ),
        })

    return render(
        request,
        "accounts/role_permissions.html",
        {
            "permissions": permissions,
            "role_summary": role_summary,
        },
    )
