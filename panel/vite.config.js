import { defineConfig } from 'vite';
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { deflateSync } from 'node:zlib';
function crc(b){let n=0xffffffff;for(const v of b){n^=v;for(let i=0;i<8;i++)n=(n>>>1)^((n&1)?0xedb88320:0);}return (n^0xffffffff)>>>0;}
function chunk(t,d){const b=Buffer.concat([Buffer.from(t),d]);const len=Buffer.alloc(4),c=Buffer.alloc(4);len.writeUInt32BE(d.length);c.writeUInt32BE(crc(b));return Buffer.concat([len,b,c]);}
function png(size){const h=Buffer.alloc(13);h.writeUInt32BE(size,0);h.writeUInt32BE(size,4);h[8]=8;h[9]=2;const rows=Buffer.alloc(size*(size*3+1));const pts=[[.24,.65],[.24,.35],[.41,.53],[.5,.35],[.59,.53],[.76,.35],[.76,.65]];for(let y=0;y<size;y++)for(let x=0;x<size;x++){const px=x/size,py=y/size;let d=1;for(let i=1;i<pts.length;i++){const [a,b]=pts[i-1],[c,e]=pts[i];const dx=c-a,dy=e-b,t=Math.max(0,Math.min(1,((px-a)*dx+(py-b)*dy)/(dx*dx+dy*dy)));d=Math.min(d,Math.hypot(px-a-t*dx,py-b-t*dy));}const off=y*(size*3+1)+1+x*3;rows.set(d<.029?[89,213,189]:[16,28,46],off);}return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',h),chunk('IDAT',deflateSync(rows)),chunk('IEND',Buffer.alloc(0))]);}
function shell(){return {name:'offline-shell',apply:'build',closeBundle(){const root='dist';for(const n of [192,512])writeFileSync(join(root,'icon-'+n+'.png'),png(n));const walk=(p)=>readdirSync(join(root,p),{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(p+e.name+'/'):[p+e.name]);const paths=walk('').filter(p=>p!=='sw.js').sort();const hash=createHash('sha256');for(const p of paths)hash.update(p).update(readFileSync(join(root,p)));const cache='multimodel-shell-'+hash.digest('hex').slice(0,16);writeFileSync(join(root,'sw.js'),`
const CACHE=${JSON.stringify(cache)}, PREFIX='multimodel-shell-', FILES=${JSON.stringify(paths)};
const urls=FILES.map(p=>new URL(p,self.registration.scope).href);
self.addEventListener('install', e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(urls))));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith(PREFIX)&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;const u=new URL(e.request.url);if(u.origin!==self.location.origin||!u.href.startsWith(self.registration.scope))return;if(e.request.mode==='navigate'){e.respondWith(caches.open(CACHE).then(c=>c.match(new URL('index.html',self.registration.scope).href)).then(r=>r||fetch(e.request)));return;}if(urls.includes(u.href))e.respondWith(caches.open(CACHE).then(c=>c.match(u.href)).then(r=>r||fetch(e.request)));});
`);}};}
export default defineConfig({base:'./',plugins:[shell()],build:{sourcemap:false}});
