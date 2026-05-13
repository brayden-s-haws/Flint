"""Data migration: re-type legacy 'ai' Insight rows based on what their InsightTarget points at.

Forward:
    InsightTarget points at a Table   -> insight_type = 'table_description'
    InsightTarget points at a Source  -> insight_type = 'source_overview'
    Anything else (or missing target) -> leave as 'ai' and print a warning

Reverse:
    'table_description' / 'source_overview' rows -> back to 'ai'
"""
from __future__ import annotations

from django.db import migrations


def retype_ai_insights_forward(apps, schema_editor):
    # Always use apps.get_model in data migrations — it returns the historical
    # version of the model as the migration sees it, so the migration still works
    # even if the real model class changes later.
    Insight = apps.get_model('insights', 'Insight')
    InsightTarget = apps.get_model('insights', 'InsightTarget')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # Look up the ContentType ids for Table and Source once, up front.
    # If a ContentType row doesn't exist yet (e.g. fresh DB with no Tables/Sources
    # ever created), .first() returns None — the comparison below just won't match,
    # which is the right behavior.
    table_ct_id = (
        ContentType.objects
        .filter(app_label='catalog', model='table')
        .values_list('id', flat=True)
        .first()
    )
    source_ct_id = (
        ContentType.objects
        .filter(app_label='sources', model='source')
        .values_list('id', flat=True)
        .first()
    )

    # Walk every 'ai'-typed Insight and decide what to re-type it to based on the
    # ContentType of its first (and in practice only) InsightTarget.
    for insight in Insight.objects.filter(insight_type='ai'):
        target = InsightTarget.objects.filter(insight=insight).first()

        if target is None:
            print(f"WARNING: insight {insight.pk} has no InsightTarget — leaving as 'ai'")
            continue

        if target.content_type_id == table_ct_id:
            insight.insight_type = 'table_description'
            insight.save()
        elif target.content_type_id == source_ct_id:
            insight.insight_type = 'source_overview'
            insight.save()
        else:
            print(
                f"WARNING: insight {insight.pk} target content_type_id={target.content_type_id} "
                f"matches neither catalog.table nor sources.source — leaving as 'ai'"
            )


def retype_ai_insights_reverse(apps, schema_editor):
    # Reverse is unambiguous: every row this migration may have re-typed gets
    # flipped back to 'ai'. Two bulk .update() calls — no need to loop.
    Insight = apps.get_model('insights', 'Insight')
    Insight.objects.filter(insight_type='table_description').update(insight_type='ai')
    Insight.objects.filter(insight_type='source_overview').update(insight_type='ai')


class Migration(migrations.Migration):

    dependencies = [
        ('insights', '0007_alter_insight_insight_type'),
    ]

    operations = [
        migrations.RunPython(
            retype_ai_insights_forward,
            retype_ai_insights_reverse,
        ),
    ]