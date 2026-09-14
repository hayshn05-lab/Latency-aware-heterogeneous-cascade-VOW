"""Structural replay readiness; never claims semantic links or executable profit."""
from bisect import bisect_right

def asof_status(rows, decision, max_age, *, provider):
    """Rows sorted by source time: (source_seconds, ingest_seconds, quality, signature)."""
    index=bisect_right(rows,decision,key=lambda row:row[0])-1
    selected=[]
    while index>=0:
        row=rows[index]
        if decision-row[0]>max_age:
            return ('stale',decision-row[0]) if not selected else _classify(selected,decision)
        if not provider or (row[1] is not None and row[1]<=decision):
            if selected and selected[0][0]!=row[0]:break
            selected.append(row)
        elif selected and selected[0][0]!=row[0]:break
        index-=1
    if selected:return _classify(selected,decision)
    return 'missing',None

def _classify(rows,decision):
    if len({row[3] for row in rows})>1:return 'conflict',decision-rows[0][0]
    return ('valid' if all(row[2]=='valid' for row in rows) else 'invalid'),decision-rows[0][0]
import argparse
import csv
import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from .replay_audit import normalize_market_tokens, parse_l2_snapshot, validate_book, ReplayValidationError
from .warehouse import canonical

def seconds(value):
    if not value:return None
    try:
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return dt.timestamp() if dt.tzinfo is not None else None
    except (ValueError,TypeError):return None

def precision_class(total, fractional):
    if not total:return 'unknown'
    if not fractional:return 'seconds_only_observed'
    if fractional==total:return 'fractional_only_observed'
    return 'mixed_seconds_and_fractional_observed'


def quantile(values,p):
    if not values:return None
    a=sorted(values);index=(len(a)-1)*p;lo=int(index);hi=min(lo+1,len(a)-1)
    return round(a[lo]+(a[hi]-a[lo])*(index-lo),6)

def csv_write(path,rows,fields):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def audit_database(database,release,window,settings):
    database=Path(database);release=Path(release);release.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(f'file:{database.as_posix()}?mode=ro',uri=True)
    try:
        counts=dict(conn.execute('SELECT kind,count(*) FROM records GROUP BY kind ORDER BY kind'))
        tweet_text_nonempty=conn.execute("SELECT count(*) FROM tweets WHERE length(trim(coalesce(json_extract(payload,'$.text'),'')))>0").fetchone()[0]
        distinct_tweet_ids=conn.execute('SELECT count(DISTINCT entity_id) FROM tweets').fetchone()[0]
        mappings={};families={};owners=defaultdict(set);conflicted_conditions=set();map_errors=Counter();meta_before=0;meta_created=0
        start=seconds(window['start']);end=seconds(window['end_exclusive'])
        for payload, in conn.execute("SELECT payload FROM markets"):
            row=json.loads(payload);cid=row.get('condition_id')
            if (seconds(row.get('ingest_ts')) or math.inf)<=start:meta_before+=1
            if seconds(row.get('market_created_at')) is not None:meta_created+=1
            try: mapping=normalize_market_tokens(row)
            except ReplayValidationError as error:map_errors[str(error)]+=1;continue
            cid=mapping['condition_id']
            pair=(mapping['yes_asset_id'],mapping['no_asset_id'])
            for label,asset in zip(('YES','NO'),pair):owners[asset].add((cid,label))
            if cid in mappings and mappings[cid]!=pair:
                map_errors['conflicting condition mapping']+=1;conflicted_conditions.add(cid);continue
            mappings[cid]=pair
            events=row.get('events') or []
            if isinstance(events,str):
                try:events=json.loads(events)
                except ValueError:events=[]
            ids=sorted({str(e['id']) for e in events if isinstance(e,dict) and e.get('id')}) if isinstance(events,list) else []
            families[cid]='event:'+','.join(ids) if ids else 'unverified:'+str(cid)
        ambiguous={asset for asset,values in owners.items() if len(values)!=1 or any(cid in conflicted_conditions for cid,label in values)}
        mappings={cid:pair for cid,pair in mappings.items() if cid not in conflicted_conditions and not any(a in ambiguous for a in pair)}
        series=defaultdict(list);quality=Counter();by_source=defaultdict(Counter);lags=[];invalid_times=0;book_fractional=0
        for payload, in conn.execute('SELECT payload FROM books'):
            row=json.loads(payload);ts=seconds(row.get('snapshot_ts'));ingest=seconds(row.get('ingest_ts'));asset=str(row.get('asset_id') or '')
            if ts is None:invalid_times+=1;continue
            if ts%1:book_fractional+=1
            if ingest is not None:lags.append(ingest-ts)
            try:
                book=parse_l2_snapshot(row);q=validate_book(book)
                sig=hashlib.sha256(canonical([book['bids'],book['asks'],book['tick_size'],book['min_order_size']]).encode()).hexdigest()
            except ReplayValidationError:
                q='malformed';sig=hashlib.sha256(canonical([row.get('bids'),row.get('asks')]).encode()).hexdigest()
            quality[q]+=1;by_source[str(row.get('source'))][q]+=1
            series[asset].append((ts,ingest,q,sig))
        assets=[]
        for asset,rows in series.items():
            rows.sort(key=lambda r:r[0]);unique=sorted({r[0] for r in rows});gaps=[b-a for a,b in zip(unique,unique[1:])]
            q=Counter(r[2] for r in rows)
            assets.append({'asset_id':asset,'rows':len(rows),'unique_times':len(unique),'valid_rows':q['valid'],'valid_fraction':round(q['valid']/len(rows),6),'gap_p50_seconds':quantile(gaps,.5),'gap_p95_seconds':quantile(gaps,.95),'gap_iqr_low':quantile(gaps,.25),'gap_iqr_high':quantile(gaps,.75),'mapping':'ambiguous' if asset in ambiguous else 'yes_no' if asset in owners else 'unmapped_or_other_outcome'})
        trade_canonical=0;trade_unmapped=0;trade_invalid=0;trade_fractional=0;trade_missing_time=0;trade_conditions=set();trade_assets=set();source_trade=Counter()
        for payload, in conn.execute('SELECT payload FROM trades'):
            row=json.loads(payload);asset=str(row.get('asset_id') or '');cid=row.get('condition_id');source_trade[str(row.get('source'))]+=1
            if cid:trade_conditions.add(cid)
            if asset:trade_assets.add(asset)
            ts=seconds(row.get('ts'))
            if ts is None:trade_missing_time+=1
            elif ts%1:trade_fractional+=1
            if asset not in owners or asset in ambiguous:trade_unmapped+=1;continue
            mapped_cid,label=next(iter(owners[asset]))
            if cid and cid!=mapped_cid:trade_invalid+=1;continue
            price=row.get('price');size=row.get('size')
            if not isinstance(price,(int,float)) or not math.isfinite(price) or not 0<=price<=1 or not isinstance(size,(int,float)) or not math.isfinite(size) or size<=0:
                trade_invalid+=1;continue
            trade_canonical+=1
        posts={};tweet_lags=[];tweet_fractional=0;tweet_times_missing=0
        for entity,stamp,ingest in conn.execute('SELECT entity_id,source_time,ingest_time FROM tweets'):
            ts=seconds(stamp);available=seconds(ingest)
            if ts is None:tweet_times_missing+=1;continue
            if ts%1:tweet_fractional+=1
            if available is not None:tweet_lags.append(available-ts)
            if start<=ts and ts+max(settings['offsets_seconds'])<end:posts[str(entity)]=ts
        ordered=sorted(posts.items(),key=lambda p:(p[1],p[0]));n=min(settings['sample_events'],len(ordered))
        sampled=[ordered[(i*len(ordered))//n] for i in range(n)] if n else []
        both={cid:pair for cid,pair in mappings.items() if all(asset in series for asset in pair)}
        any_books=sum(any(a in series for a in pair) for pair in mappings.values())
        structural=[];totals={'exchange':Counter(),'provider':Counter()};complete={'exchange':0,'provider':0};family_rates=defaultdict(list)
        for cid,pair in sorted(both.items()):
            successes={mode:0 for mode in totals}
            for _,ts in sampled:
                for mode in totals:
                    statuses=[asof_status(series[a],ts+offset,settings['max_age_seconds'],provider=mode=='provider')[0] for offset in settings['offsets_seconds'] for a in pair]
                    totals[mode].update(statuses)
                    if all(s=='valid' for s in statuses):successes[mode]+=1;complete[mode]+=1
            fraction=successes['provider']/n if n else 0
            family_rates[families[cid]].append(fraction)
            structural.append({'condition_id':cid,'family_id':families[cid],'sampled_posts':n,'exchange_complete':successes['exchange'],'provider_complete':successes['provider'],'provider_complete_fraction':round(fraction,6)})
        verified_family_rates=[sum(rates)/len(rates) for family,rates in family_rates.items() if not family.startswith('unverified:')]
        summary={'window':window,'database_counts':counts,'tweet_text_nonempty':tweet_text_nonempty,'distinct_tweet_ids':distinct_tweet_ids,'mapped_yes_no_markets':len(mappings),'mapping_exclusions':dict(map_errors),'ambiguous_assets':len(ambiguous),'metadata_ingested_by_window_start':meta_before,'metadata_with_created_time':meta_created,
          'book_quality':dict(quality),'book_sources':{k:dict(v) for k,v in sorted(by_source.items())},'book_assets':len(series),'book_invalid_timestamp_rows':invalid_times,'book_assets_not_in_yes_no_map':sum(a not in owners for a in series),
          'trade_sources':dict(source_trade),'trade_condition_ids':len(trade_conditions),'trade_assets':len(trade_assets),'trade_yes_probability_canonicalizable':trade_canonical,'trade_unmapped_or_other_outcome':trade_unmapped,'trade_invalid_or_mapping_conflict':trade_invalid,'trade_conditions_missing_from_yes_no_map':len(trade_conditions-set(mappings)),
          'any_token_book_markets':any_books,'both_token_book_markets':len(both),'sampled_post_count':n,'sampling':'uniform deterministic chronological unique-post indices; structural cross-product, NOT semantic links',
          'structural_pairs_evaluated':n*len(both),'structural_pairs_complete_exchange':complete['exchange'],'structural_pairs_complete_provider':complete['provider'],'asof_states':{k:dict(v) for k,v in totals.items()},'settings':settings,
          'source_timestamp_precision':{'classification':{'tweets':precision_class(counts.get('tweets',0)-tweet_times_missing,tweet_fractional),'trades':precision_class(counts.get('trades',0)-trade_missing_time,trade_fractional),'books':precision_class(counts.get('books',0)-invalid_times,book_fractional)},'trade_missing_time_rows':trade_missing_time,'tweet_fractional_rows':tweet_fractional,'tweet_missing_time_rows':tweet_times_missing,'trade_fractional_rows':trade_fractional,'book_fractional_rows':book_fractional,'subsecond_end_to_end_identifiable':False},
          'ingest_lag_seconds':{'tweets_p50':quantile(tweet_lags,.5),'tweets_p95':quantile(tweet_lags,.95),'books_p50':quantile(lags,.5),'books_p95':quantile(lags,.95),'negative_tweet_lags':sum(x<0 for x in tweet_lags),'negative_book_lags':sum(x<0 for x in lags)},
          'family_cluster_summary':{'known_families':len(verified_family_rates),'unverified_family_groups':sum(k.startswith('unverified:') for k in family_rates),'metric':'mean provider complete-pair fraction per metadata event family, conditional on both-token book coverage','iqr_low':quantile(verified_family_rates,.25),'median':quantile(verified_family_rates,.5),'iqr_high':quantile(verified_family_rates,.75),'interpretation':'descriptive IQR, not confidence interval; event-family assignments require validation'},
          'strict_h2_semantic_pairs':0,'execution_ready':False,'missing_gates':['independently verified semantic post-market links','historical indexed/open eligibility and metadata revisions','documented full snapshot/stream continuity','frozen fee, order-size, capital and exit rules','family-separated temporal evaluation and measured signal availability'],
          'evidence':'D0 structural coverage; mapped trades can support H0 non-executable price-state proxies; no executable PnL'}
        summary['coverage_fractions']={'canonicalizable_trades':round(trade_canonical/counts.get('trades',1),6) if counts.get('trades') else None,'valid_book_rows':round(quality['valid']/counts.get('books',1),6) if counts.get('books') else None,'both_book_markets_of_mapped':round(len(both)/len(mappings),6) if mappings else None,'provider_complete_of_evaluated_pairs':round(complete['provider']/(n*len(both)),6) if n and both else None}
        csv_write(release/'book_asset_coverage.csv',sorted(assets,key=lambda r:r['asset_id']),['asset_id','rows','unique_times','valid_rows','valid_fraction','gap_p50_seconds','gap_p95_seconds','gap_iqr_low','gap_iqr_high','mapping'])
        csv_write(release/'structural_replay_pairs.csv',structural,['condition_id','family_id','sampled_posts','exchange_complete','provider_complete','provider_complete_fraction'])
        (release/'replay_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        return summary
    finally:conn.close()

def require_complete_release(config):
    path=Path(config['release'])/'data_manifest.json'
    if not path.exists():raise ValueError('Acquisition manifest is missing or incomplete')
    manifest=json.loads(path.read_text(encoding='utf-8'))
    for spec in config['datasets']:
        entry=manifest.get('datasets',{}).get(spec['kind'],{})
        if not entry.get('complete'):raise ValueError('Acquisition is incomplete: '+spec['kind'])
        if entry.get('selection')!=spec['select_sql']:raise ValueError('Acquisition selection differs from audit config')
    return manifest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);args=parser.parse_args()
    config=json.loads(Path(args.config).read_text())
    require_complete_release(config)
    summary=audit_database(config['database'],config['release'],config['window'],config['audit'])
    print(json.dumps({'database_counts':summary['database_counts'],'both_token_book_markets':summary['both_token_book_markets'],'execution_ready':summary['execution_ready']},sort_keys=True))
    return 0
