
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from projects.models import Project


@login_required
def team_list(request):
    projects = (
        Project.objects
        .select_related("owner")
        .prefetch_related("members")
    )

    # Admins can see all projects.
    # Regular users see projects they own or belong to.
    if not request.user.is_superuser and not request.user.is_staff:
        projects = projects.filter(
            Q(owner=request.user) | Q(members=request.user)
        ).distinct()

    projects = projects.order_by("name")

    return render(
        request,
        "worksphere_team/team_list.html",
        {"projects": projects},
    )
