from django.core.management.base import BaseCommand
from django.db import transaction

from apps.messaging.models import (
    Conversation,
    ConversationParticipant,
    Delegation,
    Message,
    ReadState,
)
from apps.properties.models import Property
from apps.users.models import User


class Command(BaseCommand):
    help = "Seed development data for messaging"

    @transaction.atomic
    def handle(self, *args, **options):
        if Conversation.objects.exists():
            self.stdout.write("Data already exists, skipping seed.")
            return

        tenant = self._create_user("leietaker@hybel.no", "Ola", "Hansen")
        landlord = self._create_user("utleier@hybel.no", "Kari", "Nilsen")
        manager = self._create_user("forvalter@hybel.no", "Per", "Berg")
        contractor = self._create_user("handverker@hybel.no", "Erik", "Olsen")

        prop1 = Property.objects.create(name="Storgata 15, Oslo", address="Storgata 15, 0184 Oslo")
        prop2 = Property.objects.create(
            name="Parkveien 7, Bergen", address="Parkveien 7, 5007 Bergen"
        )

        conv1 = self._create_conversation(
            prop=prop1,
            subject="Vannlekkasje på badet",
            conv_type="maintenance",
            participants=[
                (tenant, "tenant", "tenant_side"),
                (landlord, "landlord", "landlord_side"),
                (manager, "property_manager", "landlord_side"),
            ],
        )

        Message.objects.create(
            conversation=conv1,
            sender=tenant,
            content="Hei, det lekker vann fra taket på badet. Kan noen ta en titt?",
        )
        Message.objects.create(
            conversation=conv1,
            sender=landlord,
            content="Hei Ola, vi sender en rørlegger i morgen tidlig.",
        )
        Message.objects.create(
            conversation=conv1,
            sender=manager,
            content="Rørlegger koster ca 5000kr. Dekkes av forsikringen.",
            message_type="internal_comment",
            is_internal=True,
        )

        Delegation.objects.create(
            conversation=conv1,
            assigned_to=manager,
            assigned_by=landlord,
            note="Følg opp med rørlegger",
        )

        conv2 = self._create_conversation(
            prop=prop2,
            subject="Spørsmål om leiekontrakt",
            conv_type="lease",
            participants=[
                (tenant, "tenant", "tenant_side"),
                (landlord, "landlord", "landlord_side"),
            ],
        )

        Message.objects.create(
            conversation=conv2,
            sender=tenant,
            content="Når utløper leiekontrakten min?",
        )
        Message.objects.create(
            conversation=conv2,
            sender=landlord,
            content="Kontrakten løper til 01.08.2026. Vi kan diskutere fornyelse nærmere sommeren.",
        )

        conv3 = self._create_conversation(
            prop=prop1,
            subject="Reparasjon av balkongdør",
            conv_type="maintenance",
            participants=[
                (tenant, "tenant", "tenant_side"),
                (landlord, "landlord", "landlord_side"),
                (contractor, "contractor", "landlord_side"),
            ],
        )

        Message.objects.create(
            conversation=conv3,
            sender=tenant,
            content="Balkongdøren klemmer og er vanskelig å lukke.",
        )
        Message.objects.create(
            conversation=conv3,
            sender=contractor,
            content="Jeg kan komme innom torsdag mellom 10-12. Passer det?",
        )
        Message.objects.create(
            conversation=conv3,
            sender=tenant,
            content="Ja, det passer fint!",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded: {User.objects.count()} users, "
                f"{Property.objects.count()} properties, "
                f"{Conversation.objects.count()} conversations, "
                f"{Message.objects.count()} messages"
            )
        )

    def _create_user(self, email, first_name, last_name):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        if created:
            user.set_password("testpass123")
            user.save()
        return user

    def _create_conversation(self, prop, subject, conv_type, participants):
        conv = Conversation.objects.create(
            property=prop,
            subject=subject,
            conversation_type=conv_type,
        )
        for user, role, side in participants:
            ConversationParticipant.objects.create(
                conversation=conv,
                user=user,
                role=role,
                side=side,
            )
            ReadState.objects.create(conversation=conv, user=user)
        return conv
