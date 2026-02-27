import uuid

import pytest

from apps.properties.models import Property


@pytest.mark.django_db
class TestPropertyModel:
    def test_create_property(self):
        prop = Property.objects.create(name="Storgata 15, Oslo")
        assert prop.name == "Storgata 15, Oslo"
        assert isinstance(prop.id, uuid.UUID)

    def test_str_returns_name(self):
        prop = Property(name="Karl Johans gate 1")
        assert str(prop) == "Karl Johans gate 1"

    def test_property_with_address(self):
        prop = Property.objects.create(
            name="Bygård Sentrum",
            address="Grensen 10, 0159 Oslo",
        )
        assert prop.address == "Grensen 10, 0159 Oslo"
