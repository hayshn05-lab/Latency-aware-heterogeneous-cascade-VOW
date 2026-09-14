"""Append-only, version-preserving SQLite research store (standard library)."""
import hashlib
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from .warehouse import canonical

def normalized_time(value):
    if not value:return None
    try:
        stamp=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if stamp.tzinfo is None:return None
        return stamp.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    except (ValueError,TypeError):return None

class ResearchDatabase:
    def __init__(self, path):
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        self.connection=sqlite3.connect(path)
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.connection.executescript('''
        CREATE TABLE IF NOT EXISTS records(
          kind TEXT NOT NULL, row_sha256 TEXT NOT NULL, entity_id TEXT,
          condition_id TEXT, asset_id TEXT, source_time TEXT, ingest_time TEXT,
          source TEXT, payload TEXT NOT NULL,
          PRIMARY KEY(kind,row_sha256));
        CREATE TABLE IF NOT EXISTS record_sources(
          kind TEXT NOT NULL,row_sha256 TEXT NOT NULL,query_sha256 TEXT NOT NULL,
          PRIMARY KEY(kind,row_sha256,query_sha256),
          FOREIGN KEY(kind,row_sha256) REFERENCES records(kind,row_sha256));
        CREATE INDEX IF NOT EXISTS record_asset_time ON records(kind,asset_id,source_time);
        CREATE INDEX IF NOT EXISTS record_condition_time ON records(kind,condition_id,source_time);
        CREATE INDEX IF NOT EXISTS record_entity ON records(kind,entity_id);
        CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
        INSERT OR IGNORE INTO schema_version VALUES(1);
        ''')
        for kind in ('markets','tweets','trades','books'):
            self.connection.execute(f'CREATE VIEW IF NOT EXISTS {kind} AS SELECT * FROM records WHERE kind=\'{kind}\'')

    def ingest(self,kind,rows,query_sha256):
        if kind not in {'markets','tweets','trades','books'}:
            raise ValueError('Unknown record kind')
        with self.connection:
            for row in rows:
                payload=canonical(row)
                digest=hashlib.sha256(payload.encode()).hexdigest()
                entity=row.get('tweet_id') if kind=='tweets' else row.get('id') if kind=='markets' else row.get('trade_id') if kind=='trades' else row.get('hash')
                stamp=row.get('created_at') if kind=='tweets' else row.get('ts') if kind=='trades' else row.get('snapshot_ts') if kind=='books' else row.get('market_created_at')
                self.connection.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(kind,row_sha256) DO UPDATE SET source_time=excluded.source_time,ingest_time=excluded.ingest_time',
                    (kind,digest,entity,row.get('condition_id'),row.get('asset_id'),normalized_time(stamp),normalized_time(row.get('ingest_ts')),row.get('source'),payload))
                self.connection.execute('INSERT OR IGNORE INTO record_sources VALUES(?,?,?)',(kind,digest,query_sha256))

    def counts(self):
        return dict(self.connection.execute('SELECT kind,count(*) FROM records GROUP BY kind ORDER BY kind'))

    def close(self):
        self.connection.close()
