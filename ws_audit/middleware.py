
from .models import AuditLog


class AuditLogMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        if request.method == "POST":
            try:
                user = request.user

                AuditLog.objects.create(
                    user=user if user.is_authenticated else None,
                    action="POST Request",
                    description=(
                        f"{request.method} request "
                        f"returned status {response.status_code}"
                    ),
                    ip_address=request.META.get("REMOTE_ADDR"),
                    request_path=request.path[:500],
                    status_code=response.status_code,
                )

            except Exception as error:
                print("Audit log error:", error)

        return response