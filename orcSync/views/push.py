import base64
import traceback
from datetime import datetime

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from orcSync.models import ChangeEvent, SyncAcknowledgement
from orcSync.permissions import WorkstationHasAPIKey
from orcSync.serializers import InboundChangeSerializer
from workstations.models import WorkStation


class PushChangesView(APIView):
    permission_classes = [WorkstationHasAPIKey]

    def _apply_change(self, change_data: dict):
        model_label = change_data["model"]
        object_id = change_data["object_id"]
        action = change_data["action"]
        payload = change_data["data_payload"]
        Model = apps.get_model(model_label)

        if action == "D":
            Model.objects.filter(pk=object_id).delete()
            return

        file_fields, data_fields = {}, {}
        for field_name, value in payload.items():
            if not hasattr(Model, field_name) or value is None:
                continue
            field_obj = Model._meta.get_field(field_name)

            if isinstance(
                field_obj, (models.DateTimeField, models.DateField)
            ) and isinstance(value, str):
                if value.endswith("Z"):
                    value = value[:-1] + "+00:00"
                data_fields[field_name] = datetime.fromisoformat(value)
                continue

            if (
                isinstance(field_obj, models.FileField)
                and isinstance(value, dict)
                and "content" in value
            ):
                file_fields[field_name] = value
            else:
                data_fields[field_name] = value

        try:
            instance = Model.objects.get(pk=object_id)
            for attr, value in data_fields.items():
                setattr(instance, attr, value)
        except Model.DoesNotExist:
            data_fields["pk"] = object_id
            instance = Model(**data_fields)

        instance._is_sync_operation = True
        instance.save()

        if file_fields:
            for field_name, file_data in file_fields.items():
                if file_data and "filename" in file_data and "content" in file_data:
                    filename = file_data["filename"]
                    content = base64.b64decode(file_data["content"])
                    getattr(instance, field_name).save(
                        filename, ContentFile(content), save=False
                    )
                else:
                    getattr(instance, field_name).delete(save=False)
            instance.save()

    def post(self, request, *args, **kwargs):
        source_workstation = request._request.workstation
        list_serializer = InboundChangeSerializer(data=request.data, many=True)

        if not list_serializer.is_valid():
            return Response(list_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_changes = list_serializer.validated_data
        if not validated_changes:
            return Response(
                {"status": "success", "message": "No changes processed."},
                status=status.HTTP_200_OK,
            )

        try:
            with transaction.atomic():
                other_workstations = WorkStation.objects.exclude(
                    pk=source_workstation.pk
                )
                for change_data in validated_changes:
                    self._apply_change(change_data)
                    content_type = ContentType.objects.get_for_model(
                        apps.get_model(change_data["model"])
                    )

                    event = ChangeEvent.objects.create(
                        # --- THE FIX ---
                        # Explicitly cast the incoming object_id to a string to match the model field.
                        object_id=str(change_data["object_id"]),
                        content_type=content_type,
                        action=change_data["action"],
                        data_payload=change_data["data_payload"],
                        source_workstation=source_workstation,
                    )

                    acks_to_create = [
                        SyncAcknowledgement(
                            change_event=event, destination_workstation=ws
                        )
                        for ws in other_workstations
                    ]
                    if acks_to_create:
                        SyncAcknowledgement.objects.bulk_create(acks_to_create)

        except Exception as e:
            traceback.print_exc()
            return Response(
                {
                    "error": "An internal server error occurred while processing changes."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "status": "success",
                "message": f"Processed {len(validated_changes)} changes.",
            },
            status=status.HTTP_201_CREATED,
        )
