from django.db import migrations
import json


def seed_salesforce(apps, schema_editor):
    SourceType = apps.get_model("sources", "SourceType")
    st, _ = SourceType.objects.get_or_create(name="Salesforce", defaults={"airbyte_connector_name": "source-salesforce"})
    st.config_example = json.dumps({
        "auth_type": "Client",
        "client_id": "...",
        "client_secret": "...",
        "refresh_token": "...",
        "is_sandbox": False,
        "start_date": "2024-01-01T00:00:00Z",
        "streams_criteria": [
            {"criteria": "exacts", "value": "Account"},
            {"criteria": "exacts", "value": "Contact"},
            {"criteria": "exacts", "value": "Opportunity"},
            {"criteria": "exacts", "value": "Lead"},
        ],
    }, indent=2)
    st.save()

def unseed_salesforce(apps, schema_editor):
    SourceType = apps.get_model("sources", "SourceType")
    SourceType.objects.filter(name="Salesforce").delete()

class Migration(migrations.Migration):
    dependencies = [
        ('sources', '0011_seed_hubspot_source_type')
    ]
    operations = [
        migrations.RunPython(seed_salesforce, unseed_salesforce)
    ]