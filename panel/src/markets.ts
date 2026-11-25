import type {Fixture,LinkRow,Snapshot} from './types.ts';
export const MARKET_ORDER=['1X2','double_chance','goals','btts','handicap','corners','fouls','cards','shots_total','shots_on_target'] as const;
export const MARKET_LABELS:Record<string,string>={'1X2':'Wynik 1X2',double_chance:'Podwójna szansa',goals:'Bramki',btts:'Obie drużyny strzelą',handicap:'Handicap',corners:'Rzuty rożne',fouls:'Faule',cards:'Kartki',shots_total:'Strzały ogółem',shots_on_target:'Strzały celne'};
export const marketLabel=(m:string)=>MARKET_LABELS[m]||m;
export function selectionLabel(m:string,s:string,line:number|null){
 const names:Record<string,string>={'1':'1 — gospodarze','X':'X — remis','2':'2 — goście','1X':'1X — gospodarze lub remis','X2':'X2 — remis lub goście','12':'12 — gospodarze lub goście',over:'Powyżej',under:'Poniżej',yes:'Tak',no:'Nie',home:'Gospodarze',away:'Goście'};
 const n=line===null?'':(m==='handicap'&&line>0?'+':'')+line.toLocaleString('pl-PL',{maximumFractionDigits:4});
 return [names[s]||s,n].filter(Boolean).join(' ');
}
type Obj=Record<string,unknown>;
const object=(v:unknown):Obj=>v&&typeof v==='object'&&!Array.isArray(v)?v as Obj:{};
const list=(v:unknown):Obj[]=>Array.isArray(v)?v.filter(x=>x&&typeof x==='object'&&!Array.isArray(x)):[];
const string=(v:unknown)=>typeof v==='string'?v:'';
const prob=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1;
const lineValue=(v:unknown):number|null=>typeof v==='number'&&Number.isFinite(v)?v:null;
export type RawMarket={fixture_id:string;market:string;selection:string;line:number|null;model:string;version:string;probability:number;frozen:string;scope:string;source:string;expectedRate:number|null};
export type Blocker={fixture_id:string;market:string;model:string;reason:string};
export type Evidence={fixture_id:string;market:string;selection:string;line:number|null;frozen:string;source_fixture_id:string;hit:boolean;goals:[number,number]|null;historical:boolean};
export function marketIndex(s:Snapshot|null){
 const raw=new Map<string,RawMarket[]>(), blockers=new Map<string,Blocker[]>(), evidence=new Map<string,Evidence[]>();
 if(!s)return {raw,blockers,evidence,partialDates:[] as string[],missingDates:[] as string[]};
 const fc=object(s.sections.FORECASTS),pr=object(fc.predictions),ev=object(fc.markets),sh=object(fc.shadow);
 const ids=new Set(s.fixtures.map(f=>f.fixture_id)),cut=Date.parse(s.manifest.forecast_cutoff_utc);
 function add(row:RawMarket){if(!ids.has(row.fixture_id)||Date.parse(row.frozen)!==cut||!prob(row.probability)||!row.model)return;const a=raw.get(row.fixture_id)||[];a.push(row);raw.set(row.fixture_id,a);}
 for(const x of list(pr.predictions))for(const [selection,key] of [['1','p_home'],['X','p_draw'],['2','p_away']])if(prob(x[key]))add({fixture_id:string(x.fixture_id),market:'1X2',selection,line:null,model:string(x.model_id),version:string(x.model_version),probability:x[key] as number,frozen:string(x.frozen_at_utc),scope:'match',source:'',expectedRate:null});
 for(const x of list(ev.markets)){if(!prob(x.probability)||typeof x.line!=='number'||!Number.isFinite(x.line)||!string(x.market)||!string(x.selection))continue;add({fixture_id:string(x.fixture_id),market:string(x.market),selection:string(x.selection),line:x.line,model:string(x.model_id),version:string(x.model_version),probability:x.probability,frozen:string(x.frozen_at_utc),scope:'match',source:string(x.source),expectedRate:typeof x.expected_rate==='number'&&Number.isFinite(x.expected_rate)?x.expected_rate:null});}
 for(const [group, fallback] of [[pr,'1X2'],[ev,''],[sh,'']] as const)for(const x of list(group.blockers)){const fid=string(x.fixture_id);if(!ids.has(fid))continue;const ms=Array.isArray(x.markets)?x.markets.filter(v=>typeof v==='string') as string[]:[string(x.market)||fallback];for(const market of ms){if(!market)continue;const a=blockers.get(fid)||[];a.push({fixture_id:fid,market,model:string(x.model),reason:string(x.reason)||'unknown'});blockers.set(fid,a);}}
 const results=object(s.sections.RESULTS);
 const source=object(object(s.sections.ODDS).panel_links);
 // Only exact historical evidence also present in independently resolved source rows.
 const identity=(x:Obj)=>JSON.stringify([x.fixture_id,x.market,x.selection,x.line??null,x.frozen_at_utc]);
 const byKey=new Map<string,Obj[]>();for(const x of list(results.exact_shadow_outcomes)){const k=identity(x),a=byKey.get(k)||[];a.push(x);byKey.set(k,a);}
 const seen=new Set<string>();for(const x of list(source.historical_shadow_evidence)){
  if(!Array.isArray(x.identity)||x.identity.length!==5||typeof x.hit!=='boolean'||x.official_payout_verified!==false||!string(x.source_fixture_id))continue;
  const [fid,m,sel,line,frozen]=x.identity;const k=JSON.stringify(x.identity),matches=byKey.get(k)||[];
  if(typeof fid!=='string'||!ids.has(fid)||typeof m!=='string'||typeof sel!=='string'||(line!==null&&(typeof line!=='number'||!Number.isFinite(line)))||typeof frozen!=='string'||!Number.isFinite(Date.parse(frozen))||seen.has(k)||matches.length!==1)continue;
  const v=matches[0];if(v.status!=='settled'||v.hit!==x.hit||v.source_fixture_id!==x.source_fixture_id||v.official_bookmaker_settlement_verified!==false||v.market_identity!=='exact_quote_research_only'||Date.parse(frozen)>=Date.parse(string(v.kickoff_utc)))continue;
  const g=v.actual_goals;const goals=Array.isArray(g)&&g.length===2&&g.every(n=>typeof n==='number'&&Number.isInteger(n)&&n>=0)?g as [number,number]:null;
  const a=evidence.get(fid)||[];a.push({fixture_id:fid,market:m,selection:sel,line:lineValue(line),frozen,source_fixture_id:string(x.source_fixture_id),hit:x.hit,goals,historical:Date.parse(frozen)!==cut});evidence.set(fid,a);seen.add(k);
 }
 const q=object(s.sections.FIXTURES);const dates=(x:unknown)=>Array.isArray(x)?x.filter(v=>typeof v==='string') as string[]:[];
 return {raw,blockers,evidence,partialDates:dates(q.partial_dates),missingDates:[...dates(q.missing_dates),...dates(q.invalid_dates)]};
}
export type ResearchFilters={market:string;variant:string;minProbability:number;minOdds:number;quoteMode:'priced'|'all'|'missing';line:string};
export function filterResearch(rows:LinkRow[],ids:Set<string>,f:ResearchFilters){
 const minimum=Math.max(1.2,Number.isFinite(f.minOdds)?f.minOdds:1.2);
 return rows.filter(r=>ids.has(r.fixture_id)&&(f.market==='all'||r.market===f.market)&&(f.variant==='all'||(f.variant==='SHADOW'?r.lane==='SHADOW':f.variant==='ABC'?r.lane==='ABC':r.lane==='ABC'&&r.variant===f.variant))&&(f.line==='all'||String(r.line)===f.line)&&r.probability>=f.minProbability&&
 (f.quoteMode==='all'||(f.quoteMode==='missing'?r.quote===null:r.quote_status==='archived_research_quote'&&r.quote!==null&&r.quote.price>=minimum)));
}
export function researchGroups(rows:LinkRow[],fixtures:Fixture[],preview:boolean){
 const index=new Map(fixtures.map(f=>[f.fixture_id,f])),groups=new Map<string,LinkRow[]>();
 for(const r of rows){if(!index.has(r.fixture_id))continue;const a=groups.get(r.fixture_id)||[];a.push(r);groups.set(r.fixture_id,a);}
 return [...groups].map(([id,items])=>{
  const sorted=[...items].sort((a,b)=>b.probability-a.probability||String(b.variant).localeCompare(String(a.variant))||JSON.stringify(a.forecast_identity).localeCompare(JSON.stringify(b.forecast_identity)));
  const seen=new Set<string>();const unique=sorted.filter(r=>{const k=JSON.stringify([r.lane,r.market,r.selection,r.line]);if(seen.has(k))return false;seen.add(k);return true;});
  return {fixture:index.get(id)!,total:items.length,rows:preview?unique.slice(0,3):sorted};
 }).sort((a,b)=>Date.parse(a.fixture.kickoff_utc)-Date.parse(b.fixture.kickoff_utc)||a.fixture.fixture_id.localeCompare(b.fixture.fixture_id));
}
export function categories(raw:RawMarket[],candidates:LinkRow[],blockers:Blocker[]){
 const all=new Set<string>([...MARKET_ORDER,...raw.map(r=>r.market),...candidates.map(r=>r.market),...blockers.map(r=>r.market)]);
 return [...all].map(m=>({market:m,raw:raw.filter(r=>r.market===m),abc:candidates.filter(r=>r.market===m&&r.lane==='ABC'),shadow:candidates.filter(r=>r.market===m&&r.lane==='SHADOW'),blockers:blockers.filter(r=>r.market===m)}));
}
