import { readBundle } from './import.ts';
import type { Manifest, Snapshot } from './types.ts';
const MAX=100_000_000;
export type SyncDeps={origin:string;fetcher:typeof fetch;decode:typeof readBundle;save:(s:Snapshot)=>Promise<void>;timeoutMs?:number};
export async function syncLatest(previous:Manifest|undefined,deps:SyncDeps):Promise<Snapshot>{
 const origin=new URL(deps.origin);
 if(origin.protocol!=='https:'||origin.origin!==deps.origin)throw new Error('Synchronizacja wymaga zaufanego adresu HTTPS.');
 const url=new URL('/api/panel/latest',origin);
 const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),deps.timeoutMs??30000);
 try{
  let response:Response;
  try{response=await deps.fetcher(url.href,{method:'GET',credentials:'same-origin',cache:'no-store',redirect:'error',headers:{Accept:'application/zip'},signal:ctrl.signal});}
  catch{throw new Error(ctrl.signal.aborted?'Przekroczono czas pobierania.':'Brak połączenia lub wygasła sesja. Zaloguj się ponownie albo użyj importu ZIP.');}
  if(response.status===401||response.status===403)throw new Error('Brak autoryzacji. Zaloguj się ponownie.');
  if(response.status===404||response.status===503)throw new Error('Nie udostępniono jeszcze prywatnego pakietu.');
  if(!response.ok||response.status!==200||response.redirected)throw new Error('Błąd serwera synchronizacji.');
  if(response.url&&response.url!==url.href)throw new Error('Nieprawidłowy adres odpowiedzi.');
  if(response.headers.get('content-type')?.split(';')[0].trim().toLowerCase()!=='application/zip'||response.headers.get('x-multimodel-sync')!=='v1'||!response.headers.get('cache-control')?.includes('no-store'))throw new Error('Nie jest to prywatny pakiet MultiModel. Sprawdź logowanie i konfigurację.');
  const length=Number(response.headers.get('content-length'));
  if(!Number.isSafeInteger(length)||length<=0||length>MAX||!response.body)throw new Error('Nieprawidłowy rozmiar pakietu.');
  const reader=response.body.getReader(),chunks:Uint8Array[]=[];let total=0;
  try{for(;;){const {done,value}=await reader.read();if(done)break;total+=value.byteLength;if(total>MAX||total>length){await reader.cancel();throw new Error('Przekroczono rozmiar pakietu.');}chunks.push(value);}}
  finally{reader.releaseLock();}
  if(total!==length)throw new Error('Niekompletny pakiet.');
  const bytes=new Uint8Array(total);let at=0;for(const c of chunks){bytes.set(c,at);at+=c.byteLength;}
  const next=await deps.decode(bytes.buffer,previous);
  await deps.save(next);return next;
 } finally {clearTimeout(timer);}
}
