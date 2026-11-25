
from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):

    ROLE_CHOICES = [
        ("employee", "Employee"),
        ("client", "Client / Customer"),
    ]

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "auth-input",
                "placeholder": "Choose a username",
                "autocomplete": "username",
            }
        ),
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "auth-input",
                "placeholder": "Enter your email address",
                "autocomplete": "email",
            }
        ),
    )

    requested_role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        initial="employee",
        required=True,
        label="Register As",
        widget=forms.Select(
            attrs={
                "class": "auth-input",
            }
        ),
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "auth-input password-input",
                "placeholder": "Create a password",
                "autocomplete": "new-password",
            }
        ),
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "auth-input password-input",
                "placeholder": "Confirm your password",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "requested_role",
            "password1",
            "password2",
        ]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        return email

    def clean_requested_role(self):
        role = self.cleaned_data["requested_role"]

        if role not in ("employee", "client"):
            raise forms.ValidationError(
                "Invalid registration role."
            )

        return role


class LoginForm(AuthenticationForm):

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "auth-input",
                "placeholder": "Enter your username",
                "autocomplete": "username",
            }
        ),
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "auth-input password-input",
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
            }
        ),
    )
