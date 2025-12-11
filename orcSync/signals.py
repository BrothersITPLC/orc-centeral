from orcSync.serializers import CentralGenericModelSerializer


def create_server_change_event(instance, action):
    """
    Queues a ChangeEvent creation task for async processing.
    This prevents blocking the API request thread.
    """
    if hasattr(instance, "_is_sync_operation"):
        return

    # Import the async task
    from orcSync.tasks.task import create_change_event_async

    # Serialize the instance data before queuing
    class DynamicSerializer(CentralGenericModelSerializer):
        class Meta:
            model = instance.__class__
            fields = "__all__"

    serializer = DynamicSerializer(instance)

    # Queue the async task instead of processing synchronously
    create_change_event_async.delay(
        app_label=instance._meta.app_label,
        model_name=instance._meta.model_name,
        object_id=instance.pk,
        action=action,
        data_payload=serializer.data,
    )

    print(
        f"SYNC_SERVER: Queued '{action}' event for {instance.__class__.__name__} {instance.pk}"
    )


def handle_save(sender, instance, created, **kwargs):
    action = "C" if created else "U"
    create_server_change_event(instance, action)


def handle_delete(sender, instance, **kwargs):
    create_server_change_event(instance, "D")
