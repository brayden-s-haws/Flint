from __future__ import annotations
import logging

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


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

# Orchestrates Steps 3 -> 4 -> 6 -> 7 for ONE explicitly-selected source pair and
# returns the number of insights created. Plain Python control flow; LLM calls go
# through get_service(). Fan-out cap (featuredoc "Phase 1 fan-out policy"): top 5
# relationships -> Step 4 -> pool -> top 5 hypotheses by specificity_score -> Step 6.
# `run` is the Phase 2 AgentInsightRun — accept it now, None in Phase 1.
#
# TODO(remaining): wire Step 6 result into _store_cross_source_insight(), count the
#   created insights, return the count, and add per-item try/except around Step 4 and
#   Step 6 so one bad item doesn't sink the run.
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
            created_use_cases += 1
        except Exception:
            logger.exception("Failed to generate use case for hypothesis %s; skipping", hypothesis.get('title') or 'unknown')
            continue
    return created_use_cases




# ---------------------------------------------------------------------------
# Storage (Step 7)
# ---------------------------------------------------------------------------

# TODO(stub): _store_cross_source_insight(insight_data: dict, source_a: Source,
#                                          source_b: Source) -> Insight
#   Mirror the create pattern in views.py:150-155, with TWO differences for cross-source:
#     - status='pending_review' (NOT 'active') — agent insights go through the review gate.
#     - create TWO InsightTarget rows, one per source (intra-source creates one).
#   Steps:
#     1. account = source_a.account  (both sources share the account — they're the same
#        tenant's sources; you may assert source_a.account_id == source_b.account_id).
#     2. insight = Insight.objects.create(
#            account=account,
#            text=insight_data['title'],          # `text` mirrors the title, like intra-source
#            insight_type='cross_source_use_case',
#            status='pending_review',
#            insight_prompt=None,
#            structured_data=insight_data,         # full Step 6 dict lives here
#        )
#     3. ContentType: source_ct = ContentType.objects.get_for_model(Source)
#        (Source is its own content type; both targets use the SAME content_type, different object_id.)
#     4. InsightTarget.objects.create(account=account, insight=insight,
#            content_type=source_ct, object_id=source_a.pk)
#        InsightTarget.objects.create(account=account, insight=insight,
#            content_type=source_ct, object_id=source_b.pk)
#     5. return insight
#
#   NON-DESTRUCTIVE (decided — featuredoc "Regeneration is non-destructive"):
#   there is NO delete step here. Do NOT replicate the delete-then-create block from
#   views.py:137-143. Re-running discovery for a pair APPENDS new pending_review insights;
#   the dedicated page renders newest-first so re-runs stack on top with history preserved.
#
#   Consider wrapping the insight + two targets in a transaction.atomic() so you never
#   persist an Insight with only one (or zero) targets if the second create fails.