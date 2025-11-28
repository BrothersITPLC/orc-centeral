from django.http import Http404
from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from orcSync.models import StationCredential
from orcSync.serializers import StationCredentialSerializer


class StationCredentialListCreateView(APIView):
    """
    API view for managing station credentials for synchronization.
    
    Provides endpoints to list and create sync configuration credentials
    for workstations.
    """

    @extend_schema(
        summary="List all station sync credentials",
        description="""Retrieve a list of all station synchronization credentials.
        
        **Use Case:**
        - View all configured sync relationships
        - Monitor which stations have sync enabled
        - Audit sync configuration
        """,
        tags=["Sync - Configuration"],
        responses={
            200: StationCredentialSerializer(many=True),
        },
    )
    def get(self, request, format=None):

        sync_configs = StationCredential.objects.all()
        serializer = StationCredentialSerializer(sync_configs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create station sync credentials",
        description="""Create new synchronization credentials for a workstation.
        
        **Process:**
        - Provide workstation location and sync details
        - API key and URL are configured
        - Enables bidirectional sync between stations
        """,
        tags=["Sync - Configuration"],
        request=StationCredentialSerializer,
        responses={
            201: StationCredentialSerializer,
            400: {"description": "Bad Request - Invalid data provided"},
        },
        examples=[
            OpenApiExample(
                "Create Sync Config Request",
                value={
                    "location": 1,
                    "url": "http://192.168.1.100:8000",
                    "api_key": "abc123def456"
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request, format=None):

        serializer = StationCredentialSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StationCredentialDetailView(APIView):
    """
    API view for managing individual station credentials.
    
    Provides endpoints to retrieve, update, and delete specific sync credentials.
    """

    def get_object(self, pk):

        try:
            return StationCredential.objects.get(pk=pk)
        except StationCredential.DoesNotExist:
            raise Http404

    @extend_schema(
        summary="Retrieve station sync credentials",
        description="Get detailed information about specific station sync credentials.",
        tags=["Sync - Configuration"],
        responses={
            200: StationCredentialSerializer,
            404: {"description": "Not Found"},
        },
    )
    def get(self, request, pk, format=None):
        sync_config = self.get_object(pk)
        serializer = StationCredentialSerializer(sync_config)
        return Response(serializer.data)

    @extend_schema(
        summary="Update station sync credentials",
        description="Partially update station synchronization credentials.",
        tags=["Sync - Configuration"],
        request=StationCredentialSerializer,
        responses={
            200: StationCredentialSerializer,
            400: {"description": "Bad Request"},
            404: {"description": "Not Found"},
        },
    )
    def patch(self, request, pk, format=None):
        sync_config = self.get_object(pk)
        serializer = StationCredentialSerializer(
            sync_config, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Delete station sync credentials",
        description="Remove synchronization credentials for a workstation.",
        tags=["Sync - Configuration"],
        responses={
            204: {"description": "Credentials successfully deleted"},
            404: {"description": "Not Found"},
        },
    )
    def delete(self, request, pk, format=None):
        sync_config = self.get_object(pk)
        sync_config.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
