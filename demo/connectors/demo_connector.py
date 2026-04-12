from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from apps.sources.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

PATH_TO_DATA_DIR = Path(__file__).parent.parent / 'data'

TYPE_MAP = {
    str: 'character varying',
    int: 'integer',
    float: 'numeric',
    bool: 'boolean',
}

class DemoConnector(BaseConnector):

    def test_connection(self) -> bool:
        logger.debug("Testing connection for DemoConnector")
        return True

    def discover_catalog(self) -> list[dict[str, Any]]:
        scenario = self.credentials['scenario']
        source = self.credentials['source']

        data_dir = PATH_TO_DATA_DIR / scenario
        files = sorted(data_dir.glob(f'{source}_*.json'))

        tables = []
        for file in files:
            table_name = file.stem.removeprefix(f'{source}_')
            rows = json.load(file.open('r'))
            first_row = rows[0]
            columns = [{'name': col, 'data_type': TYPE_MAP.get(type(value), 'character varying'), 'nullable': True, 'primary_key': False} for col, value in first_row.items()]
            tables.append({'name': table_name, 'table_type': 'BASE TABLE', 'columns': columns})
        return [{'name': source, 'tables': tables}]

    def get_table_metadata(self, schema_name: str, table_name: str) -> dict[str, Any]:
        scenario = self.credentials['scenario']
        source = self.credentials['source']
        path = PATH_TO_DATA_DIR / scenario / f'{source}_{table_name}.json'

        if not path.exists():
            logger.warning("Demo data file not found: %s", path)
            return {'row_count': None, 'column_stats': {}}
        with path.open('r') as f:
            rows = json.load(f)
        return {'row_count': len(rows), 'column_stats': {}}

