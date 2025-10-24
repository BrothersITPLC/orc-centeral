from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from orcSync.models import ChangeEvent, SyncAcknowledgement
from orcSync.permissions import WorkstationHasAPIKey
from orcSync.serializers import OutboundChangeSerializer
from workstations.models import WorkStation


class GetPendingChangesView(APIView):
    """
    Provides a workstation with all changes it needs to apply and confirms
    which of its previously sent changes have been fully processed.
    """

    permission_classes = [WorkstationHasAPIKey]

    def get(self, request, *args, **kwargs):
        workstation = request._request.workstation

        pending_acks = (
            SyncAcknowledgement.objects.select_related(
                "change_event", "change_event__content_type"
            )
            .prefetch_related("change_event__changed_object")
            .filter(destination_workstation=workstation, status="P")
        )

        pending_changes_events = [ack.change_event for ack in pending_acks]

        fully_acknowledged_events = (
            ChangeEvent.objects.filter(source_workstation=workstation)
            .exclude(acknowledgements__status="P")
            .values_list("id", flat=True)
        )

        pending_changes_serializer = OutboundChangeSerializer(
            pending_changes_events, many=True, context={"request": request}
        )

        response_data = {
            "pending_changes": pending_changes_serializer.data,
            "acknowledged_events": list(fully_acknowledged_events),
        }

        if hasattr(workstation, "last_seen"):
            workstation.last_seen = timezone.now()
            workstation.save(update_fields=["last_seen"])

        return Response(response_data, status=status.HTTP_200_OK)
