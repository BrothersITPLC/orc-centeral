from rest_framework.permissions import BasePermission

from .models import StationCredential


class WorkstationHasAPIKey(BasePermission):
    """
    A single, custom permission class that validates the API Key
    by looking it up directly in the StationCredential model.
    """

    message = "Invalid or missing API Key."

    def has_permission(self, request, view):
        header = request.META.get("HTTP_AUTHORIZATION")
        if not header or not header.lower().startswith("api-key "):
            return False

        try:
            _, key = header.split()
        except ValueError:
            return False

        try:
            credential = StationCredential.objects.select_related("location").get(
                api_key=key
            )
            workstation = credential.location
            request._request.workstation = workstation

            return True
        except StationCredential.DoesNotExist:
            return False
