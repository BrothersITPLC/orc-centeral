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
    """
    Receives a batch of changes from a workstation, applies them, records them,
    and creates acknowledgement tasks for all other workstations.
    """

    permission_classes = [WorkstationHasAPIKey]

    def _apply_change(self, change_data: dict):
        """
        Helper function to apply a single change to the central database.
        This version correctly handles deserialization of date strings.
        """
        model_label = change_data["model"]
        object_id = change_data["object_id"]
        action = change_data["action"]
        payload = change_data["data_payload"]

        Model = apps.get_model(model_label)

        print(f"--- APPLY_CHANGE: Action={action}, Model={model_label}, ID={object_id}")

        if action == "D":
            deleted_count, _ = Model.objects.filter(pk=object_id).delete()
            print(f"--- APPLY_CHANGE: Deleted {deleted_count} object(s).")
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
            print("--- APPLY_CHANGE: Found existing instance. Updating fields.")
            for attr, value in data_fields.items():
                setattr(instance, attr, value)
        except Model.DoesNotExist:
            print("--- APPLY_CHANGE: Instance not found, creating new one.")
            data_fields["pk"] = object_id
            instance = Model(**data_fields)

        instance._is_sync_operation = True
        instance.save()
        print(f"--- APPLY_CHANGE: Instance explicitly saved.")

        if file_fields:
            instance.save()
            print(f"--- APPLY_CHANGE: Instance saved again after file operations.")

    def post(self, request, *args, **kwargs):
        source_workstation = request._request.workstation
        print(f"\n--- SYNC PUSH: Received push from {source_workstation.name} ---")

        list_serializer = InboundChangeSerializer(data=request.data, many=True)

        if not list_serializer.is_valid():
            print("--- SYNC PUSH: FAILED - Invalid data format ---")
            print(list_serializer.errors)
            return Response(list_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_changes = list_serializer.validated_data
        if not validated_changes:
            print(
                "--- SYNC PUSH: WARNING - Request was valid but contained no data. ---"
            )
            return Response(
                {"status": "success", "message": "No changes processed."},
                status=status.HTTP_200_OK,
            )

        print(
            f"--- SYNC PUSH: Data is valid. Processing {len(validated_changes)} changes. ---"
        )

        try:
            with transaction.atomic():
                other_workstations = WorkStation.objects.exclude(
                    pk=source_workstation.pk
                )

                for change_data in validated_changes:
                    print(
                        f"--- SYNC PUSH: Applying change for model {change_data['model']}, ID {change_data['object_id']} ---"
                    )

                    self._apply_change(change_data)

                    print(
                        f"--- SYNC PUSH: Change applied successfully. Logging event... ---"
                    )

                    content_type = ContentType.objects.get_for_model(
                        apps.get_model(change_data["model"])
                    )

                    event = ChangeEvent.objects.create(
                        object_id=change_data["object_id"],
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

                    print(f"--- SYNC PUSH: Event logged successfully. ---")

        except Exception as e:
            print(f"--- SYNC PUSH: FAILED - Exception inside transaction block! ---")
            traceback.print_exc()
            return Response(
                {
                    "error": "An internal server error occurred while processing changes."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        print("--- SYNC PUSH: Transaction committed successfully. ---")
        return Response(
            {
                "status": "success",
                "message": f"Processed {len(validated_changes)} changes.",
            },
            status=status.HTTP_201_CREATED,
        )
