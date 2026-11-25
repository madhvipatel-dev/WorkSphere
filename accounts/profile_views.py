
from django import forms
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.shortcuts import redirect, render

from .models import UserProfile


# ============================================================
# MY PROFILE
# ============================================================

@login_required
def my_profile(request):
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={"role": "employee"},
    )

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        job_title = request.POST.get("job_title", "").strip()

        if not email:
            messages.error(
                request,
                "Email address is required.",
            )
            return render(
                request,
                "accounts/my_profile.html",
                {"profile": profile},
            )

        if request.user.__class__.objects.filter(
            email__iexact=email
        ).exclude(
            pk=request.user.pk
        ).exists():
            messages.error(
                request,
                "Another account already uses this email address.",
            )
            return render(
                request,
                "accounts/my_profile.html",
                {"profile": profile},
            )

        with transaction.atomic():
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "email",
                ]
            )

            profile.phone = phone
            profile.job_title = job_title
            profile.save(
                update_fields=["phone", "job_title"]
            )

        messages.success(
            request,
            "Your profile was updated successfully.",
        )
        return redirect("my_profile")

    return render(
        request,
        "accounts/my_profile.html",
        {"profile": profile},
    )


# ============================================================
# ACCOUNT SETTINGS
# ============================================================

@login_required
def account_settings(request):
    """
    Allow an authenticated user to change their own password.

    The user must supply their current password.
    The current login session is preserved after a
    successful password change.
    """

    if request.method == "POST":
        password_form = PasswordChangeForm(
            user=request.user,
            data=request.POST,
        )

        if password_form.is_valid():
            updated_user = password_form.save()

            update_session_auth_hash(
                request,
                updated_user,
            )

            messages.success(
                request,
                "Your password was changed successfully.",
            )

            return redirect("account_settings")

    else:
        password_form = PasswordChangeForm(
            user=request.user,
        )

    for field in password_form.fields.values():
        field.widget.attrs.update({
            "class": "form-control",
            "autocomplete": (
                "current-password"
                if field is password_form.fields["old_password"]
                else "new-password"
            ),
        })

    return render(
        request,
        "accounts/account_settings.html",
        {
            "password_form": password_form,
        },
    )
