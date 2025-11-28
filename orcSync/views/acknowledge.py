from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample
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

    @extend_schema(
        summary="Acknowledge applied changes",
        description="""Report that a workstation has successfully applied specific changes.
        
        **Authentication:**
        - Requires workstation API key authentication
        
        **Process:**
        1. Workstation provides list of event IDs it has applied
        2. System updates corresponding SyncAcknowledgement records
        3. Changes status from 'P' (Pending) to 'A' (Acknowledged)
        4. Records acknowledgement timestamp
        
        **Use Case:**
        - Called after workstation successfully applies changes
        - Confirms synchronization completion
        - Allows central server to track sync progress
        - Enables cleanup of fully acknowledged events
        """,
        tags=["Sync - Data Transfer"],
        request=AcknowledgeEventsSerializer,
        responses={
            200: {
                "description": "Events acknowledged successfully",
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "message": {"type": "string"}
                }
            },
            400: {"description": "Bad Request - Invalid event IDs"},
            401: {"description": "Unauthorized - Invalid API key"},
        },
        examples=[
            OpenApiExample(
                "Acknowledge Request",
                value={
                    "acknowledged_events": [123, 124, 125]
                },
                request_only=True,
            ),
            OpenApiExample(
                "Acknowledge Response",
                value={
                    "status": "success",
                    "message": "3 events acknowledged."
                },
                response_only=True,
            ),
        ],
    )
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
