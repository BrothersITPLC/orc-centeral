import base64
from datetime import datetime

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from orcSync.models import ChangeEvent, SyncAcknowledgement
from orcSync.permissions import WorkstationHasAPIKey
from orcSync.serializers import InboundChangeSerializer
from workstations.models import WorkStation


class PushChangesView(APIView):
    """
    API view for workstations to push data changes to the central server.
    
    Handles incoming change events from workstations, applies them to the database,
    and propagates them to other workstations for synchronization.
    """
    
    permission_classes = [WorkstationHasAPIKey]

    def _apply_change(self, change_data: dict, pending_relations: list):
        model_label = change_data["model"]
        object_id = change_data["object_id"]
        action = change_data["action"]
        payload = change_data["data_payload"]
        Model = apps.get_model(model_label)
        if action == "D":
            Model.objects.filter(pk=object_id).delete()
            return "deleted"

        file_fields, data_fields, fk_fields, m2m_fields = {}, {}, {}, {}

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
            elif (
                isinstance(field_obj, models.FileField)
                and isinstance(value, dict)
                and "content" in value
            ):
                file_fields[field_name] = value
            elif isinstance(field_obj, models.ForeignKey):
                fk_fields[field_name] = value
            elif isinstance(field_obj, models.ManyToManyField):
                m2m_fields[field_name] = value
            else:
                data_fields[field_name] = value

        instance = None
        operation = None

        # ------------------------------
        # Start atomic block for this object
        # ------------------------------
        with transaction.atomic():
            # 1️⃣ Try to get by PK first
            instance = Model.objects.filter(pk=object_id).first()

            # 2️⃣ If not found, try to get by unique fields to avoid duplicates
            if not instance:
                unique_fields = [
                    f.name
                    for f in Model._meta.fields
                    if f.unique and f.name in data_fields
                ]
                filters = {f: data_fields[f] for f in unique_fields}
                if filters:
                    instance = Model.objects.filter(**filters).first()

            # 3️⃣ Create new if still not found
            if not instance:
                data_fields["pk"] = object_id
                instance = Model(**data_fields)
                operation = "created"
            else:
                # Update existing
                for key, val in data_fields.items():
                    if key != Model._meta.pk.name:
                        setattr(instance, key, val)
                operation = "updated"

            instance._is_sync_operation = True
            instance.save()

        # Handle files after saving
        for field_name, file_data in file_fields.items():
            if file_data and "filename" in file_data and "content" in file_data:
                filename = file_data["filename"]
                content = base64.b64decode(file_data["content"])
                getattr(instance, field_name).save(
                    filename, ContentFile(content), save=False
                )
            else:
                current_file = getattr(instance, field_name)
                if current_file:
                    current_file.delete(save=False)
        instance.save()

        if fk_fields or m2m_fields:
            pending_relations.append((instance, fk_fields, m2m_fields))

        return operation

    def _resolve_pending_relations(self, pending_relations):
        for instance, fk_fields, m2m_fields in pending_relations:
            for field_name, related_id in fk_fields.items():
                field = instance._meta.get_field(field_name)
                RelatedModel = field.remote_field.model
                try:
                    related_instance = RelatedModel.objects.get(pk=related_id)
                    setattr(instance, field_name, related_instance)
                except RelatedModel.DoesNotExist:
                    continue
            instance.save()

            for field_name, related_ids in m2m_fields.items():
                field = getattr(instance, field_name)
                RelatedModel = field.model
                related_instances = RelatedModel.objects.filter(pk__in=related_ids)
                field.set(related_instances)


    @extend_schema(
        summary="Push changes from workstation to central server",
        description="""Push data changes from a workstation to the central server for synchronization.
        
        **Authentication:**
        - Requires workstation API key authentication
        
        **Process:**
        1. Validates incoming change events
        2. Queues changes for background processing
        3. Returns immediately with 202 Accepted
        4. Changes are processed asynchronously by Celery worker
        5. Creates ChangeEvent records for propagation
        6. Generates SyncAcknowledgement records for other workstations
        
        **Important:**
        - This endpoint returns **202 Accepted** immediately
        - Changes are processed in the background
        - Use `/get-pending/` to confirm changes have propagated
        - Check `acknowledged_events` array in `/get-pending/` response
        
        **Change Actions:**
        - `C`: Create new record
        - `U`: Update existing record
        - `D`: Delete record
        
        **Features:**
        - Async processing prevents request blocking
        - Atomic transactions per object
        - Duplicate prevention using unique fields
        - Two-pass processing (base objects, then relations)
        - File handling with base64 encoding
        - Automatic propagation to other workstations
        - Automatic retry on failure (up to 3 times)
        
        **Request Format:**
        Array of change objects, each containing:
        - `model`: Model label (e.g., "drivers.Driver")
        - `object_id`: Primary key of the object
        - `action`: Action type (C/U/D)
        - `data_payload`: Object data including relationships
        """,
        tags=["Sync - Data Transfer"],
        request=InboundChangeSerializer(many=True),
        responses={
            202: {
                "description": "Changes accepted for processing",
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "message": {"type": "string"},
                    "task_id": {"type": "string"},
                    "info": {"type": "string"}
                }
            },
            400: {"description": "Bad Request - Invalid change data"},
            401: {"description": "Unauthorized - Invalid API key"},
        },
        examples=[
            OpenApiExample(
                "Push Changes Request",
                value=[
                    {
                        "model": "drivers.Driver",
                        "object_id": 123,
                        "action": "U",
                        "data_payload": {
                            "first_name": "Abebe",
                            "last_name": "Tadesse",
                            "license_number": "ET-12345",
                            "phone_number": "+251911234567"
                        }
                    },
                    {
                        "model": "trucks.Truck",
                        "object_id": 456,
                        "action": "C",
                        "data_payload": {
                            "plate_number": "AA-12345",
                            "chassis_number": "CH123456",
                            "owner": 789
                        }
                    }
                ],
                request_only=True,
            ),
            OpenApiExample(
                "Accepted Response",
                value={
                    "status": "accepted",
                    "message": "Accepted 2 changes for processing.",
                    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "info": "Changes are being processed in the background. Check /get-pending/ for confirmation."
                },
                response_only=True,
                status_codes=["202"],
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        source_workstation = request._request.workstation
        serializer = InboundChangeSerializer(data=request.data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_changes = serializer.validated_data
        if not validated_changes:
            return Response(
                {"status": "success", "message": "No changes to process."},
                status=status.HTTP_200_OK,
            )

        # Queue async task to process changes in background
        from orcSync.tasks.task import process_pushed_changes_async
        
        task = process_pushed_changes_async.delay(
            source_workstation_id=source_workstation.pk,
            validated_changes=validated_changes,
        )

        return Response(
            {
                "status": "accepted",
                "message": f"Accepted {len(validated_changes)} changes for processing.",
                "task_id": task.id,
                "info": "Changes are being processed in the background. Check /get-pending/ for confirmation.",
            },
            status=status.HTTP_202_ACCEPTED,
        )

