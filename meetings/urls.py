
from django.urls import path

from . import views


# ============================================================
# WORKSPHERE - MEETING MANAGEMENT URLS
# ============================================================

urlpatterns = [

    # --------------------------------------------------------
    # MEETING LIST
    # --------------------------------------------------------

    path(
        "",
        views.meeting_list,
        name="meeting_list",
    ),

    # --------------------------------------------------------
    # CREATE MEETING
    # --------------------------------------------------------

    path(
        "create/",
        views.meeting_create,
        name="meeting_create",
    ),

    # --------------------------------------------------------
    # LOAD ELIGIBLE PROJECT PARTICIPANTS
    # --------------------------------------------------------

    path(
        "project-participants/",
        views.meeting_project_participants,
        name="meeting_project_participants",
    ),

    # --------------------------------------------------------
    # MEETING DETAILS
    # --------------------------------------------------------

    path(
        "<int:meeting_id>/",
        views.meeting_detail,
        name="meeting_detail",
    ),

    # --------------------------------------------------------
    # EDIT MEETING
    # --------------------------------------------------------

    path(
        "<int:meeting_id>/edit/",
        views.meeting_edit,
        name="meeting_edit",
    ),

    # --------------------------------------------------------
    # DELETE MEETING
    # --------------------------------------------------------

    path(
        "<int:meeting_id>/delete/",
        views.meeting_delete,
        name="meeting_delete",
    ),

]
