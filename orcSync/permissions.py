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
        print(header, " it is header")
        if not header or not header.lower().startswith("api-key"):
            return False

        try:
            key = header.split(" ")[1]
            print(key, " it is key")
        except ValueError:
            return False

        try:
            credential = StationCredential.objects.select_related("location").get(
                api_key=key
            )
            print(credential, " it is credential")
            workstation = credential.location
            request._request.workstation = workstation

            return True
        except StationCredential.DoesNotExist:
            print("SYNC_SERVER WARNING: API Key not found.")
            return False
