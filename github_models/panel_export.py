"""Offline MultiModel panel bundle v1. No provider calls; no model changes."""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

SCHEMA = 'multimodel-panel-v1'
SECTIONS = set('FIXTURES FORECASTS ODDS RESULTS AUDIT CALIBRATION_READINESS CALIBRATION_EXPERIMENTS MODEL_VERSIONS SOURCE_HEALTH'.split())
MAX_BYTES = 100_000_000

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def stamp(s):
    t = datetime.fromisoformat(s.replace('Z', '+00:00'))
    require(t.tzinfo is not None, 'naive_timestamp')
    return t

def digest(b):
    return hashlib.sha256(b).hexdigest()

def encode(d):
    return json.dumps(d, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def decode(b):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'duplicate_json_key')
            out[k] = v
        return out
    def invalid(x):
        raise ValueError('nonfinite_json')
    return json.loads(b, object_pairs_hook=pairs, parse_constant=invalid)

def inspect_zip(z):
    names = z.namelist()
    require(len(names) == len(set(names)), 'duplicate_zip_member')
    require(sum(x.file_size for x in z.infolist()) <= MAX_BYTES, 'zip_size_limit')
    require(z.testzip() is None, 'zip_crc_error')

def build(abc_path, odds_path, audit_path, day, run_ids, out):
    require(set(run_ids) == {'abc','odds','audit'} and all(type(v) is int and v > 0 for v in run_ids.values()), 'source_run_ids_required')
    prefix = 'reports/github_models/'
    sources = {}
    with ZipFile(abc_path) as a, ZipFile(odds_path) as o, ZipFile(audit_path) as u:
        for role, z in [('abc',a),('odds',o),('audit',u)]:
            inspect_zip(z)
            sources[role] = {'run_id':run_ids[role], 'zip_sha256':digest(Path(z.filename).read_bytes()), 'members':{}}
        def get(role, z, name, schema=None):
            b=z.read(name); d=decode(b)
            require(schema is None or (isinstance(d,dict) and d.get('schema')==schema), 'unsupported_source_schema:'+name)
            sources[role]['members'][name]=digest(b)
            return d
        q=get('abc',a,prefix+'queues/'+day+'.json','github-models-fixture-queue-v1')
        oq=get('odds',o,'pitch_queue.json','github-models-fixture-queue-v1')
        require(q==oq,'queue_mismatch')
        cutoff=q['generated_at_utc']; cut=stamp(cutoff)
        require(cut.astimezone(__import__('zoneinfo').ZoneInfo('Europe/Warsaw')).date().isoformat()==day,'day_mismatch')
        fixtures={r['fixture_id']:r for r in q['fixtures']}
        require(len(fixtures)==len(q['fixtures']), 'duplicate_fixture')
        def check(r, frozen, probs):
            f=fixtures.get(r['fixture_id']); require(f is not None,'unknown_fixture')
            require(stamp(frozen)==cut and cut<stamp(f['kickoff_utc']),'invalid_freeze')
            if 'kickoff_utc' in r:
                require(stamp(r['kickoff_utc'])==stamp(f['kickoff_utc']),'kickoff_mismatch')
            require(all(type(p) in (int,float) and math.isfinite(p) and 0<=p<=1 for p in probs),'invalid_probability')
        pred=get('abc',a,prefix+'predictions/'+day+'.json','github-models-independent-predictions-v1')
        markets=get('abc',a,prefix+'markets/'+day+'.json')
        abc=get('abc',a,prefix+'filters/ABC_'+day+'.json','github-models-abc-v1')
        shadow=get('abc',a,prefix+'shadow/'+day+'.json')
        for d in (pred,markets,shadow): require(stamp(d['generated_at_utc'])==cut,'source_cutoff_mismatch')
        require(stamp(abc['input_cutoff_utc'])==cut,'abc_cutoff_mismatch')
        for r in pred['predictions']: check(r,r['frozen_at_utc'],[r[k] for k in ('p_home','p_draw','p_away')])
        for r in markets['markets']+shadow['candidates']: check(r,r['frozen_at_utc'],[r['probability']])
        for r in abc['candidates']: check(r,cutoff,[r.get('probability',r.get('probability_min'))])
        overlay=get('odds',o,'market_overlay.json','github-models-oddspapi-market-comparison-v1')
        so=get('odds',o,'SHADOW_SUPERBET_OVERLAY.json','multimodel-v2-shadow-superbet-overlay-v1')
        require(overlay['bookmakers']==['superbet.pl'] and overlay['research_only'] is True and so['bookmaker']=='superbet.pl' and stamp(so['forecast_cutoff_utc'])==cut,'odds_provenance')
        for rows,price,when,freeze,prob in [(overlay['comparisons'],'price','odds_captured_at_utc','forecast_frozen_at_utc','p_model'),(so['rows'],'odds','price_captured_at_utc','frozen_at_utc','probability')]:
            for r in rows:
                check(r,r[freeze],[r[prob]])
                require(r['bookmaker']=='superbet.pl','wrong_bookmaker')
                if r.get(price) is not None:
                    require(type(r[price]) in (int,float) and math.isfinite(r[price]) and r[price]>1,'invalid_odds')
                    require(stamp(r[when])<stamp(fixtures[r['fixture_id']]['kickoff_utc']),'postkickoff_odds')
                    if price=='odds': require(r['status']=='quoted_research','unverified_shadow_quote')
        replay=get('audit',u,'REPLAY_AUDIT.json','github-models-oddspapi-frozen-audit-v1')
        priced=get('audit',u,'PRICED_SHADOW_SETTLEMENT.json','multimodel-priced-shadow-outcomes-v1')
        readiness=get('audit',u,'MULTIMODEL_CALIBRATION_READINESS.json','multimodel-calibration-readiness-v1')
        require(readiness['source_replay_as_of_utc']==replay['as_of_utc'] and readiness['source_shadow_as_of_utc']==priced['as_of_utc'],'audit_cutoff_mismatch')
        require(readiness['calibration_authorized'] is False,'unsupported_calibration_authorization')
        health={'abc':get('abc',a,prefix+'coverage/CYCLE_SOURCE_HEALTH_'+day+'.json'), 'odds':get('odds',o,'market_health.json'), 'disciplinary':get('audit',u,'DISCIPLINARY_SOURCE_COVERAGE.json'), 'audit_sources':get('audit',u,'outcomes/source_manifest.json'), 'issues':[]}
        name=prefix+'api_final_manifest.json'
        if name in a.namelist():
            try: health['api_final_manifest']=get('abc',a,name)
            except (ValueError,UnicodeError): health['issues'].append({'source':name,'status':'invalid_json','sha256':digest(a.read(name))})
        else: health['issues'].append({'source':name,'status':'missing'})
        sections={'FIXTURES':q,'FORECASTS':{'predictions':pred,'markets':markets,'abc':abc,'shadow':shadow,'score_67_status':'not_computed','top_status':'blocked_missing_quality_score'},'ODDS':{'abc_comparisons':overlay,'shadow_comparisons':so,'gaps':get('odds',o,'market_gaps.json'),'minimum_view_odds':1.2,'automatic_forecast_join':False},'RESULTS':{'source_results':get('abc',a,'data/github_models/settlement_verified_results.json'),'source_events':get('abc',a,'data/github_models/settlement_verified_events.json'),'identity_status':'source_ids_not_automatically_joined','exact_shadow_outcomes':priced['entries']},'AUDIT':{'abc':get('abc',a,prefix+'filters/AUDIT_'+day+'.json'),'shadow':get('abc',a,prefix+'shadow/SHADOW_AUDIT_'+day+'.json'),'priced_abc':replay,'priced_shadow':priced},'CALIBRATION_READINESS':readiness,'CALIBRATION_EXPERIMENTS':{'status':'not_available','experiments':[]},'MODEL_VERSIONS':{'status':'partial','observed':sorted({(r['model_id'],r['model_version']) for r in pred['predictions']}),'history_available':False},'SOURCE_HEALTH':health}
    payload={k+'.json':encode(v) for k,v in sections.items()}
    manifest={'schema':SCHEMA,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'forecast_cutoff_utc':cutoff,'day':day,'audit_as_of_utc':max(replay['as_of_utc'],priced['as_of_utc'],key=stamp),'sources':sources,'source_run_ids_attestation':'caller_supplied','files':{k:{'sha256':digest(v),'bytes':len(v)} for k,v in payload.items()},'historical_snapshot':True,'publication':'local_only'}
    out=Path(out); tmp=out.with_suffix(out.suffix+'.tmp')
    try:
        with ZipFile(tmp,'w',ZIP_DEFLATED) as z:
            for k,v in payload.items(): z.writestr(k,v)
            z.writestr('MANIFEST.json',encode(manifest))
        verify(tmp)
        tmp.replace(out)
    finally:
        if tmp.exists(): tmp.unlink()
    return manifest

def verify(path, previous=None):
    with ZipFile(path) as z:
        inspect_zip(z)
        m=decode(z.read('MANIFEST.json'))
        require(m['schema']==SCHEMA,'unsupported_bundle_schema')
        expected={k+'.json' for k in SECTIONS}
        require(set(m['files'])==expected and set(z.namelist())==expected|{'MANIFEST.json'},'unexpected_bundle_files')
        for name,meta in m['files'].items():
            b=z.read(name);require(len(b)==meta['bytes'] and digest(b)==meta['sha256'],'bundle_integrity:'+name);decode(b)
        if previous:
            for field in ('forecast_cutoff_utc','audit_as_of_utc'):
                require(stamp(m[field])>=stamp(previous[field]),'older_snapshot:'+field)
        return m

def main():
    p=argparse.ArgumentParser(); p.add_argument('--abc',required=True);p.add_argument('--odds',required=True);p.add_argument('--audit',required=True);p.add_argument('--day',required=True);p.add_argument('--abc-run',type=int,required=True);p.add_argument('--odds-run',type=int,required=True);p.add_argument('--audit-run',type=int,required=True);p.add_argument('--out',required=True);x=p.parse_args()
    build(x.abc,x.odds,x.audit,x.day,{'abc':x.abc_run,'odds':x.odds_run,'audit':x.audit_run},x.out)
if __name__=='__main__': main()
