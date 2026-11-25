from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import UserProfile
from .permissions import ROLE_PERMISSIONS


def has_permission(user, permission):
    """
    Check whether the logged-in user has a specific
    WorkSphere permission.
    """

    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    try:
        role = user.profile.role
    except UserProfile.DoesNotExist:
        return False

    return ROLE_PERMISSIONS.get(
        role,
        {}
    ).get(
        permission,
        False
    )


def permission_required(permission):
    """
    Protect a view using a WorkSphere permission.
    """

    def decorator(view_func):

        @wraps(view_func)
        @login_required
        def wrapped_view(request, *args, **kwargs):

            if not has_permission(
                request.user,
                permission,
            ):
                messages.error(
                    request,
                    "You do not have permission to access this section.",
                )

                return redirect("dashboard")

            return view_func(
                request,
                *args,
                **kwargs,
            )

        return wrapped_view

    return decorator