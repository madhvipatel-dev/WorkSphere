ROLE_PERMISSIONS = {
    "admin": {
        "dashboard": True,
        "projects": True,
        "tasks": True,
        "meetings": True,
        "files": True,
        "team": True,
        "discussions": True,
        "notifications": True,
        "employees": True,
        "users": True,
        "departments": True,
        "reports": True,
        "audit_logs": True,
        "settings": True,
    },

    "manager": {
        "dashboard": True,
        "projects": True,
        "tasks": True,
        "meetings": True,
        "files": True,
        "team": True,
        "discussions": True,
        "notifications": True,
        "employees": True,
        "users": False,
        "departments": False,
        "reports": True,
        "audit_logs": False,
        "settings": False,
    },

    "employee": {
        "dashboard": True,
        "projects": True,
        "tasks": True,
        "meetings": True,
        "files": True,
        "team": True,
        "discussions": True,
        "notifications": True,
        "employees": False,
        "users": False,
        "departments": False,
        "reports": False,
        "audit_logs": False,
        "settings": False,
    },
}


PERMISSION_LABELS = {
    "dashboard": "Dashboard",
    "projects": "Projects",
    "tasks": "Tasks",
    "meetings": "Meetings",
    "files": "Files",
    "team": "Team",
    "discussions": "Discussions",
    "notifications": "Notifications",
    "employees": "Manage Employees",
    "users": "Manage Users",
    "departments": "Manage Departments",
    "reports": "Reports",
    "audit_logs": "Audit Logs",
    "settings": "System Settings",
}


PERMISSION_ICONS = {
    "dashboard": "fa-solid fa-gauge-high",
    "projects": "fa-solid fa-folder",
    "tasks": "fa-solid fa-list-check",
    "meetings": "fa-solid fa-calendar-days",
    "files": "fa-solid fa-file",
    "team": "fa-solid fa-users",
    "discussions": "fa-solid fa-comments",
    "notifications": "fa-solid fa-bell",
    "employees": "fa-solid fa-user-tie",
    "users": "fa-solid fa-users-gear",
    "departments": "fa-solid fa-building",
    "reports": "fa-solid fa-chart-column",
    "audit_logs": "fa-solid fa-clock-rotate-left",
    "settings": "fa-solid fa-gear",
}


ROLE_LABELS = {
    "admin": "Administrator",
    "manager": "Manager",
    "employee": "Employee",
}