""" Tests for apps.catalog: the tenant-scoped table list/detail views, the lazy table-description
insight trigger on first detail view, and the TableStatistics model. The description task is patched
so no LLM call fires. Uses the two-tenant TenantTestCase. """
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Column, Schema, Table, TableStatistics
from apps.core.test_utils import TenantTestCase
from apps.insights.models import Insight, InsightTarget
from apps.sources.models import Source, SourceType


def make_table(account, source_type: SourceType, name: str = 'users', source_name: str = 'Src') -> Table:
    """Build the Source→Schema→Table chain for `account` and return the Table."""
    source = Source.objects.create(account=account, source_type=source_type, name=source_name, credentials='x')
    schema = Schema.objects.create(source=source, name='public', account=account)
    return Table.objects.create(schema=schema, name=name, table_type='BASE TABLE', account=account)


class TableListViewTest(TenantTestCase):
    """Returns 200, is account-scoped, and filters by ?q= (table name) and ?source=."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = SourceType.objects.create(name='PG')
        self.users = make_table(self.account_a, self.pg_type, name='users', source_name='Src A1')
        self.orders = make_table(self.account_a, self.pg_type, name='orders', source_name='Src A2')
        self.b_table = make_table(self.account_b, self.pg_type, name='secret', source_name='Src B')

    def test_list_is_account_scoped(self) -> None:
        response = self.client.get(reverse('catalog:list'))
        self.assertEqual(response.status_code, 200)
        names = {t.name for t in response.context['tables']}
        self.assertEqual(names, {'users', 'orders'})              # B's table excluded

    def test_q_filter_by_name(self) -> None:
        response = self.client.get(reverse('catalog:list'), {'q': 'user'})
        self.assertEqual({t.name for t in response.context['tables']}, {'users'})

    def test_source_filter(self) -> None:
        response = self.client.get(reverse('catalog:list'), {'source': self.orders.schema.source_id})
        self.assertEqual({t.name for t in response.context['tables']}, {'orders'})


class TableDetailViewTest(TenantTestCase):
    """Returns 200 with ordered columns + latest statistics, is account-scoped, and lazily triggers the description insight once."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = SourceType.objects.create(name='PG')
        self.table = make_table(self.account_a, self.pg_type)
        Column.objects.create(table=self.table, name='zeta', data_type='integer', account=self.account_a)
        Column.objects.create(table=self.table, name='alpha', data_type='integer', account=self.account_a)
        self.url = reverse('catalog:detail', kwargs={'pk': self.table.pk})

    @patch('apps.catalog.views.generate_table_description_task')
    def test_detail_returns_200_with_ordered_columns(self, mock_task) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c.name for c in response.context['columns']], ['alpha', 'zeta'])  # ordered by name

    @patch('apps.catalog.views.generate_table_description_task')
    def test_detail_shows_latest_statistics(self, mock_task) -> None:
        old = TableStatistics.objects.create(account=self.account_a, table=self.table, row_count=1)
        TableStatistics.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1))
        newest = TableStatistics.objects.create(account=self.account_a, table=self.table, row_count=2)
        response = self.client.get(self.url)
        self.assertEqual(response.context['statistics'].pk, newest.pk)

    @patch('apps.catalog.views.generate_table_description_task')
    def test_first_view_creates_and_dispatches_insight(self, mock_task) -> None:
        self.client.get(self.url)
        insight = Insight.objects.get(account=self.account_a, insight_type='table_description')
        self.assertEqual(insight.status, 'pending')
        target = InsightTarget.objects.get(insight=insight)  # a target row was created for the table
        self.assertEqual(target.object_id, self.table.pk)
        mock_task.delay.assert_called_once_with(insight.pk)

    @patch('apps.catalog.views.generate_table_description_task')
    def test_second_view_reuses_insight(self, mock_task) -> None:
        self.client.get(self.url)
        self.client.get(self.url)
        # Still exactly one insight, and the task was dispatched only on the first view.
        self.assertEqual(Insight.objects.filter(account=self.account_a, insight_type='table_description').count(), 1)
        mock_task.delay.assert_called_once()

    @patch('apps.catalog.views.generate_table_description_task')
    def test_cannot_view_other_accounts_table(self, mock_task) -> None:
        other = make_table(self.account_b, self.pg_type, name='b_table', source_name='B src')
        response = self.client.get(reverse('catalog:detail', kwargs={'pk': other.pk}))
        self.assertEqual(response.status_code, 404)


class TableStatisticsModelTest(TenantTestCase):
    """TableStatistics defaults (null row_count, empty column_stats) and __str__ are correct when stats are missing or partial."""
    def setUp(self) -> None:
        self.pg_type = SourceType.objects.create(name='PG')
        self.table = make_table(self.account_a, self.pg_type)

    def test_defaults_when_stats_missing(self) -> None:
        stats = TableStatistics.objects.create(account=self.account_a, table=self.table)
        self.assertIsNone(stats.row_count)          # nullable, no default
        self.assertEqual(stats.column_stats, {})    # JSONField default=dict

    def test_partial_stats_stored(self) -> None:
        stats = TableStatistics.objects.create(
            account=self.account_a, table=self.table, row_count=10,
            column_stats={'id': {'null_fraction': 0.0}})
        self.assertEqual(stats.row_count, 10)
        self.assertEqual(stats.column_stats['id']['null_fraction'], 0.0)

    def test_str_includes_table_name(self) -> None:
        stats = TableStatistics.objects.create(account=self.account_a, table=self.table)
        self.assertIn(self.table.name, str(stats))
