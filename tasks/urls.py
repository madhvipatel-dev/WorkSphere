
from django.urls import path

from . import review_views
from . import views
from . import employee_views


urlpatterns = [

    path(
        "",
        views.task_list,
        name="task_list",
    ),

    path(
        "my-tasks/",
        views.employee_task_list,
        name="employee_task_list",
    ),

    # Load project Employees dynamically
    path(
        "project-employees/",
        employee_views.project_employees,
        name="project_employees",
    ),

    path(
        "<int:task_id>/status/",
        views.update_task_status,
        name="update_task_status",
    ),

    path(
        "<int:task_id>/comment/",
        views.add_task_comment,
        name="add_task_comment",
    ),

    path(
        "<int:task_id>/submit-work/",
        views.submit_work,
        name="submit_work",
    ),

    path(
        "manager/submissions/",
        review_views.manager_submissions,
        name="manager_submissions",
    ),

    path(
        "manager/submissions/<int:submission_id>/",
        review_views.review_submission,
        name="review_submission",
    ),

    path(
        "create/",
        views.task_create,
        name="task_create",
    ),

    path(
        "<int:task_id>/",
        views.task_detail,
        name="task_detail",
    ),

    path(
        "<int:task_id>/edit/",
        views.task_edit,
        name="task_edit",
    ),

    path(
        "<int:task_id>/delete/",
        views.task_delete,
        name="task_delete",
    ),
]