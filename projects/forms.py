
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Project


User = get_user_model()


# ============================================================
# PROJECT FORM
# ============================================================

class ProjectForm(forms.ModelForm):

    class Meta:
        model = Project

        fields = [
            "name",
            "description",
            "start_date",
            "deadline",
            "status",
            "client",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter project name",
                    "autocomplete": "off",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Describe the project...",
                    "rows": 5,
                }
            ),

            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "deadline": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "client": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        }

        labels = {
            "name": "Project Name",
            "description": "Description",
            "start_date": "Start Date",
            "deadline": "Deadline",
            "status": "Project Status",
            "client": "Assigned Client",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["name"].required = True

        self.fields["start_date"].input_formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
        ]

        self.fields["deadline"].input_formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
        ]

        self.fields["client"].required = False
        self.fields["client"].empty_label = (
            "No client assigned"
        )

        self.fields["client"].queryset = (
            User.objects.filter(
                is_active=True,
                profile__role="client",
                profile__is_approved=True,
            )
            .distinct()
            .order_by("username")
        )

    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get("start_date")
        deadline = cleaned_data.get("deadline")

        if (
            start_date
            and deadline
            and deadline < start_date
        ):
            self.add_error(
                "deadline",
                "Deadline cannot be earlier than the start date.",
            )

        return cleaned_data


# ============================================================
# PROJECT MEMBER FORM
# ============================================================

class ProjectMemberForm(forms.ModelForm):

    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-select",
                "size": 8,
            }
        ),
    )

    class Meta:
        model = Project
        fields = ["members"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Approved, active internal team members.
        member_filter = Q(
            is_active=True,
            profile__is_approved=True,
            profile__role__in=[
                "admin",
                "manager",
                "employee",
            ],
        )

        # Always include the project owner when active,
        # even if the owner is a superuser.
        if self.instance.pk:
            owner = self.instance.owner

            if owner.is_active:
                member_filter |= Q(pk=owner.pk)

        self.fields["members"].queryset = (
            User.objects.filter(member_filter)
            .distinct()
            .order_by("username")
        )

    def clean_members(self):
        members = self.cleaned_data["members"]

        if self.instance.pk:
            owner = self.instance.owner

            # Ensure the owner cannot be removed
            # from the project team.
            if owner.is_active:
                members = User.objects.filter(
                    Q(pk__in=members.values_list("pk", flat=True))
                    | Q(pk=owner.pk)
                ).distinct()

        return members
