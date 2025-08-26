from django.urls import include, path
from rest_framework.routers import DefaultRouter

from orcSync.views import (
    AcknowledgeChangesView,
    GetPendingChangesView,
    PushChangesView,
    StationCredentialDetailView,
    StationCredentialListCreateView,
    WorkStationListView,
)

urlpatterns = [
    path(
        "sync-configs/",
        StationCredentialListCreateView.as_view(),
        name="sync-config-list-create",
    ),
    path(
        "sync-configs-list/",
        StationCredentialListCreateView.as_view(),
        name="sync-config-list",
    ),
    path(
        "sync-configs/<int:pk>/",
        StationCredentialDetailView.as_view(),
        name="sync-config-detail",
    ),
    path("workstation-list/", WorkStationListView.as_view(), name="workstation-list"),
    path("push/", PushChangesView.as_view(), name="push_changes"),
    path("get-pending/", GetPendingChangesView.as_view(), name="get_pending_changes"),
    path("acknowledge/", AcknowledgeChangesView.as_view(), name="acknowledge_changes"),
]
