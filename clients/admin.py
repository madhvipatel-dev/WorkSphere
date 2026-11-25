
from django.contrib import admin
from .models import ProjectRequest, ClientFeedback


@admin.register(ProjectRequest)
class ProjectRequestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "client",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("title", "client__username")


@admin.register(ClientFeedback)
class ClientFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "project_request",
        "client",
        "created_at",
    )
