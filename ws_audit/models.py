
from django.conf import settings
from django.db import models


class AuditLog(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    action = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    request_path = models.CharField(max_length=500)

    status_code = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.created_at}"