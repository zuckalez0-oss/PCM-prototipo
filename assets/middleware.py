from .models import AcessoLog

class AccessLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request
        response = self.get_response(request)

        # Log after response is generated
        try:
            # Capture IP (handling potential proxy headers)
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')

            AcessoLog.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                ip_address=ip,
                path=request.path,
                method=request.method,
                status_code=response.status_code,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
            )
        except Exception:
            # Avoid breaking the site if logging fails
            pass

        return response
