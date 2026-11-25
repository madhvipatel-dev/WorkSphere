
from django.urls import path

from . import profile_views, views


urlpatterns = [
    # Authentication
    path(
        "login/",
        views.login_view,
        name="login",
    ),
    path(
        "register/",
        views.register_view,
        name="register",
    ),
    path(
        "logout/",
        views.logout_view,
        name="logout",
    ),

    # My Profile
    path(
        "profile/",
        profile_views.my_profile,
        name="my_profile",
    ),

    # Account Settings
    path(
        "settings/",
        profile_views.account_settings,
        name="account_settings",
    ),

    # User Management
    path(
        "users/",
        views.user_management,
        name="user_management",
    ),
    path(
        "users/<int:user_id>/role/",
        views.update_user_role,
        name="update_user_role",
    ),

    # Employee Management
    path(
        "employees/",
        views.employee_management,
        name="employee_management",
    ),
    path(
        "employees/<int:user_id>/edit/",
        views.employee_edit,
        name="employee_edit",
    ),

    # Roles and Permissions
    path(
        "roles-permissions/",
        views.role_permissions,
        name="role_permissions",
    ),
]
