from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from orcSync.serializers import WorkStationSerializer
from workstations.models import WorkStation


class WorkStationListView(APIView):
    """
    API view for listing all workstations.
    
    Provides a simple list of all workstations in the system for synchronization purposes.
    """

    @extend_schema(
        summary="List all workstations",
        description="""Retrieve a list of all workstations in the system.
        
        **Use Case:**
        - Used by synchronization systems to get a list of all available workstations
        - Helps in configuring sync relationships between stations
        """,
        tags=["Sync - Configuration"],
        responses={
            200: WorkStationSerializer(many=True),
        },
    )
    def get(self, request, format=None):
        workstations = WorkStation.objects.all()
        serializer = WorkStationSerializer(workstations, many=True)
        return Response(serializer.data)
