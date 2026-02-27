from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0003_add_search_vector"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE messaging_message
                SET search_vector = setweight(
                    to_tsvector('norwegian', coalesce(content, '')), 'A'
                )
                WHERE search_vector IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION messaging_message_search_trigger()
                RETURNS trigger AS $$
                BEGIN
                    NEW.search_vector :=
                        setweight(to_tsvector('norwegian', coalesce(NEW.content, '')), 'A');
                    RETURN NEW;
                END
                $$ LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS message_search_update ON messaging_message;
                CREATE TRIGGER message_search_update
                    BEFORE INSERT OR UPDATE OF content ON messaging_message
                    FOR EACH ROW EXECUTE FUNCTION messaging_message_search_trigger();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS message_search_update ON messaging_message;
                DROP FUNCTION IF EXISTS messaging_message_search_trigger();
            """,
        ),
    ]
