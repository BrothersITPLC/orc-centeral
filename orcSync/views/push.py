import base64
from datetime import datetime

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import IntegrityError, models, transaction
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
            actual_field_name = field_name.rstrip('_id') if field_name.endswith('_id') else field_name
            if not hasattr(Model, actual_field_name) or value is None:
                continue
            field_obj = Model._meta.get_field(actual_field_name)
            
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
                if field_name.endswith('_id'):
                    data_fields[field_name] = value
                else:
                    fk_fields[field_name] = value
            elif isinstance(field_obj, models.ManyToManyField):
                m2m_fields[field_name] = value
            else:
                data_fields[field_name] = value

        instance = None
        operation = None
        
        with transaction.atomic():
            instance = Model.objects.filter(pk=object_id).first()
            if not instance:
                unique_fields = [
                    f.name
                    for f in Model._meta.fields
                    if f.unique and f.name in data_fields
                ]
                filters = {f: data_fields[f] for f in unique_fields}
                if filters:
                    instance = Model.objects.filter(**filters).first()
            if not instance:
                data_fields["pk"] = object_id
                instance = Model(**data_fields)
                operation = "created"
            else:
                for key, val in data_fields.items():
                    if key != Model._meta.pk.name:
                        setattr(instance, key, val)
                operation = "updated"

            instance._is_sync_operation = True
            instance.save()

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

    def post(self, request, *args, **kwargs):
        source_workstation = request._request.workstation
        serializer = InboundChangeSerializer(data=request.data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_changes = serializer.validated_data
        if not validated_changes:
            return Response(
                {"status": "success", "message": "No changes processed."},
                status=status.HTTP_200_OK,
            )

        pending_relations = []
        results = []

        other_workstations = WorkStation.objects.exclude(pk=source_workstation.pk)

        try:
            for change_data in validated_changes:
                operation = self._apply_change(change_data, pending_relations)
                results.append(
                    (change_data["model"], change_data["object_id"], operation)
                )

                content_type = ContentType.objects.get_for_model(
                    apps.get_model(change_data["model"])
                )
                event = ChangeEvent.objects.create(
                    object_id=str(change_data["object_id"]),
                    content_type=content_type,
                    action=change_data["action"],
                    data_payload=change_data["data_payload"],
                    source_workstation=source_workstation,
                )

                acks_to_create = [
                    SyncAcknowledgement(change_event=event, destination_workstation=ws)
                    for ws in other_workstations
                ]
                if acks_to_create:
                    SyncAcknowledgement.objects.bulk_create(acks_to_create)

            self._resolve_pending_relations(pending_relations)

        except Exception:
            import traceback

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
                "details": results,
            },
            status=status.HTTP_201_CREATED,
        )
