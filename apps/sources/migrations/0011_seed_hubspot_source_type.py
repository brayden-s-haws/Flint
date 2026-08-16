from django.db import migrations
import json


def seed_hubspot(apps, schema_editor):
    SourceType = apps.get_model("sources", "SourceType")
    st, _ = SourceType.objects.get_or_create(name="HubSpot", defaults={"airbyte_connector_name": "source-hubspot"})
    st.config_example = json.dumps({"credentials": {"credentials_title": "Private App Credentials", "access_token": "..."}, "start_date": "2024-01-01T00:00:00Z"}, indent=2)
    st.save()

def unseed_hubspot(apps, schema_editor):
    SourceType = apps.get_model("sources", "SourceType")
    SourceType.objects.filter(name="HubSpot").delete()

class Migration(migrations.Migration):
    dependencies = [
        ('sources', '0010_seed_stripe_config_example'),
    ]
    operations = [
        migrations.RunPython(seed_hubspot, unseed_hubspot),
    ]