from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from orcSync.models import SyncAcknowledgement
from orcSync.permissions import WorkstationHasAPIKey
from orcSync.serializers import AcknowledgeEventsSerializer


class AcknowledgeChangesView(APIView):
    """
    Allows a workstation to report that it has successfully applied a list of changes.
    """

    permission_classes = [HasAPIKey, WorkstationHasAPIKey]

    def post(self, request, *args, **kwargs):
        serializer = AcknowledgeEventsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        workstation = request._request.workstation

        event_ids = serializer.validated_data["acknowledged_events"]

        updated_count = SyncAcknowledgement.objects.filter(
            destination_workstation=workstation,
            change_event_id__in=event_ids,
            status="P",
        ).update(status="A", acknowledged_at=timezone.now())

        return Response(
            {"status": "success", "message": f"{updated_count} events acknowledged."},
            status=status.HTTP_200_OK,
        )
