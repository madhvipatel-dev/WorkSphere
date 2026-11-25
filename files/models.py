
import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.text import get_valid_filename


# ============================================================
# FILE UPLOAD SETTINGS
# ============================================================

ALLOWED_FILE_EXTENSIONS = [
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "txt",
    "csv",
    "jpg",
    "jpeg",
    "png",
    "webp",
    "zip",
]

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_project_file_size(value):
    """
    Reject uploaded files larger than 10 MB.
    """
    if value.size > MAX_FILE_SIZE:
        raise ValidationError(
            "File size must not exceed 10 MB."
        )


def project_file_upload_path(instance, filename):
    """
    Store files in project-specific folders.

    A random identifier prevents filename collisions.

    Example:
        project_files/project_5/uuid_report.pdf
    """
    original_name = os.path.basename(
        str(filename).replace("\\", "/")
    )

    safe_name = get_valid_filename(original_name)

    if not safe_name:
        safe_name = "upload"

    unique_name = (
        f"{uuid.uuid4().hex}_{safe_name}"
    )

    return (
        f"project_files/project_{instance.project_id}/"
        f"{unique_name}"
    )


# ============================================================
# PROJECT FILE MODEL
# ============================================================

class ProjectFile(models.Model):

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="files",
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_files",
    )

    title = models.CharField(
        max_length=200,
    )

    description = models.TextField(
        blank=True,
    )

    file = models.FileField(
        upload_to=project_file_upload_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=ALLOWED_FILE_EXTENSIONS
            ),
            validate_project_file_size,
        ],
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-uploaded_at",
            "-pk",
        ]

        verbose_name = "Project File"
        verbose_name_plural = "Project Files"

    def __str__(self):
        return self.title

    # =================================================