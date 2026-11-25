
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from projects.models import Project
from .models import Meeting


User = get_user_model()


# ============================================================
# ROLE AND PERMISSION HELPERS
# ============================================================

def get_user_role(user):
    """
    Return the user's approved WorkSphere role.

    Superusers are WorkSphere Admins.
    Django staff status alone does not grant access.
    """

    if not user or not user.is_authenticated:
        return None

    if not user.is_active:
        return None

    if user.is_superuser:
        return "admin"

    profile = getattr(user, "profile", None)

    if not profile or not profile.is_approved:
        return None

    role = str(profile.role).strip().lower()

    if role in (
        "admin",
        "manager",
        "employee",
        "client",
    ):
        return role

    return None


def can_manage_meetings(user):
    """
    Only approved Admins and Managers
    can create or edit meetings.
    """

    return get_user_role(user) in (
        "admin",
        "manager",
    )


def get_manageable_projects(user):
    """
    Superuser:
        All projects.

    Admin / Manager:
        Projects they own.

    Employee / Client:
        No meeting-management access.
    """

    if not can_manage_meetings(user):
        return Project.objects.none()

    if user.is_superuser:
        return Project.objects.all().order_by(
            "name",
            "pk",
        )

    return Project.objects.filter(
        owner=user,
    ).order_by(
        "name",
        "pk",
    )


# ============================================================
# ELIGIBLE MEETING PARTICIPANTS
# ============================================================

def get_project_participants(project):
    """
    Return eligible meeting participants.

    Includes:
        - Project owner
        - Project team members
        - Client assigned to the project

    All participants must be active and approved,
    except superusers, who are treated as Admins.

    Unrelated clients cannot be invited.
    """

    if not project or not project.pk:
        return User.objects.none()

    member_ids = project.members.values_list(
        "pk",
        flat=True,
    )

    # Project owner and team members
    participant_filter = (
        Q(pk=project.owner_id)
        | Q(pk__in=member_ids)
    )

    # Include the project's assigned Client.
    # This assumes Project.client is a ForeignKey
    # to the Django User model.
    if project.client_id:
        participant_filter |= Q(
            pk=project.client_id
        )

    project_users = User.objects.filter(
        participant_filter
    )

    return (
        project_users
        .filter(is_active=True)
        .filter(
            Q(is_superuser=True)
            | Q(
                profile__is_approved=True,
                profile__role__in=[
                    "admin",
                    "manager",
                    "employee",
                    "client",
                ],
            )
        )
        .distinct()
        .order_by(
            "username",
            "pk",
        )
    )


# ============================================================
# MEETING FORM
# ============================================================

class MeetingForm(forms.ModelForm):

    class Meta:

        model = Meeting

        fields = [
            "title",
            "description",
            "project",
            "participants",
            "meeting_date",
            "start_time",
            "end_time",
            "meeting_link",
            "location",
            "status",
        ]

        widgets = {

            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter meeting title",
                    "maxlength": 200,
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Describe the meeting agenda, "
                        "purpose, or discussion topics..."
                    ),
                    "rows": 4,
                }
            ),

            "project": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "participants": forms.SelectMultiple(
                attrs={
                    "class": "form-select",
                    "size": 7,
                }
            ),

            "meeting_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "start_time": forms.TimeInput(
                format="%H:%M",
                attrs={
                    "class": "form-control",
                    "type": "time",
                    "step": 60,
                }
            ),

            "end_time": forms.TimeInput(
                format="%H:%M",
                attrs={
                    "class": "form-control",
                    "type": "time",
                    "step": 60,
                }
            ),

            "meeting_link": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "https://meet.google.com/..."
                    ),
                }
            ),

            "location": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Meeting room, office, "
                        "or physical location"
                    ),
                }
            ),

            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

        }

        labels = {
            "title": "Meeting Title",
            "description": "Description / Agenda",
            "project": "Project",
            "participants": "Participants",
            "meeting_date": "Meeting Date",
            "start_time": "Start Time",
            "end_time": "End Time",
            "meeting_link": "Online Meeting Link",
            "location": "Physical Location",
            "status": "Meeting Status",
        }

        help_texts = {
            "participants": (
                "Select project team members and the "
                "assigned Client. Hold Ctrl to select "
                "multiple participants."
            ),
            "meeting_link": (
                "Optional when a physical location "
                "is provided."
            ),
            "location": (
                "Optional when an online meeting "
                "link is provided."
            ),
            "end_time": (
                "Optional. If provided, the end time "
                "must be after the start time."
            ),
        }

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(self, user, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.user = user
        self.user_role = get_user_role(user)

        self.is_editing = bool(
            self.instance and self.instance.pk
        )

        self.original_project_id = (
            self.instance.project_id
            if self.is_editing
            else None
        )

        # ----------------------------------------------------
        # PROJECT PERMISSIONS
        # ----------------------------------------------------

        manageable_projects = get_manageable_projects(
            user
        )

        self.fields["project"].queryset = (
            manageable_projects
        )

        if self.is_editing:

            self.fields["project"].disabled = True

            self.fields["project"].queryset = (
                manageable_projects.filter(
                    pk=self.original_project_id,
                )
            )

        # ----------------------------------------------------
        # PARTICIPANT QUERYSET
        # ----------------------------------------------------

        self.fields["participants"].queryset = (
            User.objects.none()
        )

        selected_project = None

        if self.is_editing:

            selected_project = (
                manageable_projects.filter(
                    pk=self.original_project_id
                ).first()
            )

        elif self.is_bound:

            project_id = self.data.get(
                self.add_prefix("project")
            )

            try:
                selected_project = (
                    manageable_projects.filter(
                        pk=project_id,
                    ).first()
                )

            except (
                ValueError,
                TypeError,
                ValidationError,
            ):
                selected_project = None

        else:

            initial_project = self.initial.get(
                "project"
            )

            if isinstance(initial_project, Project):
                initial_project = initial_project.pk

            if initial_project:

                try:
                    selected_project = (
                        manageable_projects.filter(
                            pk=initial_project,
                        ).first()
                    )

                except (
                    ValueError,
                    TypeError,
                    ValidationError,
                ):
                    selected_project = None

        if selected_project:

            self.fields["participants"].queryset = (
                get_project_participants(
                    selected_project
                )
            )

        # ----------------------------------------------------
        # REQUIRED AND OPTIONAL FIELDS
        # ----------------------------------------------------

        self.fields["title"].required = True
        self.fields["project"].required = True
        self.fields["meeting_date"].required = True
        self.fields["start_time"].required = True

        self.fields["participants"].required = False
        self.fields["description"].required = False
        self.fields["end_time"].required = False
        self.fields["meeting_link"].required = False
        self.fields["location"].required = False

        # ----------------------------------------------------
        # DEFAULT STATUS
        # ----------------------------------------------------

        if not self.is_editing and not self.is_bound:
            self.fields["status"].initial = (
                "scheduled"
            )

        # ----------------------------------------------------
        # RESTRICT UNAUTHORIZED USERS
        # ----------------------------------------------------

        if not can_manage_meetings(user):

            self.fields["project"].queryset = (
                Project.objects.none()
            )

            self.fields["participants"].queryset = (
                User.objects.none()
            )

    # ========================================================
    # PROJECT VALIDATION
    # ========================================================

    def clean_project(self):

        project = self.cleaned_data.get(
            "project"
        )

        if not can_manage_meetings(self.user):

            raise ValidationError(
                "You do not have permission "
                "to manage meetings."
            )

        if not project:

            raise ValidationError(
                "Please select a valid project."
            )

        if not get_manageable_projects(
            self.user
        ).filter(
            pk=project.pk
        ).exists():

            raise ValidationError(
                "You are not authorized to "
                "manage meetings for this project."
            )

        if self.is_editing:

            if project.pk != self.original_project_id:

                raise ValidationError(
                    "The project cannot be changed "
                    "after creating a meeting."
                )

        return project

    # ========================================================
    # PARTICIPANT VALIDATION
    # ========================================================

    def clean_participants(self):

        participants = self.cleaned_data.get(
            "participants"
        )

        if participants is None:
            return participants

        project = self.cleaned_data.get(
            "project"
        )

        if not project:
            return participants

        eligible_participants = (
            get_project_participants(
                project
            )
        )

        invalid_participants = participants.exclude(
            pk__in=eligible_participants.values_list(
                "pk",
                flat=True,
            )
        )

        if invalid_participants.exists():

            raise ValidationError(
                "Participants must be active, "
                "approved users assigned to "
                "the selected project, including "
                "its assigned Client."
            )

        return participants

    # ========================================================
    # MEETING DATE VALIDATION
    # ========================================================

    def clean_meeting_date(self):

        meeting_date = self.cleaned_data.get(
            "meeting_date"
        )

        if not meeting_date:
            return meeting_date

        if not self.is_editing:

            if meeting_date < timezone.localdate():

                raise ValidationError(
                    "A new meeting cannot be "
                    "scheduled on a past date."
                )

        return meeting_date

    # ========================================================
    # FORM-WIDE VALIDATION
    # ========================================================

    def clean(self):

        cleaned_data = super().clean()

        if not can_manage_meetings(self.user):

            raise ValidationError(
                "You are not authorized to "
                "create or edit meetings."
            )

        start_time = cleaned_data.get(
            "start_time"
        )

        end_time = cleaned_data.get(
            "end_time"
        )

        meeting_link = (
            cleaned_data.get("meeting_link")
            or ""
        ).strip()

        location = (
            cleaned_data.get("location")
            or ""
        ).strip()

        # ----------------------------------------------------
        # VALIDATE TIME RANGE
        # ----------------------------------------------------

        if (
            start_time
            and end_time
            and end_time <= start_time
        ):

            self.add_error(
                "end_time",
                "End time must be later "
                "than the start time."
            )

        # ----------------------------------------------------
        # VALIDATE LOCATION OR LINK
        # ----------------------------------------------------

        if not meeting_link and not location:

            self.add_error(
                "location",
                "Provide a physical location "
                "or an online meeting link."
            )

        # ----------------------------------------------------
        # VALIDATE PARTICIPANTS AGAINST PROJECT
        # ----------------------------------------------------

        project = cleaned_data.get(
            "project"
        )

        participants = cleaned_data.get(
            "participants"
        )

        if project and participants is not None:

            allowed_ids = (
                get_project_participants(
                    project
                ).values_list(
                    "pk",
                    flat=True,
                )
            )

            invalid_participants = (
                participants.exclude(
                    pk__in=allowed_ids,
                )
            )

            if invalid_participants.exists():

                self.add_error(
                    "participants",
                    "All participants must belong "
                    "to the selected project."
                )

        return cleaned_data

    # ========================================================
    # SAVE
    # ========================================================

    def save(self, commit=True):

        if not can_manage_meetings(self.user):

            raise ValidationError(
                "You do not have permission "
                "to save meetings."
            )

        meeting = super().save(
            commit=False
        )

        if not self.is_editing:
            meeting.organizer = self.user

        if commit:
            meeting.save()
            self.save_m2m()

        return meeting
