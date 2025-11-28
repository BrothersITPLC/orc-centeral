from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample
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

    @extend_schema(
        summary="Get pending changes for workstation",
        description="""Retrieve all pending changes that a workstation needs to apply.
        
        **Authentication:**
        - Requires workstation API key authentication
        
        **Process:**
        1. Identifies the requesting workstation via API key
        2. Retrieves all pending SyncAcknowledgements for this workstation
        3. Returns the associated ChangeEvents with full data
        4. Returns list of fully acknowledged events from this workstation
        5. Updates workstation's last_seen timestamp
        
        **Response Structure:**
        - `pending_changes`: Array of changes to apply locally
        - `acknowledged_events`: Array of event IDs that have been fully synced
        
        **Use Case:**
        - Workstation polls this endpoint periodically
        - Receives changes from other workstations
        - Learns which of its own changes have propagated
        """,
        tags=["Sync - Data Transfer"],
        responses={
            200: {
                "description": "Pending changes retrieved successfully",
                "type": "object",
                "properties": {
                    "pending_changes": {"type": "array"},
                    "acknowledged_events": {"type": "array"}
                }
            },
            401: {"description": "Unauthorized - Invalid API key"},
        },
        examples=[
            OpenApiExample(
                "Get Pending Response",
                value={
                    "pending_changes": [
                        {
                            "id": 123,
                            "model": "drivers.Driver",
                            "object_id": 456,
                            "action": "U",
                            "data_payload": {
                                "first_name": "Abebe",
                                "last_name": "Tadesse"
                            },
                            "timestamp": "2024-01-20T10:30:00Z"
                        }
                    ],
                    "acknowledged_events": [101, 102, 103]
                },
                response_only=True,
            ),
        ],
    )
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
