from rest_framework import serializers


class AcknowledgeEventsSerializer(serializers.Serializer):
    """
    Validates the list of event IDs sent by a workstation to acknowledge receipt.
    """

    acknowledged_events = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )
