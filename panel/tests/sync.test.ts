import {test} from 'node:test';
import assert from 'node:assert/strict';
import {syncLatest} from '../src/sync.ts';
import type {Snapshot,Manifest} from '../src/types.ts';
const origin='https://panel.example.test',bytes=new Uint8Array([80,75,3,4]);
const snap={manifest:{schema:'test'}} as Snapshot;
function response(over:Record<string,string>={},body=bytes){return new Response(body,{headers:{'Content-Type':'application/zip','Content-Length':String(bytes.length),'X-MultiModel-Bytes':String(bytes.length),'X-MultiModel-Sync':'v1','Cache-Control':'private, no-store',...over}});}
function deps(f:()=>Promise<Response>){let saves=0,decodes=0;return {origin,fetcher:(async(url,opts)=>{assert.equal(url,origin+'/api/panel/latest');assert.equal(opts?.redirect,'error');assert.equal(opts?.cache,'no-store');assert.equal(opts?.credentials,'same-origin');return f();}) as typeof fetch,decode:async(b:ArrayBuffer,p?:Manifest)=>{assert.deepEqual(new Uint8Array(b),bytes);decodes++;return snap;},save:async()=>{saves++;},counts:()=>[decodes,saves]};}
test('one same-origin request and verified save',async()=>{const d=deps(async()=>response());assert.equal(await syncLatest(undefined,d),snap);assert.deepEqual(d.counts(),[1,1]);});
test('reject HTTP and non-origin URL',async()=>{const d=deps(async()=>response());await assert.rejects(syncLatest(undefined,{...d,origin:'http://panel.example.test'}),/HTTPS/);await assert.rejects(syncLatest(undefined,{...d,origin:origin+'/foo'}),/HTTPS/);assert.deepEqual(d.counts(),[0,0]);});
test('expired session and absent bundle',async()=>{for(const status of [401,403,404,503]){const d=deps(async()=>new Response(null,{status}));await assert.rejects(syncLatest(undefined,d));assert.deepEqual(d.counts(),[0,0]);}});
test('network/redirect failure leaves saved data intact',async()=>{const d=deps(async()=>{throw new Error('failed');});await assert.rejects(syncLatest(undefined,d),/Brak połączenia/);assert.deepEqual(d.counts(),[0,0]);});
test('reject wrong content, missing no-store or wrong sync protocol',async()=>{for(const h of [{'Content-Type':'text/html'},{'Cache-Control':'public'},{'X-MultiModel-Sync':'v0'}]){const d=deps(async()=>response(h));await assert.rejects(syncLatest(undefined,d),/pakiet MultiModel/);assert.deepEqual(d.counts(),[0,0]);}});
test('reject incomplete, oversized or malformed content lengths',async()=>{for(const length of ['2','5','100000001','no']){const d=deps(async()=>response({'Content-Length':length,'X-MultiModel-Bytes':length}));await assert.rejects(syncLatest(undefined,d));assert.deepEqual(d.counts(),[0,0]);}});
test('decode failure cannot save',async()=>{const d=deps(async()=>response());await assert.rejects(syncLatest(undefined,{...d,decode:async()=>{throw new Error('rollback');}}),/rollback/);assert.deepEqual(d.counts(),[0,0]);});

test('reject mismatch between declared and transport size',async()=>{const d=deps(async()=>response({'Content-Length':'5'}));await assert.rejects(syncLatest(undefined,d),/rozmiar/);assert.deepEqual(d.counts(),[0,0]);});
