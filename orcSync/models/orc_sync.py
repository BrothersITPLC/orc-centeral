import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from workstations.models import WorkStation


class StationCredential(models.Model):
    """
    Stores the connection details and API key for each remote workstation.
    This links a known WorkStation to its network address and secret key.
    """

    location = models.OneToOneField(
        WorkStation, related_name="sync_credential", on_delete=models.CASCADE
    )
    base_url = models.CharField(
        max_length=255,
    )
    api_key = models.CharField(
        max_length=255,
        unique=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sync Credentials for {self.location}"


# class ChangeEvent(models.Model):
#     """
#     Logs every single Create, Update, or Delete operation processed by the server.
#     This is the immutable, single source of truth for the system's history.
#     """

#     class Action(models.TextChoices):
#         CREATED = "C", "Created"
#         UPDATED = "U", "Updated"
#         DELETED = "D", "Deleted"

#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

#     content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
#     object_id = models.UUIDField()
#     changed_object = GenericForeignKey("content_type", "object_id")

#     action = models.CharField(max_length=1, choices=Action.choices)
#     timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
#     data_payload = models.JSONField(
#         help_text="A JSON snapshot of the model's data at the time of the change."
#     )

#     source_workstation = models.ForeignKey(
#         WorkStation,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name="initiated_changes",
#     )

#     class Meta:
#         ordering = ["timestamp"]

#     def __str__(self):
#         return f"{self.get_action_display()} on {self.content_type.model} at {self.timestamp}"


class ChangeEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "C", "Created"
        UPDATED = "U", "Updated"
        DELETED = "D", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)

    object_id = models.CharField(max_length=255)

    changed_object = GenericForeignKey("content_type", "object_id")
    action = models.CharField(max_length=1, choices=Action.choices)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    data_payload = models.JSONField(
        help_text="A JSON snapshot of the model's data at the time of the change."
    )
    source_workstation = models.ForeignKey(
        WorkStation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_changes",
    )

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.get_action_display()} on {self.content_type.model} at {self.timestamp}"


class SyncAcknowledgement(models.Model):
    """
    Acts as a checklist, tracking the delivery status of each ChangeEvent
    to every workstation that needs to receive it.
    """

    class Status(models.TextChoices):
        PENDING = "P", "Pending"
        ACKNOWLEDGED = "A", "Acknowledged"

    id = models.BigAutoField(primary_key=True)
    change_event = models.ForeignKey(
        ChangeEvent, on_delete=models.CASCADE, related_name="acknowledgements"
    )

    destination_workstation = models.ForeignKey(
        WorkStation, on_delete=models.CASCADE, related_name="pending_acknowledgements"
    )

    status = models.CharField(
        max_length=1, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("change_event", "destination_workstation")
        ordering = ["created_at"]

    def __str__(self):
        return f"Event {str(self.change_event.id)[:8]} for {self.destination_workstation} -> {self.get_status_display()}"
