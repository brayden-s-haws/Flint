from django.db import migrations


def update_postgres_casing(apps, schema_editor):
    SourceType = apps.get_model("sources", "SourceType")
    existing = SourceType.objects.filter(name='postgresql').first()
    if existing:
        existing.name = 'PostgreSQL'
        existing.save()
    else:
        SourceType.objects.get_or_create(name='PostgreSQL', defaults={'is_demo': False})

def reverse_postgres_casing(apps, schema_editor):
    SourceType = apps.get_model("sources", "SourceType")
    existing = SourceType.objects.filter(name='PostgreSQL').first()
    if existing:
        existing.name = 'postgresql'
        existing.save()
    else:
        SourceType.objects.get_or_create(name='postgresql', defaults={'is_demo': False})



class Migration(migrations.Migration):
    dependencies = [
        ('sources', '0006_sourcetype_airbyte_connector_name'),
    ]
    operations = [
        migrations.RunPython(update_postgres_casing, reverse_postgres_casing),
    ]