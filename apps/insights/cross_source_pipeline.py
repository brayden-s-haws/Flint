from __future__ import annotations
import logging

from django.db import transaction

from apps.sources.models import Source
from apps.insights.models import Insight, InsightTarget
from apps.insights.services.provider import get_service
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)

CONFIDENCE_RANK = {
    'high': 3,
    'medium': 2,
    'low': 1
}
SEMANTIC_OVERLAP_RANK = 0

def _flatten_and_rank_relationships(relationship: dict) -> list[dict]:
    join_opportunities = relationship.get('join_opportunities', [])
    semantic_overlaps = relationship.get('semantic_overlaps', [])
    for jo in join_opportunities:
        jo['_rank'] = CONFIDENCE_RANK.get(jo.get('confidence', '').lower(), 0)
    for so in semantic_overlaps:
        so['_rank'] = SEMANTIC_OVERLAP_RANK
    merged = join_opportunities + semantic_overlaps
    merged.sort(key=lambda item: item['_rank'], reverse=True)
    for item in merged:
        del item['_rank']
    return merged

def run_discovery_for_pair(source_a: Source, source_b: Source, run=None) -> int:
    service = get_service('anthropic')
    relationship_dict = service.discover_cross_source_relationships(source_a, source_b)
    merged = _flatten_and_rank_relationships(relationship_dict)
    top_5_relationships = merged[:5]
    hypotheses = []
    for relationship in top_5_relationships:
        try:
            hypotheses.extend(service.generate_cross_source_hypotheses(relationship, source_a, source_b))
        except Exception:
            logger.exception("Failed to generate join hypothesis for source pair %s-%s; skipping", source_a, source_b)
            continue
    sorted_hypotheses = sorted(hypotheses, key=lambda h: h.get('specificity_score') or 0.0, reverse=True)
    top_5_hypotheses = sorted_hypotheses[:5]
    created_use_cases = 0
    for hypothesis in top_5_hypotheses:
        try:
            use_case = service.generate_cross_source_use_case(hypothesis, source_a, source_b)
            _store_cross_source_use_case(use_case, source_a, source_b)
            created_use_cases += 1
        except Exception:
            logger.exception("Failed to generate use case for hypothesis %s; skipping", hypothesis.get('title') or 'unknown')
            continue
    return created_use_cases

def _store_cross_source_use_case(use_case_data: dict, source_a: Source, source_b: Source) -> Insight:
    account = source_a.account
    with transaction.atomic():
        insight = Insight.objects.create(
            account=account,
            text=use_case_data['title'],
            insight_type='cross_source_use_case',
            status='pending_review',
            insight_prompt=None,
            structured_data=use_case_data,
        )
        source_ct = ContentType.objects.get_for_model(Source)
        InsightTarget.objects.create(account=account, insight=insight, content_type=source_ct, object_id=source_a.pk)
        InsightTarget.objects.create(account=account, insight=insight, content_type=source_ct, object_id=source_b.pk)
    return insight
