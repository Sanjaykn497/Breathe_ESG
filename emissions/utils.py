from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status


def exception_handler(exc, context):
    """
    Custom DRF exception handler — maps Django exceptions to proper HTTP responses.
    """
    # Let DRF handle its own exceptions first
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, PermissionDenied):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

    if isinstance(exc, DjangoValidationError):
        return Response(
            {"detail": exc.messages if hasattr(exc, "messages") else str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Unhandled — let Django's 500 handler take over in production
    return None
