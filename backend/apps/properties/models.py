import uuid

from django.db import models


class Property(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "properties_property"
        verbose_name_plural = "properties"

    def __str__(self) -> str:
        return self.name
