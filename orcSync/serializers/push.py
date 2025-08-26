from django.apps import apps
from rest_framework import serializers


class InboundChangeSerializer(serializers.Serializer):
    """
    Validates a single change item coming from a workstation's LocalChangeLog.
    """

    event_uuid = serializers.UUIDField()
    model = serializers.CharField(max_length=100)
    action = serializers.ChoiceField(choices=["C", "U", "D"])
    object_id = serializers.UUIDField()
    data_payload = serializers.JSONField()

    def validate_model(self, value):
        """
        Check that the model string (e.g., 'products.Product') is valid and synchronizable.
        """
        try:
            apps.get_model(value)
        except LookupError:
            raise serializers.ValidationError(
                f"Model '{value}' not found or is not allowed to be synchronized."
            )
        return value
