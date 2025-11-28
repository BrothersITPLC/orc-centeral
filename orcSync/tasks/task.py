import logging

from celery import shared_task
from django.apps import apps
from django.contrib.contenttypes.models import ContentType

logging.basicConfig(
    filename="/app/logs/celery.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


@shared_task
def run_sync_task():
    """Legacy sync task - kept for compatibility"""
    logging.info("Starting sync cycle ****************")
    try:
        from .functions.orchestrator import run_sync_cycle
        run_sync_cycle()
        logging.info("Sync cycle finished successfully")
    except Exception as e:
        logging.error("ERROR during sync cycle", exc_info=True)


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
        
        # Get the model class
        Model = apps.get_model(app_label, model_name)
        content_type = ContentType.objects.get_for_model(Model)
        
        # Create the ChangeEvent
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
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=3)
def process_pushed_changes_async(self, source_workstation_id, validated_changes):
    """
    Async task to process changes pushed from a workstation.
    This prevents blocking the push endpoint.
    
    Args:
        source_workstation_id: ID of the workstation that pushed the changes
        validated_changes: List of validated change dictionaries
    """
    try:
        from orcSync.models import ChangeEvent, SyncAcknowledgement
        from orcSync.views.push import PushChangesView
        from workstations.models import WorkStation
        
        logging.info(f"Processing {len(validated_changes)} changes from workstation {source_workstation_id}")
        
        source_workstation = WorkStation.objects.get(pk=source_workstation_id)
        other_workstations = WorkStation.objects.exclude(pk=source_workstation_id)
        
        # Create an instance of PushChangesView to reuse its methods
        view = PushChangesView()
        pending_relations = []
        results = []
        
        # First pass: create/update base objects
        for change_data in validated_changes:
            try:
                operation = view._apply_change(change_data, pending_relations)
                results.append((change_data["model"], change_data["object_id"], operation))
                
                # Create ChangeEvent for propagation to other workstations
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
                
                # Create sync acknowledgements for other workstations
                acks_to_create = [
                    SyncAcknowledgement(change_event=event, destination_workstation=ws)
                    for ws in other_workstations
                ]
                if acks_to_create:
                    SyncAcknowledgement.objects.bulk_create(acks_to_create)
                    
            except Exception as e:
                logging.error(f"Error processing change {change_data}: {e}", exc_info=True)
                # Continue processing other changes even if one fails
                continue
        
        # Second pass: resolve FK/M2M relations
        view._resolve_pending_relations(pending_relations)
        
        logging.info(f"Successfully processed {len(results)} changes from workstation {source_workstation_id}")
        return {"status": "success", "processed": len(results), "details": results}
        
    except Exception as exc:
        logging.error(f"Error processing pushed changes: {exc}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=10 * (self.request.retries + 1))
