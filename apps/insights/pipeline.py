from __future__ import annotations

from apps.sources.models import Source
from apps.insights.models import Insight, InsightTarget
from apps.insights.services.provider import get_service
from django.contrib.contenttypes.models import ContentType

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

# TODO(stub): run_discovery_for_pair(source_a: Source, source_b: Source, run=None) -> int
#   Orchestrates Steps 3 -> 4 -> 6 -> 7 for ONE explicitly-selected source pair and
#   returns the number of insights created. Plain Python control flow; the LLM calls
#   go through get_service(provider). `run` is the AgentInsightRun (Phase 2) — accept
#   it now but allow None in Phase 1 (pass run=None from the caller/task).
#
#   Pick the provider once at the top (e.g. service = get_service('anthropic'), matching
#   how generate_intra_use_case_suggestions hardcodes 'anthropic' in views.py:146).
#
#   STEP 3 — discovery:
#     - relationship_dict = service.discover_cross_source_relationships(source_a, source_b)
#     - merged = _flatten_and_rank_relationships(relationship_dict)
#     - Cap the fan-out: take only the top ~2-3 relationships (slice merged[:3]).
#       Why: Step 4 yields 3-5 hypotheses EACH, and Step 6 (the expensive Sonnet call)
#       runs once per surviving hypothesis — so the cap keeps cost bounded. See the
#       featuredoc "Phase 1 fan-out policy".
#
#   STEP 4 — hypotheses (loop over the capped relationships):
#     - For each relationship: hypotheses = service.generate_cross_source_hypotheses(
#           relationship, source_a, source_b)  -> list[dict]
#     - POOL all hypotheses from all relationships into one list (extend, don't nest).
#     - Each hypothesis carries its own `specificity_score` (0.0-1.0) from the LLM.
#
#   RANK + CAP (the top-5 rule):
#     - Sort the pooled hypotheses DESCENDING by hypothesis['specificity_score'].
#     - Take the top 5 (slice [:5]). This is the embedding-free Phase 1 version of the
#       spec's "surface at most N, ranked" rule. Guard against a missing/None score
#       (default to 0.0) so the sort can't KeyError on a sloppy LLM response.
#
#   STEP 6 — final insight write (loop over the top-5 survivors):
#     - For each hypothesis: insight_data = service.generate_cross_source_use_case(
#           hypothesis, source_a, source_b)  -> dict
#       (full dict: title, description, business_value, starter_sql)
#     - Hand each insight_data to the storage step below.
#
#   STEP 7 — storage (NON-DESTRUCTIVE — see its own TODO below).
#
#   RETURN: the count of Insight rows created (int).
#
#   ERROR HANDLING: wrap LLM calls so one bad relationship/hypothesis doesn't sink the
#   whole run. In Phase 1 a try/except around the per-item LLM call that logs + skips is
#   enough; Phase 2 writes failures into AgentInsightRun.error_log. Do NOT let a single
#   Step 4/Step 6 exception abort the others.
#
#   (Phase 2 hook, not now: if `run` is not None, update its counters —
#   pairs_evaluated, hypotheses_generated, insights_created — as you go.)


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