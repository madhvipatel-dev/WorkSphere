
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from projects.models import Project
from .models import Task, TaskSubmission


User = get_user_model()


# ============================================================
# ROLE HELPERS
# ============================================================

def get_approved_role(user):
    """
    Return the approved WorkSphere role.
    Superusers are treated as Admins.
    """

    if (
        user is None
        or not user.is_authenticated
        or not user.is_active
    ):
        return None

    if user.is_superuser:
        return "admin"

    profile = getattr(user, "profile", None)

    if profile is None or not profile.is_approved:
        return None

    role = str(
        getattr(profile, "role", "")
    ).strip().lower()

    if role not in (
        "admin",
        "manager",
        "employee",
        "client",
    ):
        return None

    return role


# ============================================================
# PROJECTS AVAILABLE FOR TASK MANAGEMENT
# ============================================================

def get_task_manageable_projects(user):
    """
    Superuser:
        All projects.

    Approved Admin / Manager:
        Projects they own or have joined as team members.

    Employee / Client:
        No task-management permissions.
    """

    role = get_approved_role(user)

    if role not in ("admin", "manager"):
        return Project.objects.none()

    if user.is_superuser:
        return Project.objects.all()

    return Project.objects.filter(
        Q(owner=user) | Q(members=user)
    ).distinct()


# ============================================================
# TASK FORM
# ============================================================

class TaskForm(forms.ModelForm):

    class Meta:
        model = Task

        fields = [
            "title",
            "description",
            "project",
            "assigned_to",
            "priority",
            "status",
            "due_date",
        ]

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter task title",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Describe the task...",
                }
            ),

            "project": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "assigned_to": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "priority": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "due_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.user = user

        self.fields["project"].queryset = (
            Project.objects.none()
        )

        self.fields["assigned_to"].queryset = (
            User.objects.none()
        )

        self.fields["assigned_to"].required = False

        self.fields["due_date"].input_formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
        ]

        role = get_approved_role(user)

        if role not in ("admin", "manager"):
            return

        # Include owned and joined projects.
        allowed_projects = (
            get_task_manageable_projects(user)
        )

        self.fields["project"].queryset = (
            allowed_projects.order_by("name")
        )

        # Find selected project.
        if self.is_bound:
            project_id = self.data.get("project")
        else:
            project_id = getattr(
                self.instance,
                "project_id",
                None,
            )

        if not project_id:
            return

        selected_project = allowed_projects.filter(
            pk=project_id
        ).first()

        if selected_project is None:
            return

        # Only approved Employees who belong
        # to the selected project can receive tasks.
        employees = User.objects.filter(
            is_active=True,
            profile__role="employee",
            profile__is_approved=True,
            projects=selected_project,
        ).distinct()

        self.fields["assigned_to"].queryset = (
            employees.order_by("username")
        )

    def clean(self):
        cleaned_data = super().clean()

        project = cleaned_data.get("project")
        assigned_to = cleaned_data.get("assigned_to")

        if project is None or assigned_to is None:
            return cleaned_data

        if not project.members.filter(
            pk=assigned_to.pk
        ).exists():
            self.add_error(
                "assigned_to",
                "The assigned employee must be "
                "a member of the selected project.",
            )

        return cleaned_data


# ============================================================
# TASK SUBMISSION FORM
# ============================================================

class TaskSubmissionForm(forms.ModelForm):

    class Meta:
        model = TaskSubmission

        fields = [
            "comment",
            "attachment",
        ]

        widgets = {
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": (
                        "Describe the work you completed, "
                        "what you implemented, "
                        "and any important details..."
                    ),
                }
            ),

            "attachment": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                }
            ),
        }

        labels = {
            "comment": "Work Description",
            "attachment": "Attach Work File",
        }

        help_texts = {
            "comment": (
                "Explain what you completed for this task."
            ),

            "attachment": (
                "Optional. Attach supporting work files."
            ),
        }

    def clean_comment(self):
        comment = self.cleaned_data.get(
            "comment", ""
        ).strip()

        if not comment:
            raise forms.ValidationError(
                "Please describe the work you completed."
            )

        return comment
