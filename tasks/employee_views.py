
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .forms import get_approved_role, get_task_manageable_projects


User = get_user_model()


@login_required
@require_GET
def project_employees(request):
    """
    Return eligible Employees for a project.

    Only approved Admins and Managers can use
    this endpoint, and only for projects they
    are authorized to manage tasks in.
    """

    role = get_approved_role(request.user)

    if role not in ("admin", "manager"):
        return JsonResponse(
            {"error": "Permission denied."},
            status=403,
        )

    project_id = request.GET.get(
        "project_id", ""
    ).strip()

    if not project_id.isdigit():
        return JsonResponse(
            {"employees": []}
        )

    project = (
        get_task_manageable_projects(request.user)
        .filter(pk=project_id)
        .first()
    )

    if project is None:
        return JsonResponse(
            {"error": "Project not found or access denied."},
            status=404,
        )

    employees = (
        User.objects.filter(
            is_active=True,
            profile__role="employee",
            profile__is_approved=True,
            projects=project,
        )
        .distinct()
        .order_by("username")
    )

    return JsonResponse({
        "employees": [
            {
                "id": employee.pk,
                "username": employee.username,
            }
            for employee in employees
        ]
    })
