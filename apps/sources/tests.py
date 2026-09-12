""" Tests for apps.sources: credential encryption, the connectors (PostgreSQL/Airbyte/registry),
the source CRUD views + tenancy, connection testing, manual + scheduled sync (view + Celery task),
schedule lifecycle helpers, and the source-delete insight-cleanup signal. External I/O is mocked at
the seam (build_connector, psycopg2.connect, airbyte.get_source) and the LLM task is patched so no
network calls fire; Celery runs eagerly per the test settings. """
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from cryptography.fernet import InvalidToken
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from apps.catalog.models import Column, Schema, Table, TableStatistics
from apps.core.test_utils import TenantTestCase
from apps.insights.models import Insight, InsightTarget
from apps.sources import scheduling
from apps.sources.connectors.airbyte import AirbyteConnector
from apps.sources.connectors.postgresql import PostgreSQLConnector
from apps.sources.connectors.registry import build_connector
from apps.sources.encryption import decrypt_credentials, encrypt_credentials
from apps.sources.models import Source, SourceSchedule, SourceSyncLog, SourceType
from apps.sources.tasks import run_scheduled_sync, sync_source_task

# A minimal discovered catalog: one schema, one table, two columns (one a primary key).
FAKE_CATALOG: list[dict[str, Any]] = [{
    'name': 'public',
    'tables': [{
        'name': 'users',
        'table_type': 'BASE TABLE',
        'columns': [
            {'name': 'id', 'data_type': 'integer', 'nullable': False, 'primary_key': True},
            {'name': 'email', 'data_type': 'character varying', 'nullable': True, 'primary_key': False},
        ],
    }],
}]

NATIVE_CREDS = {'host': 'localhost', 'port': 5432, 'dbname': 'db', 'user': 'u', 'password': 'p'}


class FakeConnector:
    """Stand-in BaseConnector: returns canned catalog/metadata and a fixed test_connection result."""
    def __init__(self, ok: bool = True, catalog: list | None = None, metadata: dict | None = None) -> None:
        self._ok = ok
        self._catalog = FAKE_CATALOG if catalog is None else catalog
        self._metadata = metadata or {'row_count': 100, 'column_stats': {'id': {'null_fraction': 0.0}}}

    def test_connection(self) -> bool:
        return self._ok

    def discover_catalog(self) -> list[dict[str, Any]]:
        return self._catalog

    def get_table_metadata(self, schema_name: str, table_name: str) -> dict[str, Any]:
        return self._metadata


def make_source_type(name: str = 'TestPG', airbyte: str = '', is_demo: bool = False) -> SourceType:
    return SourceType.objects.create(name=name, airbyte_connector_name=airbyte, is_demo=is_demo)


def make_source(account, source_type: SourceType, name: str = 'Src', creds: dict | None = None) -> Source:
    return Source.objects.create(
        account=account, source_type=source_type, name=name,
        credentials=encrypt_credentials(creds or NATIVE_CREDS),
    )


# ---------------------------------------------------------------------------
# Encryption (unit)
# ---------------------------------------------------------------------------
class EncryptionUnitTest(SimpleTestCase):
    """
    encrypt/decrypt_credentials round-trip a dict; tampered ciphertext raises InvalidToken;
    a missing ENCRYPTION_KEY raises ImproperlyConfigured.
    """
    def test_round_trip(self) -> None:
        creds = {'host': 'localhost', 'user': 'admin', 'password': 'secret'}
        ciphertext = encrypt_credentials(creds)
        self.assertNotIn('secret', ciphertext)          # Stored as ciphertext, not plaintext
        self.assertEqual(decrypt_credentials(ciphertext), creds)

    def test_tampered_ciphertext_raises(self) -> None:
        with self.assertRaises(InvalidToken):
            decrypt_credentials('not-a-valid-token')

    @override_settings(ENCRYPTION_KEY=None)
    def test_missing_key_raises_improperly_configured(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            encrypt_credentials({'a': 'b'})


# ---------------------------------------------------------------------------
# Connectors (unit)
# ---------------------------------------------------------------------------
def _pg_conn_mock(cursor: MagicMock) -> MagicMock:
    """Build a mock psycopg2 connection whose context-managed cursor is `cursor`."""
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn


class PostgreSQLConnectorTest(SimpleTestCase):
    """
    discover_catalog builds the schema→table→column tree and skips system schemas; get_table_metadata
    returns the row_count + column_stats shape; connection/query errors return the safe fallback.
    """
    @patch('apps.sources.connectors.postgresql.psycopg2.connect')
    def test_discover_catalog_skips_system_schemas(self, mock_connect: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [{'schema_name': 'public'}, {'schema_name': 'information_schema'},
             {'schema_name': 'pg_catalog'}, {'schema_name': 'pg_toast'}],   # schemata
            [{'table_name': 'users', 'table_type': 'BASE TABLE'}],           # tables in public
            [{'column_name': 'id'}],                                          # primary keys
            [{'column_name': 'id', 'data_type': 'integer', 'is_nullable': 'NO'},
             {'column_name': 'email', 'data_type': 'character varying', 'is_nullable': 'YES'}],
        ]
        mock_connect.return_value = _pg_conn_mock(cursor)
        catalog = PostgreSQLConnector(NATIVE_CREDS).discover_catalog()
        self.assertEqual([s['name'] for s in catalog], ['public'])           # System schemas excluded
        table = catalog[0]['tables'][0]
        self.assertEqual(table['name'], 'users')
        cols = {c['name']: c for c in table['columns']}
        self.assertTrue(cols['id']['primary_key'])
        self.assertFalse(cols['id']['nullable'])
        self.assertTrue(cols['email']['nullable'])

    @patch('apps.sources.connectors.postgresql.psycopg2.connect')
    def test_get_table_metadata_shape(self, mock_connect: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone.return_value = {'row_count': 100}
        cursor.fetchall.return_value = [
            {'attname': 'id', 'null_frac': 0.0, 'n_distinct': 100, 'most_common_vals': None},
        ]
        mock_connect.return_value = _pg_conn_mock(cursor)
        metadata = PostgreSQLConnector(NATIVE_CREDS).get_table_metadata('public', 'users')
        self.assertEqual(metadata['row_count'], 100)
        self.assertIsInstance(metadata['column_stats'], dict)
        self.assertEqual(metadata['column_stats']['id']['distinct_count'], 100)

    @patch('apps.sources.connectors.postgresql.psycopg2.connect', side_effect=Exception('boom'))
    def test_errors_return_safe_fallback(self, mock_connect: MagicMock) -> None:
        connector = PostgreSQLConnector(NATIVE_CREDS)
        self.assertFalse(connector.test_connection())
        self.assertEqual(connector.discover_catalog(), [])
        self.assertEqual(connector.get_table_metadata('public', 'users'),
                         {'row_count': None, 'column_stats': {}})


class AirbyteConnectorTest(SimpleTestCase):
    """
    discover_catalog maps a stream's JSON schema to table/column dicts; TYPE_MAP resolves known types
    and falls back on unknown ones; get_table_metadata is always empty (schema-only connector).
    """
    @patch('apps.sources.connectors.airbyte.ab.get_source')
    def test_discover_catalog_maps_streams(self, mock_get_source: MagicMock) -> None:
        stream = MagicMock()
        stream.name = 'charges'
        stream.source_defined_primary_key = [['id']]
        stream.json_schema = {'properties': {
            'id': {'type': 'string'},
            'amount': {'type': ['integer', 'null']},
        }}
        source = MagicMock()
        source.executor = None                       # Skip the custom-components config workaround
        source.discovered_catalog.streams = [stream]
        mock_get_source.return_value = source

        catalog = AirbyteConnector({'api_key': 'x'}, 'source-stripe').discover_catalog()
        self.assertEqual(catalog[0]['name'], 'stripe')          # 'source-' prefix stripped
        cols = {c['name']: c for c in catalog[0]['tables'][0]['columns']}
        self.assertEqual(cols['id']['data_type'], 'character varying')
        self.assertTrue(cols['id']['primary_key'])
        self.assertEqual(cols['amount']['data_type'], 'bigint')
        self.assertTrue(cols['amount']['nullable'])             # ['integer', 'null'] → nullable

    def test_type_map_resolution_and_fallback(self) -> None:
        self.assertEqual(AirbyteConnector._resolve_data_type({'type': 'integer'}), 'bigint')
        self.assertEqual(AirbyteConnector._resolve_data_type({'type': 'boolean'}), 'boolean')
        # Unknown type falls through to the key itself rather than raising.
        self.assertEqual(AirbyteConnector._resolve_data_type({'type': 'geography'}), 'geography')

    def test_get_table_metadata_is_empty(self) -> None:
        metadata = AirbyteConnector({}, 'source-stripe').get_table_metadata('stripe', 'charges')
        self.assertEqual(metadata, {'row_count': None, 'column_stats': {}})


class ConnectorRegistryTest(TestCase):
    """build_connector routes native-PG types to PostgreSQLConnector and Airbyte-backed types to AirbyteConnector.

    Plain TestCase (not TenantTestCase): SourceType is not tenant-scoped and routing involves no account,
    so the two-tenant fixture would be dead weight here.
    """
    def test_native_pg_routes_to_postgresql(self) -> None:
        st = make_source_type(name='PostgreSQL', airbyte='')
        self.assertIsInstance(build_connector(st, NATIVE_CREDS), PostgreSQLConnector)

    def test_airbyte_type_routes_to_airbyte(self) -> None:
        st = make_source_type(name='HubSpot', airbyte='source-hubspot')
        self.assertIsInstance(build_connector(st, {'api_key': 'x'}), AirbyteConnector)


# ---------------------------------------------------------------------------
# Source create / edit (+ encryption at the view layer)
# ---------------------------------------------------------------------------
class SourceCreateViewTest(TenantTestCase):
    """
    GET renders; POST with native fields encrypts + stamps the account + redirects; the Airbyte path
    reads the JSON config; missing fields re-render with form errors.
    """
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = make_source_type(name='TestPG', airbyte='')

    def test_get_returns_200(self) -> None:
        self.assertEqual(self.client.get(reverse('sources:add')).status_code, 200)

    def test_post_native_creates_encrypted_source(self) -> None:
        response = self.client.post(reverse('sources:add'), {
            'name': 'My DB', 'source_type': self.pg_type.pk,
            'host': 'localhost', 'port': 5432, 'dbname': 'mydb', 'user': 'admin', 'password': 'secret',
        })
        self.assertRedirects(response, reverse('sources:list'))
        source = Source.objects.get(name='My DB')
        self.assertEqual(source.account, self.account_a)          # Stamped with request.account
        self.assertNotIn('secret', source.credentials)           # Stored as ciphertext
        self.assertEqual(decrypt_credentials(source.credentials), {
            'host': 'localhost', 'port': 5432, 'dbname': 'mydb', 'user': 'admin', 'password': 'secret',
        })

    def test_post_airbyte_uses_config(self) -> None:
        airbyte_type = make_source_type(name='TestAirbyte', airbyte='source-x')
        response = self.client.post(reverse('sources:add'), {
            'name': 'SaaS', 'source_type': airbyte_type.pk, 'config': '{"api_key": "abc"}',
        })
        self.assertRedirects(response, reverse('sources:list'))
        source = Source.objects.get(name='SaaS')
        self.assertEqual(decrypt_credentials(source.credentials), {'api_key': 'abc'})

    def test_post_missing_fields_re_renders(self) -> None:
        response = self.client.post(reverse('sources:add'), {
            'name': 'Incomplete', 'source_type': self.pg_type.pk,  # native type, but no host/port/...
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(Source.objects.filter(name='Incomplete').exists())


class SourceUpdateViewTest(TenantTestCase):
    """get_initial decrypts to pre-fill; form_valid re-encrypts; tenant-scoped (editing B's source → 404)."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = make_source_type(name='TestPG', airbyte='')
        self.source = make_source(self.account_a, self.pg_type, name='Editable')

    def test_get_initial_prefills_decrypted_fields(self) -> None:
        response = self.client.get(reverse('sources:edit', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial['host'], 'localhost')

    def test_post_reencrypts_on_save(self) -> None:
        response = self.client.post(reverse('sources:edit', kwargs={'pk': self.source.pk}), {
            'name': 'Editable', 'source_type': self.pg_type.pk,
            'host': 'newhost', 'port': 5433, 'dbname': 'db', 'user': 'u', 'password': 'p',
        })
        self.assertRedirects(response, reverse('sources:detail', kwargs={'pk': self.source.pk}))
        self.source.refresh_from_db()
        self.assertEqual(decrypt_credentials(self.source.credentials)['host'], 'newhost')

    def test_cannot_edit_other_accounts_source(self) -> None:
        other = make_source(self.account_b, self.pg_type, name='B source')
        response = self.client.get(reverse('sources:edit', kwargs={'pk': other.pk}))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Source list / detail / delete (+ tenancy)
# ---------------------------------------------------------------------------
class SourceListViewTest(TenantTestCase):
    """Returns 200, is account-scoped, and filters by ?q= (name / type name) and ?type=."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = make_source_type(name='PGType')
        self.other_type = make_source_type(name='OtherType')
        self.alpha = make_source(self.account_a, self.pg_type, name='Alpha')
        self.beta = make_source(self.account_a, self.other_type, name='Beta')
        self.b_source = make_source(self.account_b, self.pg_type, name='B only')

    def test_list_is_account_scoped(self) -> None:
        response = self.client.get(reverse('sources:list'))
        self.assertEqual(response.status_code, 200)
        names = {s.name for s in response.context['sources']}
        self.assertEqual(names, {'Alpha', 'Beta'})               # B's source excluded

    def test_q_filter_by_name(self) -> None:
        response = self.client.get(reverse('sources:list'), {'q': 'Alpha'})
        self.assertEqual({s.name for s in response.context['sources']}, {'Alpha'})

    def test_type_filter(self) -> None:
        response = self.client.get(reverse('sources:list'), {'type': 'OtherType'})
        self.assertEqual({s.name for s in response.context['sources']}, {'Beta'})


class SourceDetailViewTest(TenantTestCase):
    """Returns 200 and is account-scoped (B's source → 404)."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)

    def test_detail_returns_200(self) -> None:
        self.assertEqual(self.client.get(reverse('sources:detail', kwargs={'pk': self.source.pk})).status_code, 200)

    def test_cannot_view_other_accounts_source(self) -> None:
        other = make_source(self.account_b, self.pg_type, name='B source')
        self.assertEqual(self.client.get(reverse('sources:detail', kwargs={'pk': other.pk})).status_code, 404)


class SourceDeleteViewTest(TenantTestCase):
    """Deletes an account's own source; is account-scoped (B's source → 404)."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)

    def test_delete_removes_source(self) -> None:
        response = self.client.post(reverse('sources:delete', kwargs={'pk': self.source.pk}))
        self.assertRedirects(response, reverse('sources:list'))
        self.assertFalse(Source.objects.filter(pk=self.source.pk).exists())

    def test_cannot_delete_other_accounts_source(self) -> None:
        other = make_source(self.account_b, self.pg_type, name='B source')
        self.assertEqual(self.client.post(reverse('sources:delete', kwargs={'pk': other.pk})).status_code, 404)


# ---------------------------------------------------------------------------
# Connection test view
# ---------------------------------------------------------------------------
class ConnectionTestViewTest(TenantTestCase):
    """POST flashes success/failure per connector.test_connection; GET → 405; other account → 404."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)
        self.url = reverse('sources:test_connection', kwargs={'pk': self.source.pk})

    @patch('apps.sources.views.build_connector')
    def test_success_redirects(self, mock_build: MagicMock) -> None:
        mock_build.return_value = FakeConnector(ok=True)
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('sources:detail', kwargs={'pk': self.source.pk}))

    @patch('apps.sources.views.build_connector')
    def test_failure_redirects_with_error(self, mock_build: MagicMock) -> None:
        mock_build.return_value = FakeConnector(ok=False)
        response = self.client.post(self.url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any('failed' in str(m).lower() for m in response.context['messages']))

    def test_get_returns_405(self) -> None:
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_other_account_returns_404(self) -> None:
        # 404 short-circuits before the connector is built, so no build_connector patch is needed.
        other = make_source(self.account_b, self.pg_type, name='B source')
        response = self.client.post(reverse('sources:test_connection', kwargs={'pk': other.pk}))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Manual sync: view + status poll + the sync task
# ---------------------------------------------------------------------------
class SyncSourceViewTest(TenantTestCase):
    """POST opens a running log + enqueues the task; GET → 405; other account → 404."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)
        self.url = reverse('sources:sync', kwargs={'pk': self.source.pk})

    @patch('apps.sources.views.sync_source_task')
    def test_post_enqueues_and_redirects(self, mock_task: MagicMock) -> None:
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('sources:detail', kwargs={'pk': self.source.pk}))
        self.assertTrue(self.source.sourcesynclog_set.filter(status='running').exists())
        mock_task.delay.assert_called_once()

    @patch('apps.sources.views.sync_source_task')
    def test_post_htmx_returns_partial(self, mock_task: MagicMock) -> None:
        response = self.client.post(self.url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        mock_task.delay.assert_called_once()

    def test_get_returns_405(self) -> None:
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_other_account_returns_404(self) -> None:
        # 404 short-circuits before the task is enqueued, so no sync_source_task patch is needed.
        other = make_source(self.account_b, self.pg_type, name='B source')
        response = self.client.post(reverse('sources:sync', kwargs={'pk': other.pk}))
        self.assertEqual(response.status_code, 404)


class SyncStatusViewTest(TenantTestCase):
    """Poll returns the partial while running and an HX-Refresh empty response once the sync succeeds; account-scoped."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)
        self.url = reverse('sources:sync_status', kwargs={'pk': self.source.pk})

    def test_running_returns_partial(self) -> None:
        self.source.sourcesynclog_set.create(account=self.account_a, status='running', started_at=timezone.now())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('HX-Refresh', response)

    def test_success_returns_hx_refresh(self) -> None:
        self.source.sourcesynclog_set.create(
            account=self.account_a, status='success', started_at=timezone.now(), completed_at=timezone.now())
        response = self.client.get(self.url)
        self.assertEqual(response['HX-Refresh'], 'true')
        self.assertEqual(response.content, b'')

    def test_failed_returns_partial_without_refresh(self) -> None:
        # Only 'success' triggers HX-Refresh; a failed log falls through to the status partial.
        self.source.sourcesynclog_set.create(
            account=self.account_a, status='failed', started_at=timezone.now(), completed_at=timezone.now())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('HX-Refresh', response)

    def test_other_account_returns_404(self) -> None:
        other = make_source(self.account_b, self.pg_type, name='B source')
        self.assertEqual(self.client.get(reverse('sources:sync_status', kwargs={'pk': other.pk})).status_code, 404)


class SyncSourceTaskTest(TenantTestCase):
    """The sync pipeline upserts catalog + stats, marks the log, sets first_synced_at, and dispatches the overview insight; failures mark the log failed."""
    def setUp(self) -> None:
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)
        self.sync_log = SourceSyncLog.objects.create(
            source=self.source, account=self.account_a, status='running', started_at=timezone.now())

    @patch('apps.sources.tasks.generate_source_overview_task')
    @patch('apps.sources.tasks.build_connector')
    def test_successful_sync_upserts_catalog_and_stats(self, mock_build: MagicMock, mock_overview: MagicMock) -> None:
        mock_build.return_value = FakeConnector()
        sync_source_task(self.source.pk, self.sync_log.pk)

        # Catalog upserted, scoped to the account
        self.assertEqual(Schema.objects.filter(source=self.source, account=self.account_a).count(), 1)
        self.assertEqual(Table.objects.filter(account=self.account_a).count(), 1)
        self.assertEqual(Column.objects.filter(account=self.account_a).count(), 2)
        self.assertEqual(TableStatistics.objects.filter(account=self.account_a).count(), 1)  # one snapshot per table

        # Sync log + source state
        self.sync_log.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(self.sync_log.status, 'success')
        self.assertEqual(self.sync_log.records_synced, 1)            # counts tables
        self.assertIsNotNone(self.source.first_synced_at)

        # Source-overview insight created (pending) + generation dispatched
        overview = Insight.objects.get(account=self.account_a, insight_type='source_overview')
        self.assertEqual(overview.status, 'pending')
        mock_overview.delay.assert_called_once_with(overview.pk)

    @patch('apps.sources.tasks.generate_source_overview_task')
    @patch('apps.sources.tasks.build_connector', side_effect=Exception('boom'))
    def test_failed_sync_marks_log_failed(self, mock_build: MagicMock, mock_overview: MagicMock) -> None:
        sync_source_task(self.source.pk, self.sync_log.pk)
        self.sync_log.refresh_from_db()
        self.assertEqual(self.sync_log.status, 'failed')
        self.assertTrue(self.sync_log.error_message)
        self.assertFalse(Insight.objects.filter(insight_type='source_overview').exists())


# ---------------------------------------------------------------------------
# Scheduling helpers (unit)
# ---------------------------------------------------------------------------
class ScheduleLifecycleTest(TenantTestCase):
    """create_or_update / disable / toggle / delete keep SourceSchedule and its PeriodicTask in step, without duplicates."""
    def setUp(self) -> None:
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)

    def _task_name(self) -> str:
        return f'sync-source-{self.source.pk}'

    def test_create_makes_one_of_each(self) -> None:
        schedule, created = scheduling.create_or_update_source_schedule(self.source, 'daily')
        self.assertTrue(created)
        self.assertEqual(SourceSchedule.objects.filter(source=self.source).count(), 1)
        self.assertEqual(PeriodicTask.objects.filter(name=self._task_name()).count(), 1)
        self.assertTrue(CrontabSchedule.objects.filter(hour='6', minute='0').exists())

    def test_update_reuses_rows(self) -> None:
        scheduling.create_or_update_source_schedule(self.source, 'daily')
        schedule, created = scheduling.create_or_update_source_schedule(self.source, 'hourly')
        self.assertFalse(created)                                    # same SourceSchedule, updated
        self.assertEqual(schedule.frequency, 'hourly')
        self.assertEqual(SourceSchedule.objects.filter(source=self.source).count(), 1)
        self.assertEqual(PeriodicTask.objects.filter(name=self._task_name()).count(), 1)

    def test_disable_then_recreate_reenables(self) -> None:
        scheduling.create_or_update_source_schedule(self.source, 'daily')
        scheduling.disable_source_schedule(self.source)
        schedule = SourceSchedule.objects.get(source=self.source)
        self.assertFalse(schedule.is_enabled)
        self.assertFalse(schedule.periodic_task.enabled)
        scheduling.create_or_update_source_schedule(self.source, 'daily')
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_enabled)
        self.assertTrue(schedule.periodic_task.enabled)

    def test_toggle_flips_and_reports_prior_state(self) -> None:
        scheduling.create_or_update_source_schedule(self.source, 'daily')   # enabled
        schedule, was_paused = scheduling.toggle_source_schedule(self.source)
        self.assertFalse(was_paused)                                 # was enabled before toggle
        self.assertFalse(schedule.is_enabled)
        self.assertFalse(schedule.periodic_task.enabled)

    def test_toggle_without_schedule_raises(self) -> None:
        with self.assertRaises(SourceSchedule.DoesNotExist):
            scheduling.toggle_source_schedule(self.source)

    def test_delete_removes_both(self) -> None:
        scheduling.create_or_update_source_schedule(self.source, 'daily')
        scheduling.delete_source_schedule(self.source)
        self.assertFalse(SourceSchedule.objects.filter(source=self.source).exists())
        self.assertFalse(PeriodicTask.objects.filter(name=self._task_name()).exists())

    def test_delete_without_schedule_is_noop(self) -> None:
        scheduling.delete_source_schedule(self.source)               # should not raise
        self.assertFalse(SourceSchedule.objects.filter(source=self.source).exists())

    def test_deleting_source_removes_periodic_task(self) -> None:
        scheduling.create_or_update_source_schedule(self.source, 'daily')
        self.source.delete()                                         # post_delete signal on SourceSchedule
        self.assertFalse(PeriodicTask.objects.filter(name=self._task_name()).exists())


class RunScheduledSyncTest(TenantTestCase):
    """run_scheduled_sync opens a running log + enqueues the sync; bails on missing source/schedule/disabled."""
    def setUp(self) -> None:
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)

    @patch('apps.sources.tasks.sync_source_task')
    def test_enqueues_sync(self, mock_task: MagicMock) -> None:
        scheduling.create_or_update_source_schedule(self.source, 'daily')
        run_scheduled_sync(self.source.pk)
        self.assertTrue(self.source.sourcesynclog_set.filter(status='running').exists())
        mock_task.delay.assert_called_once()

    @patch('apps.sources.tasks.sync_source_task')
    def test_bails_when_source_missing(self, mock_task: MagicMock) -> None:
        run_scheduled_sync(999999)
        mock_task.delay.assert_not_called()

    @patch('apps.sources.tasks.sync_source_task')
    def test_bails_when_no_schedule(self, mock_task: MagicMock) -> None:
        run_scheduled_sync(self.source.pk)                           # source has no schedule
        mock_task.delay.assert_not_called()

    @patch('apps.sources.tasks.sync_source_task')
    def test_bails_when_disabled(self, mock_task: MagicMock) -> None:
        scheduling.create_or_update_source_schedule(self.source, 'daily')
        scheduling.disable_source_schedule(self.source)
        run_scheduled_sync(self.source.pk)
        mock_task.delay.assert_not_called()


# ---------------------------------------------------------------------------
# Schedule views (integration) + detail schedule context
# ---------------------------------------------------------------------------
class ScheduleViewTest(TenantTestCase):
    """Tenancy 404s on B's source, and immediate-sync is triggered on create/resume but not on a plain frequency change."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)

    @patch('apps.sources.views.run_scheduled_sync')
    def test_create_triggers_immediate_sync(self, mock_run: MagicMock) -> None:
        response = self.client.post(reverse('sources:schedule_create', kwargs={'pk': self.source.pk}), {'frequency': 'daily'})
        self.assertRedirects(response, reverse('sources:detail', kwargs={'pk': self.source.pk}))
        mock_run.delay.assert_called_once_with(self.source.pk)       # created=True

    @patch('apps.sources.views.run_scheduled_sync')
    def test_frequency_change_does_not_trigger_sync(self, mock_run: MagicMock) -> None:
        scheduling.create_or_update_source_schedule(self.source, 'daily')   # already enabled
        self.client.post(reverse('sources:schedule_create', kwargs={'pk': self.source.pk}), {'frequency': 'hourly'})
        mock_run.delay.assert_not_called()

    @patch('apps.sources.views.run_scheduled_sync')
    def test_resume_from_paused_triggers_sync(self, mock_run: MagicMock) -> None:
        scheduling.create_or_update_source_schedule(self.source, 'daily')
        scheduling.disable_source_schedule(self.source)              # paused
        self.client.post(reverse('sources:schedule_create', kwargs={'pk': self.source.pk}), {'frequency': 'daily'})
        mock_run.delay.assert_called_once_with(self.source.pk)       # was_paused=True

    def test_schedule_create_get_returns_405(self) -> None:
        self.assertEqual(self.client.get(reverse('sources:schedule_create', kwargs={'pk': self.source.pk})).status_code, 405)

    def test_toggle_other_account_returns_404(self) -> None:
        other = make_source(self.account_b, self.pg_type, name='B source')
        self.assertEqual(self.client.post(reverse('sources:schedule_toggle', kwargs={'pk': other.pk})).status_code, 404)

    def test_toggle_without_schedule_returns_404(self) -> None:
        # toggle_source_schedule raises DoesNotExist → the view returns 404.
        self.assertEqual(self.client.post(reverse('sources:schedule_toggle', kwargs={'pk': self.source.pk})).status_code, 404)


class SourceDetailScheduleContextTest(TenantTestCase):
    """SourceDetailView populates schedule/next_run/frequency_display for empty and configured states, with a fallback when cron_descriptor raises."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)

    def test_empty_schedule_context(self) -> None:
        context = self.client.get(reverse('sources:detail', kwargs={'pk': self.source.pk})).context
        self.assertIsNone(context['schedule'])
        self.assertIsNone(context['next_run'])
        self.assertIsNone(context['frequency_display'])

    def test_configured_schedule_context(self) -> None:
        scheduling.create_or_update_source_schedule(self.source, 'daily')
        context = self.client.get(reverse('sources:detail', kwargs={'pk': self.source.pk})).context
        self.assertIsNotNone(context['schedule'])
        self.assertTrue(timezone.is_aware(context['next_run']))       # timezone-aware next run
        self.assertTrue(context['frequency_display'])

    @patch('apps.sources.views.ExpressionDescriptor')
    def test_frequency_display_falls_back(self, mock_descriptor: MagicMock) -> None:
        mock_descriptor.return_value.get_description.side_effect = Exception('cron_descriptor boom')
        schedule, _ = scheduling.create_or_update_source_schedule(self.source, 'daily')
        context = self.client.get(reverse('sources:detail', kwargs={'pk': self.source.pk})).context
        self.assertEqual(context['frequency_display'], schedule.get_frequency_display())


# ---------------------------------------------------------------------------
# Source delete — insight cleanup signal
# ---------------------------------------------------------------------------
class SourceDeleteInsightCleanupTest(TenantTestCase):
    """The pre_delete signal hard-deletes insights targeting the source and its tables (GenericFK has no cascade), scoped by account."""
    def setUp(self) -> None:
        self.pg_type = make_source_type()
        self.source = make_source(self.account_a, self.pg_type)
        self.schema = Schema.objects.create(source=self.source, name='public', account=self.account_a)
        self.table = Table.objects.create(schema=self.schema, name='t', table_type='BASE TABLE', account=self.account_a)
        self.source_ct = ContentType.objects.get_for_model(Source)
        self.table_ct = ContentType.objects.get_for_model(Table)
        self.overview = self._insight('source_overview', self.source_ct, self.source.pk)
        self.use_case = self._insight('use_case_suggestion', self.source_ct, self.source.pk)
        self.table_desc = self._insight('table_description', self.table_ct, self.table.pk)

    def _insight(self, insight_type: str, ct: ContentType, object_id: int, account=None) -> Insight:
        account = account or self.account_a
        insight = Insight.objects.create(account=account, text='x', insight_type=insight_type, status='active')
        InsightTarget.objects.create(account=account, insight=insight, content_type=ct, object_id=object_id)
        return insight

    def test_deletes_source_and_table_insights(self) -> None:
        self.source.delete()
        self.assertFalse(Insight.objects.filter(pk__in=[self.overview.pk, self.use_case.pk, self.table_desc.pk]).exists())

    def test_no_orphaned_targets_remain(self) -> None:
        self.source.delete()
        self.assertEqual(InsightTarget.objects.filter(account=self.account_a).count(), 0)

    def test_other_source_insight_left_intact(self) -> None:
        other_source = make_source(self.account_a, self.pg_type, name='Other')
        keep = self._insight('source_overview', self.source_ct, other_source.pk)
        self.source.delete()
        self.assertTrue(Insight.objects.filter(pk=keep.pk).exists())

    def test_tenancy_colliding_object_id_left_intact(self) -> None:
        # An account B insight whose object_id collides with source_a.pk must survive — the signal
        # scopes deletion to instance.account.
        b_insight = self._insight('source_overview', self.source_ct, self.source.pk, account=self.account_b)
        self.source.delete()
        self.assertTrue(Insight.objects.filter(pk=b_insight.pk).exists())
