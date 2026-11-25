
from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "action",
        "ip_address",
        "request_path",
        "status_code",
        "created_at",
    )

    list_filter = (
        "action",
        "status_code",
        "created_at",
    )

    search_fields = (
        "user__username",
        "action",
        "description",
        "request_path",
        "ip_address",
    )

    readonly_fields = (
        "user",
        "action",
        "description",
        "ip_address",
        "request_path",
        "status_code",
        "created_at",
    )

    ordering = ("-created_at",)