from django.db import migrations


def seed_stripe_config_example(apps, schema_editor):
    SourceType = apps.get_model("sources", "SourceType")
    st = SourceType.objects.filter(name="Stripe").first()
    if st:
        st.config_example = '{\n  "client_secret": "sk_test_...",\n  "account_id": "acct_...",\n  "start_date": "2024-01-01T00:00:00Z"\n}'
        st.save()

def unseed_stripe_config_example(apps, schema_editor):
    SourceType = apps.get_model("sources", "SourceType")
    st = SourceType.objects.filter(name="Stripe").first()
    if st:
        st.config_example = ''
        st.save()

class Migration(migrations.Migration):
    dependencies = [
        ('sources', '0009_sourcetype_config_example'),
    ]
    operations = [
        migrations.RunPython(seed_stripe_config_example, unseed_stripe_config_example),
    ]