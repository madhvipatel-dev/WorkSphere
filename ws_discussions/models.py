
from django.conf import settings
from django.db import models


class Discussion(models.Model):
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="discussions",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="worksphere_discussions",
    )

    message = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        room = self.project.name if self.project else "General Discussion"
        return f"{room} - {self.author} - {self.created_at:%Y-%m-%d %H:%M}"
