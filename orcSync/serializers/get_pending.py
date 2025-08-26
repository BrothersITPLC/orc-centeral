from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from rest_framework import serializers

from orcSync.models import ChangeEvent


class OutboundChangeSerializer(serializers.ModelSerializer):
    """
    Formats a ChangeEvent record to be sent down to a workstation.
    """

    model = serializers.CharField(source="content_type.model_class_label")

    class Meta:
        model = ChangeEvent
        fields = ("id", "model", "action", "object_id", "data_payload", "timestamp")


class PendingDataSerializer(serializers.Serializer):
    """
    The top-level serializer for the response of the get-pending endpoint.
    """

    pending_changes = OutboundChangeSerializer(many=True)
    acknowledged_events = serializers.ListField(child=serializers.UUIDField())
