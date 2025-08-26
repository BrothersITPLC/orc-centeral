import decimal
import uuid

from django.db import models
from django.db.models.fields.related import ManyToManyField
from rest_framework import serializers

from orcSync.models import ChangeEvent


class OutboundChangeSerializer(serializers.ModelSerializer):
    """
    Formats a ChangeEvent record to be sent down to a workstation.
    This version is compatible with older Django versions and correctly skips ManyToManyFields.
    """

    model = serializers.SerializerMethodField()
    data_payload = serializers.SerializerMethodField()

    class Meta:
        model = ChangeEvent
        fields = ("id", "model", "action", "object_id", "data_payload", "timestamp")

    def get_model(self, obj):
        model_class = obj.content_type.model_class()
        if not model_class:
            return f"{obj.content_type.app_label}.{obj.content_type.model.capitalize()}"
        return f"{obj.content_type.app_label}.{model_class.__name__}"

    def get_data_payload(self, obj):
        if obj.action == "D" or not obj.changed_object:
            return obj.data_payload

        instance = obj.changed_object
        payload = {}
        for field in instance._meta.get_fields():
            if isinstance(
                field,
                (
                    models.ManyToOneRel,
                    models.ManyToManyRel,
                    models.OneToOneRel,
                    ManyToManyField,
                ),
            ):
                continue

            if isinstance(field, models.FileField):
                file_val = getattr(instance, field.name)
                if file_val and hasattr(file_val, "url"):
                    payload[field.name] = self.context["request"].build_absolute_uri(
                        file_val.url
                    )
                else:
                    payload[field.name] = None
            elif isinstance(field, models.ForeignKey):
                related_obj = getattr(instance, field.name)
                payload[field.attname] = str(related_obj.pk) if related_obj else None
            else:
                value = getattr(instance, field.name)
                if isinstance(value, (decimal.Decimal, uuid.UUID)):
                    payload[field.name] = str(value)
                elif hasattr(value, "isoformat"):
                    payload[field.name] = value.isoformat()
                else:
                    payload[field.name] = value
        return payload
