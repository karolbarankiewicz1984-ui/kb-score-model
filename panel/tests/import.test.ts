import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import JSZip from 'jszip';
import {readBundle,strictJson,compare,preflight} from '../src/import.ts';
import {SECTIONS} from '../src/types.ts';
const cutoff='2026-11-24T12:00:00Z', kickoff='2026-11-24T20:00:00Z';
function data(){
 const row={fixture_id:'synthetic-f1',market:'goals',selection:'over',line:2.5,variant:'A',model:'synthetic-model',probability:0.75};
 return {FIXTURES:{schema:'github-models-fixture-queue-v1',generated_at_utc:cutoff,fixtures:[{fixture_id:row.fixture_id,home:'Test A',away:'Test B',league:'Test',kickoff_utc:kickoff}]},
 FORECASTS:{abc:{schema:'github-models-abc-v1',input_cutoff_utc:cutoff,candidates:[row]},shadow:{schema:'multimodel-v2-shadow-markets-v1',generated_at_utc:cutoff,candidates:[]},markets:{schema:'github-models-event-markets-v1',generated_at_utc:cutoff,markets:[]},predictions:{schema:'github-models-independent-predictions-v1',generated_at_utc:cutoff,predictions:[]}},
 ODDS:{panel_links:{schema:'multimodel-panel-links-v1',research_view_only:true,rows:[{...row,forecast_identity:['ABC',row.fixture_id,row.market,row.selection,row.line,row.model,row.variant,cutoff],lane:'ABC',probability_status:'uncalibrated_research',quality_score:null,top_eligible:false,quote:{price:1.2,captured_at_utc:'2026-11-24T13:00:00Z',bookmaker:'superbet.pl',source_market_id:'test',source_outcome_id:'test'},quote_status:'archived_research_quote'}]}},
 RESULTS:{},AUDIT:{},CALIBRATION_READINESS:{schema:'multimodel-calibration-readiness-v1',calibration_authorized:false,distinct_fixtures_used_for_gate:0,fixtures_remaining_to_100_review:100,abc_distinct_settled_fixtures:0,shadow_distinct_settled_fixtures:0,abc_settled_quotes:0,shadow_settled_quotes:0,holdout_evidence_available:false,exact_cross_model_fixture_union_verified:false},CALIBRATION_EXPERIMENTS:{},MODEL_VERSIONS:{},SOURCE_HEALTH:{}};
}
async function pack(sections=data(),options:{tamper?:boolean;extra?:boolean;schema?:string;duplicate?:boolean}={}){
 const zip=new JSZip(), files:Record<string,{bytes:number;sha256:string}>={};
 for(const s of SECTIONS){const name=s+'.json',text=options.duplicate&&s==='SOURCE_HEALTH'?'{"a":1,"a":2}':JSON.stringify(sections[s]);files[name]={bytes:Buffer.byteLength(text),sha256:createHash('sha256').update(text).digest('hex')};zip.file(name,options.tamper&&s==='SOURCE_HEALTH'?text+' ':text);}
 const manifest={schema:options.schema||'multimodel-panel-v1',day:'2026-11-24',forecast_cutoff_utc:cutoff,audit_as_of_utc:'2026-11-25T12:00:00Z',generated_at_utc:'2026-11-25T13:00:00Z',historical_snapshot:true,publication:'local_only',files};
 zip.file('MANIFEST.json',JSON.stringify(manifest));if(options.extra)zip.file('unexpected.json','{}');return zip.generateAsync({type:'arraybuffer',compression:'DEFLATE'});
}
test('valid source bundle and exact 1.20',async()=>{const s=await readBundle(await pack());assert.equal(s.rows.length,1);assert.equal(s.rows[0].quote?.price,1.2);assert.equal(s.rows[0].top_eligible,false);});
test('checksum mismatch',async()=>{await assert.rejects(readBundle(await pack(data(),{tamper:true})),/SHA-256/);});
test('extra member',async()=>{await assert.rejects(readBundle(await pack(data(),{extra:true})),/ZIP/);});
test('wrong schema',async()=>{await assert.rejects(readBundle(await pack(data(),{schema:'unknown'})),/schemat/);});
test('duplicate JSON keys including escaped equivalents',async()=>{assert.throws(()=>strictJson(new TextEncoder().encode('{"a":1,"\\u0061":2}')),/Zduplikowany/);await assert.rejects(readBundle(await pack(data(),{duplicate:true})),/Zduplikowany/);});
test('nonfinite numbers',()=>assert.throws(()=>strictJson(new TextEncoder().encode('{"v":1e999}')),/Nieskończona/));
test('unrelated forecast identity',async()=>{const s=data();s.ODDS.panel_links.rows[0].line=3.5;await assert.rejects(readBundle(await pack(s)),/powiązanie/);});
test('post-kickoff quote',async()=>{const s=data();s.ODDS.panel_links.rows[0].quote.captured_at_utc=kickoff;await assert.rejects(readBundle(await pack(s)),/kurs/);});
test('before-freeze quote',async()=>{const s=data();s.ODDS.panel_links.rows[0].quote.captured_at_utc='2026-11-24T11:00:00Z';await assert.rejects(readBundle(await pack(s)),/kurs/);});
test('duplicate fixture',async()=>{const s=data();s.FIXTURES.fixtures.push(s.FIXTURES.fixtures[0]);await assert.rejects(readBundle(await pack(s)),/Powielony/);});
test('no unauthorized calibration',async()=>{const s=data();s.CALIBRATION_READINESS.calibration_authorized=true;await assert.rejects(readBundle(await pack(s)),/kalibracja/);});
test('no rollback or equal-date conflicts',async()=>{const s=await readBundle(await pack());const m=s.manifest;compare(m,m);assert.throws(()=>compare(m,{...m,forecast_cutoff_utc:'2026-11-25T12:00:00Z'}),/Starsza/);assert.throws(()=>compare(m,{...m,audit_as_of_utc:'2026-11-26T12:00:00Z'}),/Starsza/);assert.throws(()=>compare(m,{...m,files:{...m.files,'FIXTURES.json':{bytes:0,sha256:'x'}}}),/Konflikt/);});
test('reject broken zip',()=>assert.throws(()=>preflight(new ArrayBuffer(100)),/katalog/));
