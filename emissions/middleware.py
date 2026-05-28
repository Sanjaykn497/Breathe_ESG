import json
from django.contrib.auth import get_user_model
from emissions.models import Organization
from emissions.enums import UserRole

User = get_user_model()

class DevAuthenticationMiddleware:
    """
    Development-only middleware that automatically authenticates a mock user
    based on the X-Mock-User header or falls back to a default Analyst.
    Only active in development (DEBUG = True).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        if settings.DEBUG:
            mock_user_header = request.headers.get("X-Mock-User")
            
            email = "analyst@breathe.io"
            role = UserRole.ANALYST
            
            if mock_user_header:
                try:
                    user_data = json.loads(mock_user_header)
                    email = user_data.get("email", email)
                    role = user_data.get("role", role)
                except Exception:
                    pass
            
            # Auto-create organization if not exists
            org, _ = Organization.objects.get_or_create(
                slug="breathe-corp",
                defaults={"name": "Breathe Corp"},
            )
            
            # Auto-create or fetch the user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "organization": org,
                    "role": role,
                    "is_active": True,
                }
            )
            
            # If the user role has changed (e.g. analyst logged in then admin), update it
            if not created and user.role != role:
                user.role = role
                user.save()
                
            request.user = user

        return self.get_response(request)


from rest_framework.authentication import SessionAuthentication

class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Custom SessionAuthentication that bypasses CSRF checks in development.
    """
    def enforce_csrf(self, request):
        return
