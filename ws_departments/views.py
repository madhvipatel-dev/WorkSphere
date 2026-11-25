from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import permission_required

from .models import Department


@permission_required("departments")
def department_list(request):
    departments = (
        Department.objects
        .select_related("manager")
        .all()
    )

    search_query = request.GET.get(
        "search",
        "",
    ).strip()

    status_filter = request.GET.get(
        "status",
        "",
    ).strip()

    if search_query:
        departments = departments.filter(
            name__icontains=search_query
        ) | departments.filter(
            code__icontains=search_query
        )

    if status_filter == "active":
        departments = departments.filter(
            is_active=True
        )

    elif status_filter == "inactive":
        departments = departments.filter(
            is_active=False
        )

    total_departments = Department.objects.count()

    active_departments = Department.objects.filter(
        is_active=True
    ).count()

    inactive_departments = Department.objects.filter(
        is_active=False
    ).count()

    assigned_managers = Department.objects.filter(
        manager__isnull=False
    ).count()

    context = {
        "departments": departments,
        "search_query": search_query,
        "status_filter": status_filter,
        "total_departments": total_departments,
        "active_departments": active_departments,
        "inactive_departments": inactive_departments,
        "assigned_managers": assigned_managers,
    }

    return render(
        request,
        "ws_departments/department_list.html",
        context,
    )


@permission_required("departments")
def department_create(request):
    managers = User.objects.filter(
        is_active=True
    ).order_by("username")

    if request.method == "POST":

        name = request.POST.get(
            "name",
            "",
        ).strip()

        code = request.POST.get(
            "code",
            "",
        ).strip().upper()

        description = request.POST.get(
            "description",
            "",
        ).strip()

        manager_id = request.POST.get(
            "manager"
        )

        is_active = request.POST.get(
            "is_active"
        ) == "on"

        if not name or not code:

            messages.error(
                request,
                "Department name and code are required.",
            )

            return render(
                request,
                "ws_departments/department_form.html",
                {
                    "department": None,
                    "managers": managers,
                    "form_data": request.POST,
                },
            )

        if Department.objects.filter(
            name__iexact=name
        ).exists():

            messages.error(
                request,
                "A department with this name already exists.",
            )

            return render(
                request,
                "ws_departments/department_form.html",
                {
                    "department": None,
                    "managers": managers,
                    "form_data": request.POST,
                },
            )

        if Department.objects.filter(
            code__iexact=code
        ).exists():

            messages.error(
                request,
                "A department with this code already exists.",
            )

            return render(
                request,
                "ws_departments/department_form.html",
                {
                    "department": None,
                    "managers": managers,
                    "form_data": request.POST,
                },
            )

        manager = None

        if manager_id:
            manager = get_object_or_404(
                User,
                id=manager_id,
                is_active=True,
            )

        Department.objects.create(
            name=name,
            code=code,
            description=description,
            manager=manager,
            is_active=is_active,
        )

        messages.success(
            request,
            f"{name} department was created successfully.",
        )

        return redirect(
            "department_list"
        )

    return render(
        request,
        "ws_departments/department_form.html",
        {
            "department": None,
            "managers": managers,
        },
    )


@permission_required("departments")
def department_edit(request, department_id):

    department = get_object_or_404(
        Department,
        id=department_id,
    )

    managers = User.objects.filter(
        is_active=True
    ).order_by("username")

    if request.method == "POST":

        name = request.POST.get(
            "name",
            "",
        ).strip()

        code = request.POST.get(
            "code",
            "",
        ).strip().upper()

        description = request.POST.get(
            "description",
            "",
        ).strip()

        manager_id = request.POST.get(
            "manager"
        )

        is_active = request.POST.get(
            "is_active"
        ) == "on"

        if not name or not code:

            messages.error(
                request,
                "Department name and code are required.",
            )

            return render(
                request,
                "ws_departments/department_form.html",
                {
                    "department": department,
                    "managers": managers,
                },
            )

        if Department.objects.filter(
            name__iexact=name
        ).exclude(
            id=department.id
        ).exists():

            messages.error(
                request,
                "A department with this name already exists.",
            )

            return render(
                request,
                "ws_departments/department_form.html",
                {
                    "department": department,
                    "managers": managers,
                },
            )

        if Department.objects.filter(
            code__iexact=code
        ).exclude(
            id=department.id
        ).exists():

            messages.error(
                request,
                "A department with this code already exists.",
            )

            return render(
                request,
                "ws_departments/department_form.html",
                {
                    "department": department,
                    "managers": managers,
                },
            )

        manager = None

        if manager_id:
            manager = get_object_or_404(
                User,
                id=manager_id,
                is_active=True,
            )

        department.name = name
        department.code = code
        department.description = description
        department.manager = manager
        department.is_active = is_active

        department.save()

        messages.success(
            request,
            f"{name} department was updated successfully.",
        )

        return redirect(
            "department_list"
        )

    return render(
        request,
        "ws_departments/department_form.html",
        {
            "department": department,
            "managers": managers,
        },
    )


@permission_required("departments")
def department_delete(request, department_id):

    department = get_object_or_404(
        Department,
        id=department_id,
    )

    if request.method != "POST":
        return redirect(
            "department_list"
        )

    department_name = department.name

    department.delete()

    messages.success(
        request,
        f"{department_name} department was deleted successfully.",
    )

    return redirect(
        "department_list"
    )