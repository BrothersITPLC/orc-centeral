from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from orcSync.models import ChangeEvent, SyncAcknowledgement
from orcSync.serializers import CentralGenericModelSerializer
from workstations.models import WorkStation


def create_server_change_event(instance, action):
    """
    Creates a ChangeEvent and SyncAcknowledgements for all active workstations.
    """
    if hasattr(instance, "_is_sync_operation"):
        return

    with transaction.atomic():

        class DynamicSerializer(CentralGenericModelSerializer):
            class Meta:
                model = instance.__class__
                fields = "__all__"

        serializer = DynamicSerializer(instance)

        event = ChangeEvent.objects.create(
            content_type=ContentType.objects.get_for_model(instance.__class__),
            object_id=instance.pk,
            action=action,
            data_payload=serializer.data,
            source_workstation=None,
        )

        all_workstations = WorkStation.objects.all()
        acks_to_create = [
            SyncAcknowledgement(change_event=event, destination_workstation=ws)
            for ws in all_workstations
        ]
        if acks_to_create:
            SyncAcknowledgement.objects.bulk_create(acks_to_create)

        print(
            f"SYNC_SERVER: Logged local '{action}' for {instance.__class__.__name__} {instance.pk}"
        )


def handle_save(sender, instance, created, **kwargs):
    action = "C" if created else "U"
    create_server_change_event(instance, action)


def handle_delete(sender, instance, **kwargs):
    create_server_change_event(instance, "D")
    create_server_change_event(instance, "D")
