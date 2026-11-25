import JSZip from 'jszip';
import { SECTIONS } from './types.ts';
import type { Manifest, Snapshot, Section, Fixture, LinkRow, Readiness } from './types.ts';
const names = [...SECTIONS.map(x=>x+'.json'),'MANIFEST.json'].sort();
const LIMIT=100_000_000;
export function ensure(ok:unknown,msg:string): asserts ok {if(!ok)throw new Error(msg);}
function obj(x:unknown):Record<string,unknown>{ensure(x!==null&&typeof x==='object'&&!Array.isArray(x),'Niepoprawna struktura obiektu');return x as Record<string,unknown>;}
function array(x:unknown):unknown[]{ensure(Array.isArray(x),'Brak wymaganej listy');return x;}
function str(x:unknown):string{ensure(typeof x==='string'&&x.length>0,'Brak tekstu źródłowego');return x;}
function num(x:unknown):number{ensure(typeof x==='number'&&Number.isFinite(x),'Niepoprawna liczba');return x;}
function count(x:unknown):number{const n=num(x);ensure(Number.isSafeInteger(n)&&n>=0,'Niepoprawny licznik');return n;}
function time(x:unknown):number{const s=str(x);ensure(/(?:Z|[+-]\d\d:\d\d)$/.test(s),'Brak strefy czasowej');const n=Date.parse(s);ensure(Number.isFinite(n),'Niepoprawna data');return n;}
function p(x:unknown):number{const n=num(x);ensure(n>=0&&n<=1,'Prawdopodobieństwo poza zakresem');return n;}
function equal(a:unknown,b:unknown){return JSON.stringify(a)===JSON.stringify(b);}
export function preflight(buffer:ArrayBuffer){
 const v=new DataView(buffer),n=v.byteLength;
 ensure(n>=22&&n<=LIMIT,'Niepoprawny rozmiar ZIP');
 let end=-1;
 for(let i=n-22;i>=Math.max(0,n-65557);i--){if(v.getUint32(i,true)===0x06054b50&&i+22+v.getUint16(i+20,true)===n){end=i;break;}}
 ensure(end>=0,'Brak katalogu ZIP');
 ensure(v.getUint16(end+4,true)===0&&v.getUint16(end+6,true)===0&&v.getUint16(end+8,true)===names.length&&v.getUint16(end+10,true)===names.length,'Nieobsługiwany ZIP');
 const size=v.getUint32(end+12,true),start=v.getUint32(end+16,true);
 ensure(start+size===end,'Nieprawidłowy katalog ZIP');
 const dec=new TextDecoder('utf-8',{fatal:true}),seen=new Set<string>();let offset=start,total=0;
 for(let i=0;i<names.length;i++){
  ensure(offset+46<=end&&v.getUint32(offset,true)===0x02014b50,'Niepoprawny nagłówek ZIP');
  const flags=v.getUint16(offset+8,true),method=v.getUint16(offset+10,true),compressed=v.getUint32(offset+20,true),raw=v.getUint32(offset+24,true),nl=v.getUint16(offset+28,true),extra=v.getUint16(offset+30,true),comment=v.getUint16(offset+32,true),local=v.getUint32(offset+42,true);
  ensure((flags&1)===0&&(method===0||method===8)&&v.getUint16(offset+34,true)===0,'Nieobsługiwany format kompresji');
  ensure(offset+46+nl+extra+comment<=end&&raw<=LIMIT&&compressed<=LIMIT,'Zbyt duży wpis ZIP');
  const name=dec.decode(new Uint8Array(buffer,offset+46,nl));
  ensure(names.includes(name)&&!seen.has(name),'Obcy lub zduplikowany plik: '+name);seen.add(name);
  ensure(local+30<=start&&v.getUint32(local,true)===0x04034b50,'Brak nagłówka lokalnego');
  const ln=v.getUint16(local+26,true),lx=v.getUint16(local+28,true);
  ensure(local+30+ln+lx+compressed<=start&&dec.decode(new Uint8Array(buffer,local+30,ln))===name,'Niezgodny nagłówek ZIP');
  total+=raw;ensure(total<=LIMIT,'Pakiet przekracza limit 100 MB');offset+=46+nl+extra+comment;
 }
 ensure(offset===end,'Niezgodny katalog ZIP');
}
export function strictJson(bytes:Uint8Array):unknown{
 const s=new TextDecoder('utf-8',{fatal:true}).decode(bytes);let i=0;
 const ws=()=>{while(i<s.length&&/\s/.test(s[i]))i++;};
 function string(){ensure(s[i]==='"','Niepoprawny klucz JSON');const start=i++;while(i<s.length){const ch=s[i++];if(ch==='\\'){i++;continue;}if(ch==='"')return JSON.parse(s.slice(start,i)) as string;}throw new Error('Niepełny JSON');}
 function value(depth:number){ensure(depth<=100,'Zbyt głęboki JSON');ws();const ch=s[i];
 if(ch==='{'){i++;ws();const keys=new Set<string>();if(s[i]==='}'){i++;return;}for(;;){ws();const k=string();ensure(!keys.has(k),'Zduplikowany klucz JSON');keys.add(k);ws();ensure(s[i++]===':','Niepoprawny JSON');value(depth+1);ws();if(s[i]==='}'){i++;return;}ensure(s[i++]===',','Niepoprawny JSON');}}
 else if(ch==='['){i++;ws();if(s[i]===']'){i++;return;}for(;;){value(depth+1);ws();if(s[i]===']'){i++;return;}ensure(s[i++]===',','Niepoprawny JSON');}}
 else if(ch==='"'){string();}else{const start=i;while(i<s.length&&!/[\s,\]}]/.test(s[i]))i++;const token=s.slice(start,i);const v=JSON.parse(token);ensure(typeof v!=='number'||Number.isFinite(v),'Nieskończona liczba JSON');}}
 value(0);ws();ensure(i===s.length,'Nadmiarowe dane JSON');return JSON.parse(s);
}
async function hash(b:Uint8Array){const h=await crypto.subtle.digest('SHA-256',new Uint8Array(b));return Array.from(new Uint8Array(h),x=>x.toString(16).padStart(2,'0')).join('');}
export function validate(manifest:unknown,sections:Record<Section,unknown>):Omit<Snapshot,'importedAt'>{
 const m=obj(manifest);ensure(m.schema==='multimodel-panel-v1'&&m.historical_snapshot===true&&m.publication==='local_only','Nieobsługiwany schemat pakietu');
 const cutoff=time(m.forecast_cutoff_utc);time(m.audit_as_of_utc);time(m.generated_at_utc);ensure(/^\d{4}-\d{2}-\d{2}$/.test(str(m.day)),'Niepoprawny dzień pakietu');
 const q=obj(sections.FIXTURES);ensure(q.schema==='github-models-fixture-queue-v1'&&time(q.generated_at_utc)===cutoff,'Niezgodna kolejka');
 const byId=new Map<string,Fixture>();
 const fixtures=array(q.fixtures).map(x=>{const a=obj(x),id=str(a.fixture_id);ensure(!byId.has(id),'Powielony identyfikator meczu');ensure(time(a.kickoff_utc)>cutoff,'Mecz przed zamrożeniem');str(a.home);str(a.away);str(a.league);const f=a as Fixture;byId.set(id,f);return f;});
 const fc=obj(sections.FORECASTS),abc=obj(fc.abc),sh=obj(fc.shadow),market=obj(fc.markets),pred=obj(fc.predictions);
 ensure(abc.schema==='github-models-abc-v1'&&sh.schema==='multimodel-v2-shadow-markets-v1'&&market.schema==='github-models-event-markets-v1'&&pred.schema==='github-models-independent-predictions-v1','Niezgodny schemat prognoz');
 ensure(time(abc.input_cutoff_utc)===cutoff&&[sh,market,pred].every(x=>time(x.generated_at_utc)===cutoff),'Niezgodny cutoff prognoz');
 const candidate=new Map<string,number>();
 for(const [lane,group] of [['ABC',abc],['SHADOW',sh]] as const)for(const x of array(group.candidates)){
  const a=obj(x),id=str(a.fixture_id);ensure(byId.has(id),'Nieznany mecz prognozy');
  const model=lane==='ABC'?(a.model||'elo-and-dixon-min-consensus'):a.model_id;
  const ident=[lane,id,str(a.market),str(a.selection),a.line??null,str(model),lane==='ABC'?str(a.variant):null,m.forecast_cutoff_utc];
  if(lane==='ABC')ensure(['A','B','C'].includes(str(a.variant)),'Nieznany wariant');
  else ensure(time(a.frozen_at_utc)===cutoff,'Niezgodny SHADOW freeze');
  const k=JSON.stringify(ident);ensure(!candidate.has(k),'Powielona prognoza');candidate.set(k,p(a.probability??a.probability_min));
 }
 for(const x of array(market.markets)){const a=obj(x);ensure(byId.has(str(a.fixture_id))&&time(a.frozen_at_utc)===cutoff,'Niezgodna prognoza rynku');p(a.probability);}
 for(const x of array(pred.predictions)){const a=obj(x);ensure(byId.has(str(a.fixture_id))&&time(a.frozen_at_utc)===cutoff,'Niezgodna prognoza 1X2');ensure(Math.abs(p(a.p_home)+p(a.p_draw)+p(a.p_away)-1)<1e-5,'Niepoprawne 1X2');}
 const odds=obj(sections.ODDS),links=obj(odds.panel_links);ensure(links.schema==='multimodel-panel-links-v1'&&links.research_view_only===true,'Brak bezpiecznych powiązań kursów');
 const seen=new Set<string>();
 const rows=array(links.rows).map(x=>{const a=obj(x),id=str(a.fixture_id),f=byId.get(id);ensure(f,'Nieznany mecz powiązania');
  ensure(a.lane==='ABC'||a.lane==='SHADOW','Nieznana ścieżka');str(a.market);str(a.selection);str(a.model);ensure(a.line===null||typeof a.line==='number'&&Number.isFinite(a.line),'Niepoprawna linia');
  const identity=[a.lane,id,a.market,a.selection,a.line,a.model,a.variant,m.forecast_cutoff_utc],k=JSON.stringify(identity);
  ensure(equal(a.forecast_identity,identity)&&!seen.has(k)&&candidate.has(k)&&candidate.get(k)===p(a.probability),'Niezgodne powiązanie prognozy');seen.add(k);
  ensure(a.top_eligible===false&&a.quality_score===null&&a.probability_status==='uncalibrated_research','Niedozwolona promocja prognozy');
  if(a.quote!==null){const v=obj(a.quote),price=num(v.price),captured=time(v.captured_at_utc);ensure(price>1&&v.bookmaker==='superbet.pl'&&captured>=cutoff&&captured<time(f.kickoff_utc),'Niepoprawny kurs');ensure(a.quote_status===(price>=1.2?'archived_research_quote':'below_minimum_odds'),'Niezgodny status kursu');if(a.lane==='ABC'){str(v.source_market_id);str(v.source_outcome_id);}}
  else ensure(['missing_verified_quote','ambiguous_quote'].includes(str(a.quote_status)),'Niepoprawny status braku kursu');
  return a as LinkRow;
 });
 ensure(seen.size===candidate.size,'Niekompletna lista powiązań');
 const cr=obj(sections.CALIBRATION_READINESS);ensure(cr.schema==='multimodel-calibration-readiness-v1'&&cr.calibration_authorized===false,'Nieuprawniona kalibracja');
 for(const k of ['distinct_fixtures_used_for_gate','fixtures_remaining_to_100_review','abc_distinct_settled_fixtures','shadow_distinct_settled_fixtures','abc_settled_quotes','shadow_settled_quotes'])count(cr[k]);
 ensure(typeof cr.holdout_evidence_available==='boolean'&&typeof cr.exact_cross_model_fixture_union_verified==='boolean','Brak statusu kalibracji');
 for(const s of SECTIONS)obj(sections[s]);
 return {manifest:m as Manifest,sections,fixtures,rows,readiness:cr as Readiness};
}
export function compare(next:Manifest,previous?:Manifest){if(!previous)return;for(const k of ['forecast_cutoff_utc','audit_as_of_utc'] as const)ensure(time(next[k])>=time(previous[k]),'Starsza migawka: '+k);if(time(next.forecast_cutoff_utc)===time(previous.forecast_cutoff_utc)&&time(next.audit_as_of_utc)===time(previous.audit_as_of_utc))ensure(names.filter(n=>n!=='MANIFEST.json').every(n=>next.files[n].sha256===previous.files[n].sha256&&next.files[n].bytes===previous.files[n].bytes),'Konflikt danych przy tym samym cutoff');}
export async function readBundle(buffer:ArrayBuffer,previous?:Manifest):Promise<Snapshot>{
 preflight(buffer);ensure(globalThis.crypto?.subtle,'Import wymaga HTTPS lub localhost');
 const z=await JSZip.loadAsync(buffer,{checkCRC32:true});ensure(equal(Object.keys(z.files).sort(),names),'Niezgodna zawartość ZIP');
 const m=obj(strictJson(await z.file('MANIFEST.json')!.async('uint8array')));const meta=obj(m.files);
 ensure(equal(Object.keys(meta).sort(),names.filter(n=>n!=='MANIFEST.json')),'Niezgodny manifest');
 const sections={} as Record<Section,unknown>;
 for(const s of SECTIONS){const name=s+'.json',entry=obj(meta[name]),b=await z.file(name)!.async('uint8array');ensure(b.length===count(entry.bytes)&&await hash(b)===entry.sha256,'Niezgodna suma SHA-256: '+name);sections[s]=strictJson(b);}
 const validated=validate(m,sections);compare(validated.manifest,previous);return {...validated,importedAt:new Date().toISOString()};
}
