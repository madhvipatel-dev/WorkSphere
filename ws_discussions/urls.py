
from django.urls import path

from . import views


app_name = "ws_discussions"


urlpatterns = [
    # General Team Discussions
    path(
        "",
        views.discussion_list,
        name="discussion_list",
    ),
    path(
        "send/",
        views.send_message,
        name="send_message",
    ),
    path(
        "messages/",
        views.messages_json,
        name="messages_json",
    ),

    # Project-wise Discussions
    path(
        "project/<int:project_id>/",
        views.project_discussion_list,
        name="project_discussion",
    ),
    path(
        "project/<int:project_id>/send/",
        views.send_project_message,
        name="send_project_message",
    ),
    path(
        "project/<int:project_id>/messages/",
        views.project_messages_json,
        name="project_messages_json",
    ),
]
