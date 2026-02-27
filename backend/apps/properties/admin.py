from django.contrib import admin

from .models import Property


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "address", "created_at"]
    search_fields = ["name", "address"]
