import {createRemoteJWKSet,jwtVerify} from 'jose';
const KEY='multimodel/latest.zip',MAX=100_000_000;
const headers={'Cache-Control':'private, no-store, max-age=0','Pragma':'no-cache','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Cross-Origin-Resource-Policy':'same-origin'};
const reply=(msg,status)=>new Response(msg,{status,headers:{...headers,'Content-Type':'text/plain; charset=utf-8'}});
const jwks=new Map();
function remote(issuer){if(!jwks.has(issuer))jwks.set(issuer,createRemoteJWKSet(new URL(issuer+'/cdn-cgi/access/certs'),{timeoutDuration:5000}));return jwks.get(issuer);}
export function configured(env){
 return typeof env.APP_ORIGIN==='string'&&/^https:\/\/[a-z0-9.-]+$/i.test(env.APP_ORIGIN)&&typeof env.ACCESS_ISSUER==='string'&&/^https:\/\/[a-z0-9-]+\.cloudflareaccess\.com$/i.test(env.ACCESS_ISSUER)&&typeof env.ACCESS_AUD==='string'&&/^[a-f0-9]{64}$/i.test(env.ACCESS_AUD)&&typeof env.OWNER_EMAIL==='string'&&/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(env.OWNER_EMAIL);
}
export async function access(request,env,resolve=remote){
 const token=request.headers.get('Cf-Access-Jwt-Assertion');
 if(!configured(env)||!token||token.length>16384)return false;
 try{const {payload}=await jwtVerify(token,resolve(env.ACCESS_ISSUER),{issuer:env.ACCESS_ISSUER,audience:env.ACCESS_AUD,algorithms:['RS256'],requiredClaims:['exp','iat','sub','email'],clockTolerance:5});
 return typeof payload.email==='string'&&payload.email.toLowerCase()===env.OWNER_EMAIL.toLowerCase()&&typeof payload.sub==='string'&&payload.sub.length>0&&typeof payload.iat==='number'&&payload.iat<=Date.now()/1000+5;
 }catch{return false;}
}
export function handler(resolve=remote){return async function(request,env){
 const url=new URL(request.url);
 if(!configured(env)||url.origin!==env.APP_ORIGIN)return reply('Private sync not configured',503);
 if(request.method!=='GET'&&request.method!=='HEAD')return reply('Method not allowed',405);
 if(!(await access(request,env,resolve)))return reply('Authentication required',401);
 if(url.pathname==='/api/panel/session')return reply('Sesja MultiModel aktywna. Wróć do aplikacji i naciśnij Pobierz dane.',200);
 if(url.pathname==='/api/panel/latest'){
  if(request.headers.has('Range'))return reply('Partial downloads not supported',416);
  if(!env.PANEL_BUCKET)return reply('No private storage',503);
  let obj;try{obj=await env.PANEL_BUCKET.get(KEY);}catch{return reply('Storage unavailable',503);}
  if(!obj)return reply('No published bundle',404);
  if(!Number.isSafeInteger(obj.size)||obj.size<=0||obj.size>MAX){await obj.body?.cancel();return reply('Invalid bundle size',503);}
  if(request.method==='HEAD')await obj.body?.cancel();
  return new Response(request.method==='HEAD'?null:obj.body,{headers:{...headers,'Content-Type':'application/zip','Content-Length':String(obj.size),'Content-Disposition':'attachment; filename="MULTIMODEL_PANEL.zip"','X-MultiModel-Sync':'v1'}});
 }
 if(url.pathname.startsWith('/api/')||url.pathname==='/api')return reply('Not found',404);
 if(!env.ASSETS)return reply('No application build',503);
 const response=await env.ASSETS.fetch(request);
 const out=new Headers(response.headers);for(const [k,v] of Object.entries(headers))out.set(k,v);out.set('X-Frame-Options','DENY');
 return new Response(response.body,{status:response.status,headers:out});
};}
export default {fetch:handler()};
