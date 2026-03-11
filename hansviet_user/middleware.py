from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class LoginRequiredMiddleware(MiddlewareMixin):
    """
    Redirect anonymous users to LOGIN_URL unless path is exempt.
    """

    def process_request(self, request):
        # Skip if already authenticated
        if request.user.is_authenticated:
            return None

        path = request.path
        admin_login_url = getattr(settings, "ADMIN_LOGIN_URL", "/hansviet_admin/login/")
        admin_prefix = "/hansviet_admin/"
        admin_login_prefix = admin_login_url.rstrip("/")

        # Keep admin authentication separate from user authentication.
        if path.startswith(admin_prefix) and not path.startswith(admin_login_prefix):
            return redirect(f"{admin_login_url}?next={request.get_full_path()}")

        # Allow exempt paths/prefixes
        for exempt in getattr(settings, "LOGIN_EXEMPT_URLS", []):
            # Allow exactly '/' when listed, without whitelisting everything
            if exempt == "/" and path == "/":
                return None
            if exempt != "/" and path.startswith(exempt):
                return None

        # Otherwise, send to login with next param
        login_url = settings.LOGIN_URL
        return redirect(f"{login_url}?next={request.get_full_path()}")
