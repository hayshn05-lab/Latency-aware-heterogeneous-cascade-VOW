"""Config-driven bounded SQL export into an incremental research database."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
from .warehouse import WarehouseClient, canonical
from .research_db import ResearchDatabase

def export_pages(client, select_sql, order_by, page_size, consume):
    expected=int(client.query('SELECT count(*) AS n FROM ('+select_sql+') AS counted')[0]['n'])
    offset=0
    while offset < expected:
        sql=f'{select_sql} ORDER BY {order_by} LIMIT {page_size} OFFSET {offset}'
        rows=client.query(sql)
        if not rows or len(rows)>page_size or offset+len(rows)>expected:
            raise ValueError('Source count/pagination mismatch')
        consume(rows,sql)
        offset+=len(rows)
    if offset != expected:
        raise ValueError('Source count/pagination mismatch')
    return offset

def load_token(path):
    if os.environ.get('LUMID_PAT'):return os.environ['LUMID_PAT']
    if not Path(path).exists():return ''
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if line.strip().startswith('#') or '=' not in line:continue
        key,value=line.split('=',1)
        if key.strip()=='LUMID_PAT':return value.strip().strip('\"').strip("'")
    return ''

def run(config, *, offline=False, database=None, only=None):
    client=WarehouseClient(Path(config['cache']),token='' if offline else load_token('.env'),offline=offline)
    db=ResearchDatabase(database or config['database'])
    release=Path(config['release']);release.mkdir(parents=True,exist_ok=True)
    manifest_path=release/'data_manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'datasets':{},'requests':[]}
    manifest.update({'dataset_version':config['dataset_version'],'window':config['window'],'config_sha256':hashlib.sha256(canonical(config).encode()).hexdigest(),'database_schema_version':1})
    try:
        for spec in config['datasets']:
            if only and spec['kind'] not in only:continue
            def consume(rows,sql):
                db.ingest(spec['kind'],rows,hashlib.sha256(sql.encode()).hexdigest())
                print(spec['kind'], 'imported page',len(rows),flush=True)
            n=export_pages(client,spec['select_sql'],spec['order_by'],config['page_size'],consume)
            manifest['datasets'][spec['kind']]={'source_rows':n,'selection':spec['select_sql'],'complete':True}
            print(spec['kind'],'complete',n,flush=True)
        if not only:
            manifest['supplementary']={item['name']:client.query(item['sql']) for item in config.get('supplementary_queries',[])}
    finally:
        old={canonical(x['parameters']):x for x in manifest['requests']}
        old.update({canonical(x['parameters']):x for x in client.records})
        manifest['requests']=[old[k] for k in sorted(old)]
        manifest['database_counts']=db.counts()
        manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        db.close()
    return manifest

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--database')
    parser.add_argument('--only',nargs='+',choices=['markets','tweets','trades','books'])
    args=parser.parse_args()
    try:run(json.loads(Path(args.config).read_text()),offline=args.offline,database=args.database,only=args.only)
    except (RuntimeError,ValueError) as error:
        print(str(error));return 2
    return 0
