"""Add performance indexes to ReadState and Delegation models.

ReadState: (user, conversation) index for user-first queries in WebSocket sync.
Delegation: (conversation, is_active) index for active delegation lookups.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0004_search_trigger"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="readstate",
            index=models.Index(
                fields=["user", "conversation"],
                name="idx_readstate_user_conv",
            ),
        ),
        migrations.AddIndex(
            model_name="delegation",
            index=models.Index(
                fields=["conversation", "is_active"],
                name="idx_delegation_conv_active",
            ),
        ),
    ]
