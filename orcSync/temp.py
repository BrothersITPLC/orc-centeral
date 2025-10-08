# #orcSync/models/orc_sync.py
# ```
# import uuid

# from django.contrib.contenttypes.fields import GenericForeignKey
# from django.contrib.contenttypes.models import ContentType
# from django.db import models

# from base.models import BaseModel
# from workstations.models import WorkStation


# class StationCredential(BaseModel):
#     """
#     Stores the connection details and API key for each remote workstation.
#     This links a known WorkStation to its network address and secret key.
#     """

#     location = models.OneToOneField(
#         WorkStation, related_name="sync_credential", on_delete=models.CASCADE
#     )
#     base_url = models.CharField(
#         max_length=255,
#     )
#     api_key = models.CharField(
#         max_length=255,
#         unique=True,
#     )

#     def __str__(self):
#         return f"Sync Credentials for {self.location}"


# class ChangeEvent(models.Model):
#     class Action(models.TextChoices):
#         CREATED = "C", "Created"
#         UPDATED = "U", "Updated"
#         DELETED = "D", "Deleted"

#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)

#     object_id = models.CharField(max_length=255)

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


# class SyncAcknowledgement(models.Model):
#     """
#     Acts as a checklist, tracking the delivery status of each ChangeEvent
#     to every workstation that needs to receive it.
#     """

#     class Status(models.TextChoices):
#         PENDING = "P", "Pending"
#         ACKNOWLEDGED = "A", "Acknowledged"

#     id = models.BigAutoField(primary_key=True)
#     change_event = models.ForeignKey(
#         ChangeEvent, on_delete=models.CASCADE, related_name="acknowledgements"
#     )

#     destination_workstation = models.ForeignKey(
#         WorkStation, on_delete=models.CASCADE, related_name="pending_acknowledgements"
#     )

#     status = models.CharField(
#         max_length=1, choices=Status.choices, default=Status.PENDING, db_index=True
#     )
#     created_at = models.DateTimeField(auto_now_add=True)
#     acknowledged_at = models.DateTimeField(null=True, blank=True)

#     class Meta:
#         unique_together = ("change_event", "destination_workstation")
#         ordering = ["created_at"]

#     def __str__(self):
#         return f"Event {str(self.change_event.id)[:8]} for {self.destination_workstation} -> {self.get_status_display()}"

# ```

# #orcSync/serializers/acknowledge.py
# ```
# from rest_framework import serializers


# class AcknowledgeEventsSerializer(serializers.Serializer):
#     """
#     Validates the list of event IDs sent by a workstation to acknowledge receipt.
#     """

#     acknowledged_events = serializers.ListField(
#         child=serializers.UUIDField(), allow_empty=False
#     )

# ```

# #orcSync/serializers/generic.py
# ```
# import base64

# from django.db import models
# from django.db.models.fields.related import ManyToManyField
# from rest_framework import serializers


# class CentralGenericModelSerializer(serializers.ModelSerializer):
#     """
#     A dynamic serializer for the central server to capture its own changes.
#     Correctly handles special types and now skips ManyToManyFields.
#     """

#     def to_representation(self, instance):
#         ret = {}
#         fields = instance._meta.get_fields()
#         for field in fields:
#             if isinstance(
#                 field,
#                 (
#                     models.ManyToOneRel,
#                     models.ManyToManyRel,
#                     models.OneToOneRel,
#                     ManyToManyField,
#                 ),
#             ):
#                 continue

#             value = getattr(instance, field.name)
#             if value is None:
#                 ret[field.name] = None
#                 continue
#             if isinstance(field, (models.DateTimeField, models.DateField)):
#                 ret[field.name] = value.isoformat()
#             elif isinstance(field, models.DecimalField):
#                 ret[field.name] = str(value)
#             elif isinstance(field, models.UUIDField):
#                 ret[field.name] = str(value)
#             elif isinstance(field, models.FileField):
#                 if value:
#                     try:
#                         with value.open("rb") as f:
#                             encoded_string = base64.b64encode(f.read()).decode("utf-8")
#                         ret[field.name] = {
#                             "filename": value.name.split("/")[-1],
#                             "content": encoded_string,
#                         }
#                     except (IOError, FileNotFoundError):
#                         ret[field.name] = None
#                 else:
#                     ret[field.name] = None
#             elif isinstance(field, models.ForeignKey):
#                 related_obj = value
#                 ret[field.attname] = str(related_obj.pk) if related_obj else None
#             else:
#                 ret[field.name] = value
#         return ret

#     class Meta:
#         pass

# ```

# #orcSync/serializers/get_pending.py
# ```
# from django.apps import apps
# from django.contrib.contenttypes.models import ContentType
# from django.db import transaction
# from rest_framework import serializers

# from orcSync.models import ChangeEvent


# class OutboundChangeSerializer(serializers.ModelSerializer):
#     """
#     Formats a ChangeEvent record to be sent down to a workstation.
#     """

#     model = serializers.CharField(source="content_type.model_class_label")

#     class Meta:
#         model = ChangeEvent
#         fields = ("id", "model", "action", "object_id", "data_payload", "timestamp")


# class PendingDataSerializer(serializers.Serializer):
#     """
#     The top-level serializer for the response of the get-pending endpoint.
#     """

#     pending_changes = OutboundChangeSerializer(many=True)
#     acknowledged_events = serializers.ListField(child=serializers.UUIDField())

# ```

# #orcSync/serializers/outbound_change.py
# ```
# import decimal
# import uuid

# from django.db import models
# from django.db.models.fields.related import ManyToManyField
# from rest_framework import serializers

# from orcSync.models import ChangeEvent


# class OutboundChangeSerializer(serializers.ModelSerializer):
#     """
#     Formats a ChangeEvent record to be sent down to a workstation.
#     This version is compatible with older Django versions and correctly skips ManyToManyFields.
#     """

#     model = serializers.SerializerMethodField()
#     data_payload = serializers.SerializerMethodField()

#     class Meta:
#         model = ChangeEvent
#         fields = ("id", "model", "action", "object_id", "data_payload", "timestamp")

#     def get_model(self, obj):
#         model_class = obj.content_type.model_class()
#         if not model_class:
#             return f"{obj.content_type.app_label}.{obj.content_type.model.capitalize()}"
#         return f"{obj.content_type.app_label}.{model_class.__name__}"

#     def get_data_payload(self, obj):
#         if obj.action == "D" or not obj.changed_object:
#             return obj.data_payload

#         instance = obj.changed_object
#         payload = {}
#         for field in instance._meta.get_fields():
#             if isinstance(
#                 field,
#                 (
#                     models.ManyToOneRel,
#                     models.ManyToManyRel,
#                     models.OneToOneRel,
#                     ManyToManyField,
#                 ),
#             ):
#                 continue

#             if isinstance(field, models.FileField):
#                 file_val = getattr(instance, field.name)
#                 if file_val and hasattr(file_val, "url"):
#                     payload[field.name] = self.context["request"].build_absolute_uri(
#                         file_val.url
#                     )
#                 else:
#                     payload[field.name] = None
#             elif isinstance(field, models.ForeignKey):
#                 related_obj = getattr(instance, field.name)
#                 payload[field.attname] = str(related_obj.pk) if related_obj else None
#             else:
#                 value = getattr(instance, field.name)
#                 if isinstance(value, (decimal.Decimal, uuid.UUID)):
#                     payload[field.name] = str(value)
#                 elif hasattr(value, "isoformat"):
#                     payload[field.name] = value.isoformat()
#                 else:
#                     payload[field.name] = value
#         return payload

# ```
# #orcSync/serializers/push.py
# ```
# from django.apps import apps
# from rest_framework import serializers


# class InboundChangeSerializer(serializers.Serializer):
#     """
#     Validates a single change item coming from a workstation's LocalChangeLog.
#     """

#     event_uuid = serializers.UUIDField()
#     model = serializers.CharField(max_length=100)
#     action = serializers.ChoiceField(choices=["C", "U", "D"])

#     object_id = serializers.CharField(max_length=255)

#     data_payload = serializers.JSONField()

#     def validate_model(self, value):
#         try:
#             apps.get_model(value)
#         except LookupError:
#             raise serializers.ValidationError(
#                 f"Model '{value}' not found or is not allowed to be synchronized."
#             )
#         return value

# ```
# #orcSync/serializers/sync_address.py
# ```
# from rest_framework import serializers

# from orcSync.models import StationCredential
# from workstations.models import WorkStation


# class WorkStationSerializer(serializers.ModelSerializer):

#     class Meta:
#         model = WorkStation
#         fields = ["id", "name"]


# class StationCredentialSerializer(serializers.ModelSerializer):
#     location = WorkStationSerializer(read_only=True)
#     location_id = serializers.PrimaryKeyRelatedField(
#         queryset=WorkStation.objects.all(), source="location", write_only=True
#     )

#     class Meta:
#         model = StationCredential
#         fields = [
#             "id",
#             "location",
#             "location_id",
#             "base_url",
#             "api_key",
#             "created_at",
#             "updated_at",
#         ]
#         extra_kwargs = {"api_key": {"write_only": True}}

# ```

# #orcSync/tasks/task.py
# ```
# import logging

# from celery import shared_task

# from .functions.orchestrator import run_sync_cycle

# logging.basicConfig(
#     filename="/app/logs/celery.log",
#     level=logging.INFO,
#     format="%(asctime)s - %(levelname)s - %(message)s",
# )


# @shared_task
# def run_sync_task():
#     logging.info("Starting sync cycle ****************")
#     try:
#         run_sync_cycle()
#         logging.info("Sync cycle finished successfully")
#     except Exception as e:
#         logging.error("ERROR during sync cycle", exc_info=True)

# ```

# #orcSync/views/acknowledge.py
# ```

# ```
# #orcSync/views/generic.py
# ```

# ```
# #orcSync/views/get_pending.py
# ```

# ```
# #orcSync/views/outbound_change.py
# ```

# ```
# #orcSync/views/push.py
# ```

# ```
# #orcSync/views/sync_address.py
# ```

# ```


# #orcSync/apps.py
# ```

# from django.apps import AppConfig
# from django.conf import settings
# from django.db.models.signals import post_save, pre_delete


# class OrcsyncConfig(AppConfig):
#     default_auto_field = "django.db.models.BigAutoField"
#     name = "orcSync"

#     def ready(self):
#         from django.apps import apps

#         from .signals import handle_delete, handle_save

#         model_strings = getattr(settings, "SYNCHRONIZABLE_MODELS", [])
#         for model_string in model_strings:
#             try:
#                 model = apps.get_model(model_string)
#                 post_save.connect(
#                     handle_save,
#                     sender=model,
#                     dispatch_uid=f"central_sync_save_{model._meta.label}",
#                 )
#                 pre_delete.connect(
#                     handle_delete,
#                     sender=model,
#                     dispatch_uid=f"central_sync_delete_{model._meta.label}",
#                 )
#                 print(f"SYNC_SERVER: Signals connected for model {model_string}")
#             except LookupError:
#                 print(f"SYNC_SERVER WARNING: Model '{model_string}' not found.")
#                 print(f"SYNC_SERVER WARNING: Model '{model_string}' not found.")

# ```
# #orcSync/permissions.py
# ```
# from rest_framework.permissions import BasePermission

# from .models import StationCredential


# class WorkstationHasAPIKey(BasePermission):
#     """
#     A single, custom permission class that validates the API Key
#     by looking it up directly in the StationCredential model.
#     """

#     message = "Invalid or missing API Key."

#     def has_permission(self, request, view):
#         header = request.META.get("HTTP_AUTHORIZATION")
#         print(header, " it is header")
#         if not header or not header.lower().startswith("api-key "):
#             return False

#         try:
#             _, key = header.split()
#         except ValueError:
#             return False

#         try:
#             credential = StationCredential.objects.select_related("location").get(
#                 api_key=key
#             )
#             workstation = credential.location
#             request._request.workstation = workstation

#             return True
#         except StationCredential.DoesNotExist:
#             return False

# ```
# #orcSync/signals.py
# ```
# from django.contrib.contenttypes.models import ContentType
# from django.db import transaction

# from orcSync.models import ChangeEvent, SyncAcknowledgement
# from orcSync.serializers import CentralGenericModelSerializer
# from workstations.models import WorkStation


# def create_server_change_event(instance, action):
#     """
#     Creates a ChangeEvent and SyncAcknowledgements for all active workstations.
#     """
#     if hasattr(instance, "_is_sync_operation"):
#         return

#     with transaction.atomic():

#         class DynamicSerializer(CentralGenericModelSerializer):
#             class Meta:
#                 model = instance.__class__
#                 fields = "__all__"

#         serializer = DynamicSerializer(instance)

#         event = ChangeEvent.objects.create(
#             content_type=ContentType.objects.get_for_model(instance.__class__),
#             object_id=instance.pk,
#             action=action,
#             data_payload=serializer.data,
#             source_workstation=None,
#         )

#         all_workstations = WorkStation.objects.all()
#         acks_to_create = [
#             SyncAcknowledgement(change_event=event, destination_workstation=ws)
#             for ws in all_workstations
#         ]
#         if acks_to_create:
#             SyncAcknowledgement.objects.bulk_create(acks_to_create)

#         print(
#             f"SYNC_SERVER: Logged local '{action}' for {instance.__class__.__name__} {instance.pk}"
#         )


# def handle_save(sender, instance, created, **kwargs):
#     action = "C" if created else "U"
#     create_server_change_event(instance, action)


# def handle_delete(sender, instance, **kwargs):
#     create_server_change_event(instance, "D")
#     create_server_change_event(instance, "D")

# ```

# #orcSync/urls.py
# ```
# from django.urls import include, path
# from rest_framework.routers import DefaultRouter

# from orcSync.views import (
#     AcknowledgeChangesView,
#     GetPendingChangesView,
#     PushChangesView,
#     StationCredentialDetailView,
#     StationCredentialListCreateView,
#     WorkStationListView,
# )

# urlpatterns = [
#     path(
#         "sync-configs/",
#         StationCredentialListCreateView.as_view(),
#         name="sync-config-list-create",
#     ),
#     path(
#         "sync-configs-list/",
#         StationCredentialListCreateView.as_view(),
#         name="sync-config-list",
#     ),
#     path(
#         "sync-configs/<int:pk>/",
#         StationCredentialDetailView.as_view(),
#         name="sync-config-detail",
#     ),
#     path("workstation-list/", WorkStationListView.as_view(), name="workstation-list"),
#     path("push/", PushChangesView.as_view(), name="push_changes"),
#     path("get-pending/", GetPendingChangesView.as_view(), name="get_pending_changes"),
#     path("acknowledge/", AcknowledgeChangesView.as_view(), name="acknowledge_changes"),
# ]

# ```

# #InsaBackednLatest/settings.py

# ```
# import os
# from datetime import timedelta
# from pathlib import Path  # Ensure this import exists

# from dotenv import load_dotenv

# # Load environment variables from .env file
# load_dotenv()

# # Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR = Path(__file__).resolve().parent.parent

# # SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
# # SECURITY WARNING: don't run with debug turned on in production!
# # DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "False"
# DEBUG = True
# ROOT_URLCONF = "InsaBackednLatest.urls"
# # Internationalization
# LANGUAGE_CODE = "en-us"
# TIME_ZONE = "UTC"
# USE_I18N = True
# USE_TZ = True
# # Internationalization
# LANGUAGE_CODE = "en-us"
# TIME_ZONE = "UTC"
# USE_I18N = True
# USE_TZ = True
# ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
# ALLOWED_HOSTS.append("localhost")
# ALLOWED_HOSTS.append("127.0.0.1")
# ALLOWED_HOSTS.append("0.0.0.0")
# ALLOWED_HOSTS.append("localhost:8010")
# ALLOWED_HOSTS.append("192.168.10.42")
# ALLOWED_HOSTS.append("host.docker.internal")
# TEMPLATES = [
#     {
#         "BACKEND": "django.template.backends.django.DjangoTemplates",
#         "DIRS": [os.path.join(BASE_DIR, "templates")],
#         "APP_DIRS": True,
#         "OPTIONS": {
#             "context_processors": [
#                 "django.template.context_processors.debug",
#                 "django.template.context_processors.request",
#                 "django.contrib.auth.context_processors.auth",
#                 "django.contrib.messages.context_processors.messages",
#             ],
#         },
#     },
# ]


# # Custom user model
# AUTH_USER_MODEL = "users.CustomUser"
# AUTHENTICATION_BACKENDS = [
#     "django.contrib.auth.backends.ModelBackend",
# ]

# # Database
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.environ.get("POSTGRES_DB"),
#         "USER": os.environ.get("POSTGRES_USER"),
#         "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
#         "HOST": os.environ.get("POSTGRES_HOST"),
#         "PORT": os.environ.get("POSTGRES_PORT"),
#     },
#     "central": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.environ.get("POSTGRES_DB"),
#         "USER": os.environ.get("POSTGRES_USER"),
#         "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
#         "HOST": "local_postgres",
#         "PORT": 5432,
#     },
# }


# # Email settings
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = "smtp.gmail.com"
# EMAIL_PORT = os.environ.get("EMAIL_PORT")
# EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
# EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
# EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
# WSGI_APPLICATION = "InsaBackednLatest.wsgi.application"
# CORS_ALLOW_CREDENTIALS = os.environ.get("CORS_ALLOW_CREDENTIALS") == "True"
# CORS_ALLOW_HEADERS = os.environ.get("CORS_ALLOW_HEADERS", "").split(",")

# CORS_ALLOW_METHODS = os.environ.get("CORS_ALLOW_METHODS", "").split(",")


# # JWT settings
# SIMPLE_JWT = {
#     "ACCESS_TOKEN_LIFETIME": timedelta(
#         minutes=int(os.environ.get("JWT_ACCESS_TOKEN_LIFETIME", "15"))
#     ),
#     "REFRESH_TOKEN_LIFETIME": timedelta(
#         days=int(os.environ.get("JWT_REFRESH_TOKEN_LIFETIME", "1"))
#     ),
#     "SIGNING_KEY": SECRET_KEY,
#     "VERIFYING_KEY": os.environ.get("JWT_VERIFYING_KEY", SECRET_KEY),
#     "AUTH_HEADER_TYPES": ("Bearer",),
# }

# INSTALLED_APPS = [
#     "django.contrib.admin",
#     "django.contrib.auth",
#     "django.contrib.contenttypes",
#     "django.contrib.sessions",
#     "django.contrib.messages",
#     "django.contrib.staticfiles",
#     "rest_framework",
#     "rest_framework_api_key",
#     "rest_framework.authtoken",
#     "django_filters",
#     "corsheaders",
#     "auditlog",
#     # Moved to correct position
#     "users",
#     "address",
#     "drivers",
#     "workstations",
#     "trucks",
#     "declaracions",
#     "exporters",
#     "tax",
#     "analysis",
#     "drf_yasg",
#     "django_pandas",
#     "core",
#     "localcheckings",
#     "audit",
#     "path",
#     "news",
#     "api",
#     "orcSync",
# ]

# MIDDLEWARE = [
#     "corsheaders.middleware.CorsMiddleware",
#     "django.middleware.security.SecurityMiddleware",
#     "django.contrib.sessions.middleware.SessionMiddleware",
#     "django.middleware.common.CommonMiddleware",
#     "django.middleware.csrf.CsrfViewMiddleware",
#     "django.contrib.auth.middleware.AuthenticationMiddleware",
#     "django.contrib.messages.middleware.MessageMiddleware",
#     "django.middleware.clickjacking.XFrameOptionsMiddleware",
#     "common.middleware.AttachJWTTokenMiddleware",
#     "common.middleware.RefreshTokenMiddleware",
#     "common.middleware.DisplayCurrentUserMiddleware",
# ]
# # External APIs and Tokens
# DERASH_API_KEY = os.environ.get("DERASH_API_KEY")
# DERASH_SECRET_KEY = os.environ.get("DERASH_SECRET_KEY")
# DERASH_END_POINT = os.environ.get("DERASH_END_POINT")
# WEIGHTBRIDGE_TOKEN = os.environ.get("WEIGHTBRIDGE_TOKEN")
# EXTERNAL_URI_WEIGHT_BRIDGE = os.environ.get("EXTERNAL_URI_WEIGHT_BRIDGE")
# STATIC_URL = "/static/"
# # CORS and CSRF settings
# CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
# CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")

# # Media settings
# MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/app/media")
# MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")

# STATIC_ROOT = BASE_DIR / "staticfiles"

# STATICFILES_DIRS = [
#     BASE_DIR / "static",
# ]


# SYNCHRONIZABLE_MODELS = [
#     "drivers.Driver",
#     "workstations.WorkStation",
#     "workstations.WorkedAt",
#     "trucks.TruckOwner",
#     "trucks.Truck",
#     "exporters.TaxPayerType",
#     "exporters.Exporter",
#     "tax.Tax",
#     "users.Report",
#     "users.UserStatus",
#     "users.CustomUser",
#     "users.Department",
# ]
# ```
