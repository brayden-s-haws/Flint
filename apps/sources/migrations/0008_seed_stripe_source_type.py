from django.db import migrations


def seed_stripe_source_type(apps, schema_editor):
    SourceType = apps.get_model("sources", "SourceType")
    SourceType.objects.get_or_create(name="Stripe", defaults={'airbyte_connector_name': 'source-stripe'})


def unseed_stripe_source_type(apps, schema_editor):
    SourceType = apps.get_model("sources", "SourceType")
    SourceType.objects.filter(name="Stripe").delete()


class Migration(migrations.Migration):
    dependencies = [
        ('sources', '0007_update_postgres_casing'),
    ]
    operations = [
        migrations.RunPython(seed_stripe_source_type, unseed_stripe_source_type),
    ]