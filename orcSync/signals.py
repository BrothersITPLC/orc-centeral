from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from orcSync.serializers import CentralGenericModelSerializer


def create_server_change_event(instance, action):
    """
    Queues an async task to create a ChangeEvent and SyncAcknowledgements.
    This prevents blocking the main request thread.
    
    Uses transaction.on_commit() to ensure the task is only queued after
    the database transaction commits successfully.
    """
    # Skip if this is a sync operation from another workstation
    if hasattr(instance, "_is_sync_operation"):
        return

    # Serialize the instance data
    class DynamicSerializer(CentralGenericModelSerializer):
        class Meta:
            model = instance.__class__
            fields = "__all__"

    serializer = DynamicSerializer(instance)
    
    # Get model metadata
    app_label = instance._meta.app_label
    model_name = instance.__class__.__name__
    object_id = instance.pk
    data_payload = serializer.data
    
    # Queue the async task AFTER the transaction commits
    # This ensures the object exists in the DB before the task runs
    def queue_task():
        from orcSync.tasks.task import create_change_event_async
        create_change_event_async.delay(
            app_label=app_label,
            model_name=model_name,
            object_id=object_id,
            action=action,
            data_payload=data_payload,
        )
    
    transaction.on_commit(queue_task)
    
    print(
        f"SYNC_SERVER: Queued async task for '{action}' on {instance.__class__.__name__} {instance.pk}"
    )


def handle_save(sender, instance, created, **kwargs):
    """Signal handler for post_save - queues async task for create/update"""
    action = "C" if created else "U"
    create_server_change_event(instance, action)


def handle_delete(sender, instance, **kwargs):
    """Signal handler for pre_delete - queues async task for delete"""
    create_server_change_event(instance, "D")
