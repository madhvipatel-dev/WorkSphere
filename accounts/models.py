from django.conf import settings
from django.db import models


class UserProfile(models.Model):

    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("employee", "Employee"),
         ("client", "Client"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="employee",
    )

    
    requested_role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="employee",
    )

    is_approved = models.BooleanField(default=True)


    phone = models.CharField(
        max_length=20,
        blank=True,
    )

    department = models.ForeignKey(
        "ws_departments.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )

    job_title = models.CharField(
        max_length=100,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"