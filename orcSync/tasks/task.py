import logging

from celery import shared_task
from django.apps import apps
from django.contrib.contenttypes.models import ContentType

logging.basicConfig(
    filename="/app/logs/celery.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


@shared_task(bind=True, max_retries=3)
def create_change_event_async(self, app_label, model_name, object_id, action, data_payload):
    """
    Async task to create ChangeEvent and SyncAcknowledgements in background.
    This prevents blocking the main API request thread.
    
    Args:
        app_label: App label of the model (e.g., 'drivers')
        model_name: Model name (e.g., 'Driver')
        object_id: Primary key of the changed object
        action: Action type ('C', 'U', or 'D')
        data_payload: Serialized data of the object
    """
    try:
        from orcSync.models import ChangeEvent, SyncAcknowledgement
        from workstations.models import WorkStation
        
        logging.info(f"Creating ChangeEvent for {app_label}.{model_name} {object_id} - {action}")
        
        Model = apps.get_model(app_label, model_name)
        content_type = ContentType.objects.get_for_model(Model)
        
        event = ChangeEvent.objects.create(
            content_type=content_type,
            object_id=str(object_id),
            action=action,
            data_payload=data_payload,
            source_workstation=None,  
        )
        
        all_workstations = WorkStation.objects.all()
        acks_to_create = [
            SyncAcknowledgement(change_event=event, destination_workstation=ws)
            for ws in all_workstations
        ]
        
        if acks_to_create:
            SyncAcknowledgement.objects.bulk_create(acks_to_create)
            logging.info(f"Created {len(acks_to_create)} SyncAcknowledgements for event {event.id}")
        
        logging.info(f"Successfully created ChangeEvent {event.id}")
        
    except Exception as exc:
        logging.error(f"Error creating ChangeEvent: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))