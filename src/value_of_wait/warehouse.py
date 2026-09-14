"""Read-only SQL retrieval with immutable local materializations."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

BASE = 'https://lum.id/findata'

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

def _transport(url, body, headers):
    with urlopen(Request(url, data=body, headers=headers), timeout=45) as response:
        return response.read()

class WarehouseClient:
    def __init__(self, cache: Path, *, token='', offline=False, transport=_transport):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.token = token
        self.offline = offline
        self.transport = transport
        self.records = []

    def query(self, sql):
        key = hashlib.sha256(sql.encode()).hexdigest()
        metadata = self.cache / (key + '.json')
        if metadata.exists():
            record = json.loads(metadata.read_text(encoding='utf-8'))
            body = (self.cache / record['body_file']).read_bytes()
            if hashlib.sha256(body).hexdigest() != record['response_sha256']:
                raise ValueError('Cached response checksum mismatch')
        else:
            if self.offline:
                raise ValueError('Required SQL materialization is absent from offline cache')
            if not self.token:
                raise ValueError('Findata authentication is not configured')
            headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type':'application/json'}
            try:
                result = json.loads(self.transport(BASE + '/retrieve', canonical({'sql':sql,'output_format':'jsonl'}).encode(), headers))
                uri = result['materialized_uri']
                if not re.fullmatch(r'/blobs/retrievals/[A-Za-z0-9-]+/result\.jsonl', uri):
                    raise ValueError('Unsafe materialization path')
                body = self.transport(BASE + uri, None, headers)
            except ValueError as error:
                if str(error) == 'Unsafe materialization path':
                    raise ValueError('Unsafe materialization path') from None
                raise RuntimeError('Findata returned invalid materialization metadata') from None
            except Exception as error:
                status = getattr(error, 'code', None)
                raise RuntimeError('Findata SQL retrieval failed' + (f' (HTTP {status})' if status else '')) from None
            rows = [json.loads(line) for line in body.split(b'\n') if line.strip()]
            if len(rows) != result['rowcount']:
                raise ValueError('Materialized row count does not match response')
            if self.token.encode() in body:
                raise ValueError('Credential-bearing response rejected')
            digest = hashlib.sha256(body).hexdigest()
            body_file = digest + '.jsonl'
            record = {'endpoint':'/retrieve', 'parameters':{'sql':sql,'output_format':'jsonl'}, 'rows':len(rows),
                      'response_sha256':digest, 'body_file':body_file,
                      'retrieved_at':datetime.now(timezone.utc).isoformat()}
            (self.cache / body_file).write_bytes(body)
            metadata.write_text(canonical(record) + '\n', encoding='utf-8')
        self.records.append(record)
        return [json.loads(line) for line in body.split(b'\n') if line.strip()]
