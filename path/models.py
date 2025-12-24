from django.db import models
from django.db.models import F, Max, Q

from base.models import BaseModel
from workstations.models import WorkStation


class Path(BaseModel):
    name = models.CharField(max_length=100, null=True)
    created_by = models.ForeignKey(
        "users.CustomUser", on_delete=models.RESTRICT, related_name="path_created_by"
    )
    def __str__(self):
        return self.name


class PathStation(BaseModel):
    path = models.ForeignKey(
        Path, on_delete=models.CASCADE, related_name="path_stations"
    )
    station = models.ForeignKey(
        WorkStation, on_delete=models.RESTRICT, related_name="path_station"
    )
    order = models.PositiveBigIntegerField()
    class Meta:
        unique_together = (("path", "station"), ("path", "order"))
    def save(self, *args, **kwargs):
        if (
            not self.order
        ): 
            max_order = PathStation.objects.filter(path=self.path).aggregate(
                Max("order")
            )["order__max"]
            self.order = (max_order or 0) + 1  

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.path.name} - {self.station.name} (Sequence: {self.sequence})"
