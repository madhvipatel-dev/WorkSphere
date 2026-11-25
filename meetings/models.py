
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from projects.models import Project


# ============================================================
# MEETING MODEL
# ============================================================

class Meeting(models.Model):

    # --------------------------------------------------------
    # MEETING STATUS
    # --------------------------------------------------------

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    # --------------------------------------------------------
    # BASIC INFORMATION
    # --------------------------------------------------------

    title = models.CharField(
        max_length=200,
    )

    description = models.TextField(
        blank=True,
    )

    # --------------------------------------------------------
    # PROJECT RELATIONSHIP
    # --------------------------------------------------------

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="meetings",
    )

    # --------------------------------------------------------
    # ORGANIZER
    # --------------------------------------------------------

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organized_meetings",
    )

    # --------------------------------------------------------
    # PARTICIPANTS
    # --------------------------------------------------------

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="meetings",
    )

    # --------------------------------------------------------
    # MEETING SCHEDULE
    # --------------------------------------------------------

    meeting_date = models.DateField()

    start_time = models.TimeField()

    end_time = models.TimeField(
        null=True,
        blank=True,
    )

    # --------------------------------------------------------
    # MEETING LOCATION / LINK
    # --------------------------------------------------------

    meeting_link = models.URLField(
        blank=True,
    )

    location = models.CharField(
        max_length=255,
        blank=True,
    )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
    )

    # --------------------------------------------------------
    # TIMESTAMPS
    # --------------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # ========================================================
    # MODEL META
    # ========================================================

    class Meta:

        ordering = [
            "meeting_date",
            "start_time",
            "pk",
        ]

        verbose_name = "Meeting"
        verbose_name_plural = "Meetings"

    # ========================================================
    # STRING REPRESENTATION
    # ========================================================

    def __str__(self):
        return self.title

    # ========================================================
    # MODEL VALIDATION
    # ========================================================

    def clean(self):
        """
        Validate the meeting schedule.

        Rules:
        1. End time must be after start time.
        2. Newly scheduled meetings cannot start
           in the past.
        3. Meetings must have either a physical
           location or an online meeting link.
        """
        super().clean()

        errors = {}

        # ----------------------------------------------------
        # VALIDATE START AND END TIME
        # ----------------------------------------------------

        if self.start_time and self.end_time:

            if self.end_time <= self.start_time:
                errors["end_time"] = (
                    "End time must be later than start time."
                )

        # ----------------------------------------------------
        # VALIDATE SCHEDULED DATE
        # ----------------------------------------------------

        if (
            self.status == "scheduled"
            and self.meeting_date
            and self.start_time
        ):

            # Enforce future dates only for new meetings.
            # Existing meetings can still be edited
            # after their scheduled time has passed.
            if self._state.adding:

                current_time = timezone.localtime()

                meeting_datetime = datetime.combine(
                    self.meeting_date,
                    self.start_time,
                )

                meeting_datetime = timezone.make_aware(
                    meeting_datetime,
                    timezone.get_current_timezone(),
                )

                if meeting_datetime < current_time:
                    errors["meeting_date"] = (
                        "New meetings cannot be scheduled "
                        "in the past."
                    )

        # ----------------------------------------------------
        # VALIDATE MEETING LOCATION
        # ----------------------------------------------------

        meeting_link = (
            self.meeting_link or ""
        ).strip()

        location = (
            self.location or ""
        ).strip()

        if not meeting_link and not location:
            errors["location"] = (
                "Provide a meeting location "
                "or an online meeting link."
            )

        # ----------------------------------------------------
        # RAISE VALIDATION ERRORS
        # ----------------------------------------------------

        if errors:
            raise ValidationError(errors)

    # ========================================================
    # MEETING DATE/TIME HELPERS
    # ========================================================

    @property
    def starts_at(self):
        """
        Return the timezone-aware meeting start
        datetime using Django's configured timezone.
        """
        if not self.meeting_date or not self.start_time:
            return None

        naive_datetime = datetime.combine(
            self.meeting_date,
            self.start_time,
        )

        return timezone.make_aware(
            naive_datetime,
            timezone.get_current_timezone(),
        )

    @property
    def ends_at(self):
        """
        Return the timezone-aware meeting end
        datetime when an end time exists.
        """
        if (
            not self.meeting_date
            or not self.end_time
        ):
            return None

        naive_datetime = datetime.combine(
            self.meeting_date,
            self.end_time,
        )

        return timezone.make_aware(
            naive_datetime,
            timezone.get_current_timezone(),
        )

    # ========================================================
    # MEETING STATUS HELPERS
    # ========================================================

    @property
    def is_cancelled(self):
        return self.status == "cancelled"

    @property
    def is_completed(self):
        return self.status == "completed"

    @property
    def is_scheduled(self):
        return self.status == "scheduled"

    @property
    def is_upcoming(self):
        """
        True when a meeting is scheduled
        and its start time is in the future.
        """
        if not self.is_scheduled:
            return False

        start = self.starts_at

        if start is None:
            return False

        return start > timezone.now()

    @property
    def is_past(self):
        """
        True when the meeting's start time
        has already passed.
        """
        start = self.starts_at

        if start is None:
            return False

        return start < timezone.now()

    @property
    def is_today(self):
        """
        True when the meeting is scheduled
        for today's local date.
        """
        if not self.meeting_date:
            return False

        return (
            self.meeting_date
            == timezone.localdate()
        )

    # ========================================================
    # PARTICIPANT HELPERS
    # ========================================================

    @property
    def participant_count(self):
        """
        Return the number of meeting participants.
        """
        if not self.pk:
            return 0

        return self.participants.count()

    def is_participant(self, user):
        """
        Check whether a user is explicitly
        included in the meeting participants.
        """
        if (
            not self.pk
            or not user.is_authenticated
            or not user.is_active
        ):
            return False

        return self.participants.filter(
            pk=user.pk
        ).exists()

    # ========================================================
    # SAVE
    # ========================================================

    def save(self, *args, **kwargs):
        """
        Validate meeting data before saving.

        Note:
        Participant membership and organizer/project
        authorization must be enforced in forms
        and views because those depend on the
        currently logged-in user.
        """
        self.full_clean()

        return super().save(*args, **kwargs)
