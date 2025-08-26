from django.contrib import admin

# Register your models here.
from orcSync.models import ChangeEvent, StationCredential, SyncAcknowledgement

admin.site.register(ChangeEvent)
admin.site.register(SyncAcknowledgement)
admin.site.register(StationCredential)
