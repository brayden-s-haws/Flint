""" Tests for apps.insights: insight list/detail, the four LLM generation tasks, the async HTMX
endpoints (status/retry/rating/use-cases), provider selection, and the cross-source discovery
pipeline + views. The LLM service is mocked at the seam everywhere (get_service / the service
methods) so no network call fires; Celery runs eagerly per the test settings. Uses TenantTestCase. """
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Schema, Table
from apps.core.test_utils import TenantTestCase
from apps.insights.cross_source_pipeline import (
    _flatten_and_rank_relationships, _store_cross_source_use_case, run_discovery_for_pair,
)
from apps.insights.models import Insight, InsightTarget
from apps.insights.services.anthropic_service import AnthropicService
from apps.insights.services.openai_service import OpenAIService
from apps.insights.services.provider import get_service
from apps.insights.tasks import (
    generate_intra_source_use_cases_task, generate_source_overview_task,
    generate_table_description_task, run_cross_source_discovery_task,
)
from apps.insights.views import build_use_cases_context
from apps.sources.encryption import encrypt_credentials
from apps.sources.models import Source, SourceType
from apps.sources.tasks import sync_source_task


# --- helpers ----------------------------------------------------------------
def make_source(account, source_type: SourceType, name: str = 'Src', synced: bool = False) -> Source:
    return Source.objects.create(
        account=account, source_type=source_type, name=name, credentials='x',
        first_synced_at=timezone.now() if synced else None,
    )


def make_table(account, source: Source, name: str = 'users') -> Table:
    schema = Schema.objects.create(source=source, name='public', account=account)
    return Table.objects.create(schema=schema, name=name, table_type='BASE TABLE', account=account)


def make_insight(account, insight_type: str, status: str = 'active', text: str = 't', structured=None) -> Insight:
    return Insight.objects.create(
        account=account, insight_type=insight_type, status=status, text=text, structured_data=structured)


def target(insight: Insight, obj, account) -> InsightTarget:
    return InsightTarget.objects.create(
        account=account, insight=insight,
        content_type=ContentType.objects.get_for_model(type(obj)), object_id=obj.pk)


class FakeConnector:
    """Minimal connector for the sync-overview-handling tests."""
    def test_connection(self) -> bool:
        return True

    def discover_catalog(self) -> list:
        return [{'name': 'public', 'tables': [{'name': 'users', 'table_type': 'BASE TABLE',
                 'columns': [{'name': 'id', 'data_type': 'integer', 'nullable': False, 'primary_key': True}]}]}]

    def get_table_metadata(self, schema_name: str, table_name: str) -> dict:
        return {'row_count': 1, 'column_stats': {}}


# ---------------------------------------------------------------------------
# Insight list / detail
# ---------------------------------------------------------------------------
class InsightListViewTest(TenantTestCase):
    """Returns 200, is account-scoped, and filters by ?q=, ?type=, and ?source= (source + its tables' insights)."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = SourceType.objects.create(name='PG')
        self.source = make_source(self.account_a, self.pg_type)
        self.table = make_table(self.account_a, self.source)
        self.overview = make_insight(self.account_a, 'source_overview', text='overview alpha')
        target(self.overview, self.source, self.account_a)
        self.table_desc = make_insight(self.account_a, 'table_description', text='table beta')
        target(self.table_desc, self.table, self.account_a)
        self.other = make_insight(self.account_a, 'manual', text='unrelated gamma')  # no target
        self.b_insight = make_insight(self.account_b, 'manual', text='account b')

    def test_list_is_account_scoped(self) -> None:
        response = self.client.get(reverse('insights:list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.b_insight, response.context['insights'])

    def test_q_filter(self) -> None:
        response = self.client.get(reverse('insights:list'), {'q': 'alpha'})
        self.assertEqual({i.pk for i in response.context['insights']}, {self.overview.pk})

    def test_type_filter(self) -> None:
        response = self.client.get(reverse('insights:list'), {'type': 'table_description'})
        self.assertEqual({i.pk for i in response.context['insights']}, {self.table_desc.pk})

    def test_source_filter_unions_source_and_table_insights(self) -> None:
        response = self.client.get(reverse('insights:list'), {'source': self.source.pk})
        # The source's own overview PLUS its tables' descriptions — but not the untargeted 'manual' insight.
        self.assertEqual({i.pk for i in response.context['insights']}, {self.overview.pk, self.table_desc.pk})


class InsightDetailViewTest(TenantTestCase):
    """Returns 200, resolves the target URL by type, and is account-scoped."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = SourceType.objects.create(name='PG')
        self.source = make_source(self.account_a, self.pg_type)
        self.insight = make_insight(self.account_a, 'source_overview')
        target(self.insight, self.source, self.account_a)

    def test_detail_returns_200_with_target_url(self) -> None:
        response = self.client.get(reverse('insights:detail', kwargs={'pk': self.insight.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['target_url'], reverse('sources:detail', args=[self.source.pk]))

    def test_cannot_view_other_accounts_insight(self) -> None:
        b_insight = make_insight(self.account_b, 'manual')
        self.assertEqual(self.client.get(reverse('insights:detail', kwargs={'pk': b_insight.pk})).status_code, 404)


# ---------------------------------------------------------------------------
# Table descriptions: task + status/retry views
# ---------------------------------------------------------------------------
class GenerateTableDescriptionTaskTest(TenantTestCase):
    """The task sets text + active on success and failed on failure, never raising."""
    def setUp(self) -> None:
        self.pg_type = SourceType.objects.create(name='PG')
        self.source = make_source(self.account_a, self.pg_type)
        self.table = make_table(self.account_a, self.source)
        self.insight = make_insight(self.account_a, 'table_description', status='pending', text='')
        target(self.insight, self.table, self.account_a)

    @patch('apps.insights.tasks.get_service')
    def test_success_sets_active(self, mock_get_service: MagicMock) -> None:
        mock_get_service.return_value.generate_table_description.return_value = 'A description.'
        generate_table_description_task(self.insight.pk)
        self.insight.refresh_from_db()
        self.assertEqual(self.insight.status, 'active')
        self.assertEqual(self.insight.text, 'A description.')

    @patch('apps.insights.tasks.get_service')
    def test_failure_sets_failed(self, mock_get_service: MagicMock) -> None:
        mock_get_service.return_value.generate_table_description.side_effect = Exception('boom')
        generate_table_description_task(self.insight.pk)   # must not raise
        self.insight.refresh_from_db()
        self.assertEqual(self.insight.status, 'failed')


class InsightStatusViewTest(TenantTestCase):
    """Poll returns a partial per status; an unrecognized status is 400; account-scoped."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)

    def _status_url(self, insight: Insight) -> str:
        return reverse('insights:insight_status', kwargs={'insight_id': insight.pk})

    def test_active_pending_failed_return_200(self) -> None:
        for status in ('active', 'pending', 'failed'):
            insight = make_insight(self.account_a, 'table_description', status=status)
            self.assertEqual(self.client.get(self._status_url(insight)).status_code, 200)

    def test_unrecognized_status_returns_400(self) -> None:
        insight = make_insight(self.account_a, 'table_description', status='archived')
        self.assertEqual(self.client.get(self._status_url(insight)).status_code, 400)

    def test_other_account_returns_404(self) -> None:
        b_insight = make_insight(self.account_b, 'table_description', status='active')
        self.assertEqual(self.client.get(self._status_url(b_insight)).status_code, 404)


class InsightRetryViewTest(TenantTestCase):
    """Retry re-dispatches a failed insight (→ pending); a non-failed insight is 400; account-scoped."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)

    def _retry_url(self, insight: Insight) -> str:
        return reverse('insights:insight_retry', kwargs={'insight_id': insight.pk})

    @patch('apps.insights.views.generate_table_description_task')
    def test_retry_failed_resets_to_pending(self, mock_task: MagicMock) -> None:
        insight = make_insight(self.account_a, 'table_description', status='failed')
        response = self.client.post(self._retry_url(insight))
        self.assertEqual(response.status_code, 200)
        insight.refresh_from_db()
        self.assertEqual(insight.status, 'pending')
        mock_task.delay.assert_called_once_with(insight.id)

    @patch('apps.insights.views.generate_table_description_task')
    def test_retry_non_failed_returns_400(self, mock_task: MagicMock) -> None:
        insight = make_insight(self.account_a, 'table_description', status='active')
        self.assertEqual(self.client.post(self._retry_url(insight)).status_code, 400)
        mock_task.delay.assert_not_called()

    @patch('apps.insights.views.generate_table_description_task')
    def test_other_account_returns_404(self, mock_task: MagicMock) -> None:
        b_insight = make_insight(self.account_b, 'table_description', status='failed')
        self.assertEqual(self.client.post(self._retry_url(b_insight)).status_code, 404)


# ---------------------------------------------------------------------------
# Source overview: task + sync-side handling + use-cases gate
# ---------------------------------------------------------------------------
class GenerateSourceOverviewTaskTest(TenantTestCase):
    """The task sets active on success and failed on failure."""
    def setUp(self) -> None:
        self.pg_type = SourceType.objects.create(name='PG')
        self.source = make_source(self.account_a, self.pg_type)
        self.insight = make_insight(self.account_a, 'source_overview', status='pending', text='')
        target(self.insight, self.source, self.account_a)

    @patch('apps.insights.tasks.get_service')
    def test_success_sets_active(self, mock_get_service: MagicMock) -> None:
        mock_get_service.return_value.generate_source_overview.return_value = 'Overview text.'
        generate_source_overview_task(self.insight.pk)
        self.insight.refresh_from_db()
        self.assertEqual(self.insight.status, 'active')
        self.assertEqual(self.insight.text, 'Overview text.')

    @patch('apps.insights.tasks.get_service')
    def test_failure_sets_failed(self, mock_get_service: MagicMock) -> None:
        mock_get_service.return_value.generate_source_overview.side_effect = Exception('boom')
        generate_source_overview_task(self.insight.pk)
        self.insight.refresh_from_db()
        self.assertEqual(self.insight.status, 'failed')


class SyncSourceOverviewHandlingTest(TenantTestCase):
    """During sync: a failed overview is deleted and re-created pending; an active overview is left untouched."""
    def setUp(self) -> None:
        self.pg_type = SourceType.objects.create(name='PG')
        self.source = make_source(self.account_a, self.pg_type)
        # sync_source_task decrypts credentials before building the connector, so they must be real
        # ciphertext (the default 'x' would raise InvalidToken and fail the sync before overview handling).
        self.source.credentials = encrypt_credentials({'host': 'h'})
        self.source.save()
        self.source_ct = ContentType.objects.get_for_model(Source)

    def _run_sync(self):
        from apps.sources.models import SourceSyncLog
        log = SourceSyncLog.objects.create(source=self.source, account=self.account_a, status='running', started_at=timezone.now())
        sync_source_task(self.source.pk, log.pk)

    @patch('apps.sources.tasks.generate_source_overview_task')
    @patch('apps.sources.tasks.build_connector')
    def test_failed_overview_is_replaced(self, mock_build: MagicMock, mock_overview: MagicMock) -> None:
        mock_build.return_value = FakeConnector()
        failed = make_insight(self.account_a, 'source_overview', status='failed')
        target(failed, self.source, self.account_a)
        self._run_sync()
        self.assertFalse(Insight.objects.filter(pk=failed.pk).exists())     # old failed one deleted
        fresh = Insight.objects.get(insight_type='source_overview', account=self.account_a)
        self.assertEqual(fresh.status, 'pending')
        mock_overview.delay.assert_called_once_with(fresh.pk)

    @patch('apps.sources.tasks.generate_source_overview_task')
    @patch('apps.sources.tasks.build_connector')
    def test_active_overview_untouched(self, mock_build: MagicMock, mock_overview: MagicMock) -> None:
        mock_build.return_value = FakeConnector()
        active = make_insight(self.account_a, 'source_overview', status='active', text='kept')
        target(active, self.source, self.account_a)
        self._run_sync()
        active.refresh_from_db()
        self.assertEqual(active.status, 'active')                           # unchanged
        self.assertEqual(Insight.objects.filter(insight_type='source_overview').count(), 1)  # no new one
        mock_overview.delay.assert_not_called()


class UseCasesGateTest(TenantTestCase):
    """build_use_cases_context exposes the overview text only while the overview is active (gates the generate form)."""
    def setUp(self) -> None:
        self.pg_type = SourceType.objects.create(name='PG')
        self.source = make_source(self.account_a, self.pg_type)

    def test_active_overview_exposed(self) -> None:
        overview = make_insight(self.account_a, 'source_overview', status='active', text='ready')
        target(overview, self.source, self.account_a)
        self.assertEqual(build_use_cases_context(self.source)['source_overview'], 'ready')

    def test_pending_overview_hidden(self) -> None:
        overview = make_insight(self.account_a, 'source_overview', status='pending', text='')
        target(overview, self.source, self.account_a)
        self.assertIsNone(build_use_cases_context(self.source)['source_overview'])


# ---------------------------------------------------------------------------
# Intra-source use cases: task + views
# ---------------------------------------------------------------------------
class GenerateIntraUseCasesTaskTest(TenantTestCase):
    """Success creates one active use-case per result + deletes the placeholder; failure flips it to failed; regeneration appends."""
    def setUp(self) -> None:
        self.pg_type = SourceType.objects.create(name='PG')
        self.source = make_source(self.account_a, self.pg_type)

    def _placeholder(self) -> Insight:
        ph = make_insight(self.account_a, 'use_case_suggestion', status='pending', text='')
        target(ph, self.source, self.account_a)
        return ph

    @patch('apps.insights.tasks.get_service')
    def test_success_creates_use_cases_and_deletes_placeholder(self, mock_get_service: MagicMock) -> None:
        mock_get_service.return_value.generate_intra_source_use_case.return_value = [
            {'title': 'UC1'}, {'title': 'UC2'}]
        placeholder = self._placeholder()
        generate_intra_source_use_cases_task(self.source.pk, placeholder.pk)
        self.assertFalse(Insight.objects.filter(pk=placeholder.pk).exists())      # placeholder gone
        active = Insight.objects.filter(insight_type='use_case_suggestion', status='active', account=self.account_a)
        self.assertEqual(active.count(), 2)

    @patch('apps.insights.tasks.get_service')
    def test_failure_flips_placeholder(self, mock_get_service: MagicMock) -> None:
        mock_get_service.return_value.generate_intra_source_use_case.side_effect = Exception('boom')
        placeholder = self._placeholder()
        generate_intra_source_use_cases_task(self.source.pk, placeholder.pk)
        placeholder.refresh_from_db()
        self.assertEqual(placeholder.status, 'failed')
        self.assertFalse(Insight.objects.filter(insight_type='use_case_suggestion', status='active').exists())

    @patch('apps.insights.tasks.get_service')
    def test_regeneration_is_non_destructive(self, mock_get_service: MagicMock) -> None:
        mock_get_service.return_value.generate_intra_source_use_case.return_value = [{'title': 'UC'}]
        generate_intra_source_use_cases_task(self.source.pk, self._placeholder().pk)
        generate_intra_source_use_cases_task(self.source.pk, self._placeholder().pk)
        self.assertEqual(
            Insight.objects.filter(insight_type='use_case_suggestion', status='active').count(), 2)  # appended


class GenerateIntraUseCasesViewTest(TenantTestCase):
    """The view enqueues the task on the happy path but rejects with 400 when there's no overview or it's rate-limited; account-scoped."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = SourceType.objects.create(name='PG')
        self.source = make_source(self.account_a, self.pg_type)

    def _url(self, source: Source) -> str:
        return reverse('insights:generate_use_cases', kwargs={'source_id': source.pk})

    def _add_overview(self) -> None:
        overview = make_insight(self.account_a, 'source_overview', status='active', text='o')
        target(overview, self.source, self.account_a)

    @patch('apps.insights.views.generate_intra_source_use_cases_task')
    def test_happy_path_enqueues(self, mock_task: MagicMock) -> None:
        self._add_overview()
        response = self.client.post(self._url(self.source))
        self.assertEqual(response.status_code, 200)
        placeholder = Insight.objects.get(insight_type='use_case_suggestion', status='pending')
        mock_task.delay.assert_called_once_with(self.source.id, placeholder.pk)

    @patch('apps.insights.views.generate_intra_source_use_cases_task')
    def test_no_overview_returns_400(self, mock_task: MagicMock) -> None:
        self.assertEqual(self.client.post(self._url(self.source)).status_code, 400)
        mock_task.delay.assert_not_called()

    @patch('apps.insights.views.generate_intra_source_use_cases_task')
    def test_rate_limited_returns_400(self, mock_task: MagicMock) -> None:
        self._add_overview()
        recent = make_insight(self.account_a, 'use_case_suggestion', status='active')  # created just now
        target(recent, self.source, self.account_a)
        self.assertEqual(self.client.post(self._url(self.source)).status_code, 400)
        mock_task.delay.assert_not_called()

    def test_other_account_returns_404(self) -> None:
        b_source = make_source(self.account_b, self.pg_type, name='B src')
        self.assertEqual(self.client.post(self._url(b_source)).status_code, 404)


class UseCasesStatusViewTest(TenantTestCase):
    """The poll renders the section for the account's own source and 404s another account's source."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = SourceType.objects.create(name='PG')
        self.source = make_source(self.account_a, self.pg_type)

    def test_returns_200(self) -> None:
        url = reverse('insights:use_cases_status', kwargs={'source_id': self.source.pk})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_other_account_returns_404(self) -> None:
        b_source = make_source(self.account_b, self.pg_type, name='B src')
        url = reverse('insights:use_cases_status', kwargs={'source_id': b_source.pk})
        self.assertEqual(self.client.get(url).status_code, 404)


# ---------------------------------------------------------------------------
# Rating
# ---------------------------------------------------------------------------
class RateInsightViewTest(TenantTestCase):
    """Records approved/rejected, toggles the current rating back to none, rejects other values, and is account-scoped."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.insight = make_insight(self.account_a, 'table_description')

    def _url(self, insight: Insight) -> str:
        return reverse('insights:rate_insight', kwargs={'insight_id': insight.pk})

    def test_records_rating(self) -> None:
        self.client.post(self._url(self.insight), {'rating': 'approved'})
        self.insight.refresh_from_db()
        self.assertEqual(self.insight.rating, 'approved')

    def test_resubmitting_toggles_to_none(self) -> None:
        self.insight.rating = 'approved'
        self.insight.save()
        self.client.post(self._url(self.insight), {'rating': 'approved'})
        self.insight.refresh_from_db()
        self.assertEqual(self.insight.rating, 'none')

    def test_invalid_value_returns_400(self) -> None:
        self.assertEqual(self.client.post(self._url(self.insight), {'rating': 'banana'}).status_code, 400)

    def test_other_account_returns_404(self) -> None:
        b_insight = make_insight(self.account_b, 'table_description')
        self.assertEqual(self.client.post(self._url(b_insight), {'rating': 'approved'}).status_code, 404)


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------
@override_settings(OPENAI_API_KEY='sk-test', ANTHROPIC_API_KEY='anthropic-test')
class ProviderSelectionTest(SimpleTestCase):
    """get_service returns the matching service wired with the right key; an unknown provider raises ValueError."""
    def test_openai(self) -> None:
        service = get_service('openai')
        self.assertIsInstance(service, OpenAIService)
        self.assertEqual(service.api_key, 'sk-test')

    def test_anthropic(self) -> None:
        service = get_service('anthropic')
        self.assertIsInstance(service, AnthropicService)
        self.assertEqual(service.api_key, 'anthropic-test')

    def test_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_service('gemini')


# ---------------------------------------------------------------------------
# Cross-source discovery: pipeline + storage
# ---------------------------------------------------------------------------
class FlattenAndRankTest(SimpleTestCase):
    """_flatten_and_rank ranks join opportunities by confidence above semantic overlaps, strips _rank, and tolerates missing keys."""
    def test_confidence_ranking_and_ordering(self) -> None:
        rel = {
            'join_opportunities': [
                {'id': 'low', 'confidence': 'low'},
                {'id': 'high', 'confidence': 'high'},
                {'id': 'unknown', 'confidence': 'wat'},   # unknown → 0
            ],
            'semantic_overlaps': [{'id': 'semantic'}],     # rank 0
        }
        merged = _flatten_and_rank_relationships(rel)
        self.assertEqual(merged[0]['id'], 'high')          # highest confidence first
        for item in merged:
            self.assertNotIn('_rank', item)                # scratch key stripped from outputs
        # inputs mutated in place also had _rank removed
        self.assertNotIn('_rank', rel['join_opportunities'][0])

    def test_missing_keys_do_not_raise(self) -> None:
        self.assertEqual(_flatten_and_rank_relationships({}), [])


class RunDiscoveryForPairTest(TenantTestCase):
    """The pipeline stores one pending_review insight (with two source targets) per surviving hypothesis, caps fan-out, isolates per-item failures, and appends on re-run."""
    def setUp(self) -> None:
        self.pg_type = SourceType.objects.create(name='PG')
        self.source_a = make_source(self.account_a, self.pg_type, name='A', synced=True)
        self.source_b = make_source(self.account_a, self.pg_type, name='B', synced=True)

    def _service(self, *, relationships=None, hypotheses=None, use_case=None) -> MagicMock:
        service = MagicMock()
        service.discover_cross_source_relationships.return_value = {
            'join_opportunities': relationships if relationships is not None else [{'confidence': 'high'}],
            'semantic_overlaps': [],
        }
        service.generate_cross_source_hypotheses.return_value = (
            hypotheses if hypotheses is not None else [{'title': 'h', 'specificity_score': 0.9}])
        service.generate_cross_source_use_case.return_value = use_case or {'title': 'Use Case'}
        return service

    @patch('apps.insights.cross_source_pipeline.get_service')
    def test_stores_one_insight_with_two_targets(self, mock_get_service: MagicMock) -> None:
        mock_get_service.return_value = self._service()
        count = run_discovery_for_pair(self.source_a, self.source_b)
        self.assertEqual(count, 1)
        insight = Insight.objects.get(insight_type='cross_source_use_case')
        self.assertEqual(insight.status, 'pending_review')
        self.assertEqual(insight.account, self.account_a)
        object_ids = set(insight.insighttarget_set.values_list('object_id', flat=True))
        self.assertEqual(object_ids, {self.source_a.pk, self.source_b.pk})   # exactly two, one per source

    @patch('apps.insights.cross_source_pipeline.get_service')
    def test_step4_caps_at_five_relationships(self, mock_get_service: MagicMock) -> None:
        service = self._service(relationships=[{'confidence': 'high'} for _ in range(7)], hypotheses=[])
        mock_get_service.return_value = service
        run_discovery_for_pair(self.source_a, self.source_b)
        self.assertEqual(service.generate_cross_source_hypotheses.call_count, 5)   # top 5 only

    @patch('apps.insights.cross_source_pipeline.get_service')
    def test_step6_caps_and_sorts_by_specificity(self, mock_get_service: MagicMock) -> None:
        hypotheses = [{'id': i, 'specificity_score': i / 10} for i in range(1, 9)]  # 8 scored
        hypotheses += [{'id': 'none', 'specificity_score': None}, {'id': 'missing'}]  # None/missing → 0.0
        service = self._service(hypotheses=hypotheses)
        mock_get_service.return_value = service
        run_discovery_for_pair(self.source_a, self.source_b)
        self.assertEqual(service.generate_cross_source_use_case.call_count, 5)      # top 5 survive
        used_ids = {call.args[0]['id'] for call in service.generate_cross_source_use_case.call_args_list}
        self.assertEqual(used_ids, {8, 7, 6, 5, 4})                                # highest scores

    @patch('apps.insights.cross_source_pipeline.get_service')
    def test_step6_failure_is_isolated(self, mock_get_service: MagicMock) -> None:
        service = self._service(hypotheses=[{'title': 'h1', 'specificity_score': 0.9},
                                            {'title': 'h2', 'specificity_score': 0.8}])
        service.generate_cross_source_use_case.side_effect = [Exception('boom'), {'title': 'ok'}]
        mock_get_service.return_value = service
        count = run_discovery_for_pair(self.source_a, self.source_b)
        self.assertEqual(count, 1)                                                 # only the survivor persisted
        self.assertEqual(Insight.objects.filter(insight_type='cross_source_use_case').count(), 1)

    @patch('apps.insights.cross_source_pipeline.get_service')
    def test_regeneration_appends(self, mock_get_service: MagicMock) -> None:
        mock_get_service.return_value = self._service()
        run_discovery_for_pair(self.source_a, self.source_b)
        run_discovery_for_pair(self.source_a, self.source_b)
        self.assertEqual(Insight.objects.filter(insight_type='cross_source_use_case').count(), 2)

    def test_store_is_atomic(self) -> None:
        # A failure creating the second target rolls back the whole insight (never a 1-target insight).
        with patch.object(InsightTarget.objects, 'create', side_effect=[MagicMock(), Exception('boom')]):
            with self.assertRaises(Exception):
                _store_cross_source_use_case({'title': 'x'}, self.source_a, self.source_b)
        self.assertEqual(Insight.objects.filter(insight_type='cross_source_use_case').count(), 0)


class RunCrossSourceDiscoveryTaskTest(TenantTestCase):
    """The task loads both sources scoped to the account and bails (no insights) when a source belongs to another account."""
    def setUp(self) -> None:
        self.pg_type = SourceType.objects.create(name='PG')
        self.source_a = make_source(self.account_a, self.pg_type, name='A', synced=True)
        self.source_b = make_source(self.account_a, self.pg_type, name='B', synced=True)

    @patch('apps.insights.tasks.run_discovery_for_pair')
    def test_runs_for_own_pair(self, mock_run: MagicMock) -> None:
        run_cross_source_discovery_task(self.account_a.id, self.source_a.id, self.source_b.id)
        mock_run.assert_called_once_with(self.source_a, self.source_b)   # right sources, right order

    @patch('apps.insights.tasks.run_discovery_for_pair')
    def test_cross_account_source_bails(self, mock_run: MagicMock) -> None:
        b_source = make_source(self.account_b, self.pg_type, name='B-owned', synced=True)
        run_cross_source_discovery_task(self.account_a.id, self.source_a.id, b_source.id)
        mock_run.assert_not_called()                                               # DoesNotExist → bail
        self.assertFalse(Insight.objects.filter(insight_type='cross_source_use_case').exists())


# ---------------------------------------------------------------------------
# Cross-source discovery: views
# ---------------------------------------------------------------------------
class RunCrossSourceDiscoveryViewTest(TenantTestCase):
    """POST enqueues the task on the happy path; rejects self-pair / unsynced (400), other-account (404), and rate-limited pairs (400)."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = SourceType.objects.create(name='PG')
        self.source_a = make_source(self.account_a, self.pg_type, name='A', synced=True)
        self.source_b = make_source(self.account_a, self.pg_type, name='B', synced=True)
        self.url = reverse('insights:run_cross_source_discovery')

    def _recent_pair_insight(self, a: Source, b: Source, status: str = 'active') -> Insight:
        insight = make_insight(self.account_a, 'cross_source_use_case', status=status)
        target(insight, a, self.account_a)
        target(insight, b, self.account_a)
        return insight

    @patch('apps.insights.views.run_cross_source_discovery_task')
    def test_happy_path_enqueues(self, mock_task: MagicMock) -> None:
        mock_task.delay.return_value.id = 'task-123'
        response = self.client.post(self.url, {'source_a': self.source_a.pk, 'source_b': self.source_b.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['running'])
        mock_task.delay.assert_called_once_with(self.account_a.id, self.source_a.id, self.source_b.id)

    def test_self_pair_returns_400(self) -> None:
        response = self.client.post(self.url, {'source_a': self.source_a.pk, 'source_b': self.source_a.pk})
        self.assertEqual(response.status_code, 400)

    def test_unsynced_source_returns_400(self) -> None:
        unsynced = make_source(self.account_a, self.pg_type, name='U', synced=False)
        response = self.client.post(self.url, {'source_a': self.source_a.pk, 'source_b': unsynced.pk})
        self.assertEqual(response.status_code, 400)

    def test_other_account_source_returns_404(self) -> None:
        b_source = make_source(self.account_b, self.pg_type, name='B-owned', synced=True)
        response = self.client.post(self.url, {'source_a': self.source_a.pk, 'source_b': b_source.pk})
        self.assertEqual(response.status_code, 404)

    def test_rate_limited_pair_returns_400(self) -> None:
        self._recent_pair_insight(self.source_a, self.source_b)
        response = self.client.post(self.url, {'source_a': self.source_a.pk, 'source_b': self.source_b.pk})
        self.assertEqual(response.status_code, 400)

    @patch('apps.insights.views.run_cross_source_discovery_task')
    def test_partial_pair_match_not_rate_limited(self, mock_task: MagicMock) -> None:
        mock_task.delay.return_value.id = 't'
        other = make_source(self.account_a, self.pg_type, name='C', synced=True)
        self._recent_pair_insight(self.source_a, other)     # a+other, not a+b
        response = self.client.post(self.url, {'source_a': self.source_a.pk, 'source_b': self.source_b.pk})
        self.assertEqual(response.status_code, 200)         # proceeds

    def test_dismissed_pair_still_rate_limits(self) -> None:
        self._recent_pair_insight(self.source_a, self.source_b, status='dismissed')
        response = self.client.post(self.url, {'source_a': self.source_a.pk, 'source_b': self.source_b.pk})
        self.assertEqual(response.status_code, 400)         # dismissed still counts as "a run happened"


class AcceptDismissAgentInsightTest(TenantTestCase):
    """accept/dismiss flip a pending_review cross-source insight; both guard on status, account, and insight_type."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.insight = make_insight(self.account_a, 'cross_source_use_case', status='pending_review')

    def test_accept_activates(self) -> None:
        response = self.client.post(reverse('insights:accept_agent_insight', kwargs={'insight_id': self.insight.pk}))
        self.assertEqual(response.status_code, 200)
        self.insight.refresh_from_db()
        self.assertEqual(self.insight.status, 'active')

    def test_dismiss_dismisses_with_empty_body(self) -> None:
        response = self.client.post(reverse('insights:dismiss_agent_insight', kwargs={'insight_id': self.insight.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')
        self.insight.refresh_from_db()
        self.assertEqual(self.insight.status, 'dismissed')

    def test_accept_non_pending_review_returns_400(self) -> None:
        self.insight.status = 'active'
        self.insight.save()
        self.assertEqual(self.client.post(
            reverse('insights:accept_agent_insight', kwargs={'insight_id': self.insight.pk})).status_code, 400)

    def test_wrong_insight_type_returns_404(self) -> None:
        # The lookup scopes to insight_type='cross_source_use_case'.
        other = make_insight(self.account_a, 'table_description', status='pending_review')
        self.assertEqual(self.client.post(
            reverse('insights:accept_agent_insight', kwargs={'insight_id': other.pk})).status_code, 404)

    def test_other_account_returns_404(self) -> None:
        b_insight = make_insight(self.account_b, 'cross_source_use_case', status='pending_review')
        self.assertEqual(self.client.post(
            reverse('insights:dismiss_agent_insight', kwargs={'insight_id': b_insight.pk})).status_code, 404)


class CrossSourceDiscoveryViewTest(TenantTestCase):
    """Lists only non-dismissed cross-source insights, newest-first, filterable by source/text, account-scoped."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = SourceType.objects.create(name='PG')
        self.source = make_source(self.account_a, self.pg_type, synced=True)
        self.active = make_insight(self.account_a, 'cross_source_use_case', status='active', text='alpha finding')
        target(self.active, self.source, self.account_a)
        self.dismissed = make_insight(self.account_a, 'cross_source_use_case', status='dismissed', text='gone')
        self.b_insight = make_insight(self.account_b, 'cross_source_use_case', status='active', text='b finding')

    def test_excludes_dismissed_and_other_accounts(self) -> None:
        insights = self.client.get(reverse('insights:discovery')).context['insights']
        pks = {i.pk for i in insights}
        self.assertIn(self.active.pk, pks)
        self.assertNotIn(self.dismissed.pk, pks)
        self.assertNotIn(self.b_insight.pk, pks)

    def test_source_filter(self) -> None:
        insights = self.client.get(reverse('insights:discovery'), {'source': self.source.pk}).context['insights']
        self.assertEqual({i.pk for i in insights}, {self.active.pk})

    def test_q_filter(self) -> None:
        insights = self.client.get(reverse('insights:discovery'), {'q': 'alpha'}).context['insights']
        self.assertEqual({i.pk for i in insights}, {self.active.pk})


class CrossSourceDiscoveryStatusViewTest(TenantTestCase):
    """running is True only while a task_id's AsyncResult is not ready."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.url = reverse('insights:cross_source_discovery_status')

    def test_no_task_id_not_running(self) -> None:
        self.assertFalse(self.client.get(self.url).context['running'])

    @patch('apps.insights.views.run_cross_source_discovery_task')
    def test_unfinished_task_is_running(self, mock_task: MagicMock) -> None:
        mock_task.AsyncResult.return_value.ready.return_value = False
        self.assertTrue(self.client.get(self.url, {'task_id': 'abc'}).context['running'])

    @patch('apps.insights.views.run_cross_source_discovery_task')
    def test_finished_task_not_running(self, mock_task: MagicMock) -> None:
        mock_task.AsyncResult.return_value.ready.return_value = True
        self.assertFalse(self.client.get(self.url, {'task_id': 'abc'}).context['running'])


class DashboardCrossSourceCountTest(TenantTestCase):
    """The dashboard's cross_source_insight_count excludes dismissed and other accounts' insights."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)

    def test_count_excludes_dismissed_and_other_account(self) -> None:
        make_insight(self.account_a, 'cross_source_use_case', status='active')
        make_insight(self.account_a, 'cross_source_use_case', status='pending_review')
        make_insight(self.account_a, 'cross_source_use_case', status='dismissed')   # excluded
        make_insight(self.account_b, 'cross_source_use_case', status='active')       # excluded
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.context['cross_source_insight_count'], 2)