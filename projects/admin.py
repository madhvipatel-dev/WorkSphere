
from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "owner",
        "client",
        "status",
        "progress_display",
        "deadline",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
        "deadline",
    )

    search_fields = (
        "name",
        "description",
        "owner__username",
        "client__username",
    )

    autocomplete_fields = (
        "owner",
    )

    filter_horizontal = (
        "members",
    )

    readonly_fields = (
        "progress_display",
        "total_tasks_display",
        "completed_tasks_display",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Project Information",
            {
                "fields": (
                    "name",
                    "description",
                    "status",
                    "start_date",
                    "deadline",
                )
            },
        ),
        (
            "Project Assignment",
            {
                "fields": (
                    "owner",
                    "client",
                    "members",
                )
            },
        ),
        (
            "Project Progress",
            {
                "fields": (
                    "total_tasks_display",
                    "completed_tasks_display",
                    "progress_display",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Total Tasks")
    def total_tasks_display(self, obj):
        if not obj.pk:
            return 0
        return obj.total_tasks

    @admin.display(description="Completed Tasks")
    def completed_tasks_display(self, obj):
        if not obj.pk:
            return 0
        return obj.completed_tasks

    @admin.display(description="Progress")
    def progress_display(self, obj):
        if not obj.pk:
            return "0%"
        return f"{obj.progress_percentage}%"
