import fs from 'node:fs';
const pages=await(await fetch('http://127.0.0.1:9222/json/list')).json();
const ws=new WebSocket(pages.find(x=>x.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let id=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){pending.get(m.id)?.(m);pending.delete(m.id)}};
function call(method,params={}){return new Promise(r=>{const n=++id;pending.set(n,r);ws.send(JSON.stringify({id:n,method,params}))})}
const ev=async expression=>(await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result.result.value;
await call('Page.navigate',{url:'http://127.0.0.1:8765/'});
for(let i=0;i<40;i++){if(await ev('document.querySelectorAll("#rows tr").length>0'))break;await new Promise(r=>setTimeout(r,100))}
console.log('Initial',await ev('({title:document.title,rows:document.querySelectorAll("#rows tr").length,status:document.querySelector("#status").innerText})'));
await ev('document.querySelector("#funded").checked=true;document.querySelector("#funded").dispatchEvent(new Event("input"))');
console.log('Funded',await ev('document.querySelectorAll("#rows tr").length'));
await ev('document.querySelector("#funded").checked=false;document.querySelector("#search").value="SAGES";document.querySelector("#search").dispatchEvent(new Event("input"))');
console.log('Search',await ev('document.querySelector("#rows").innerText'));
await ev('document.querySelector("#search").value="";document.querySelector("#search").dispatchEvent(new Event("input"))');
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
const screenshot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/home/stevenhsu/conference-calendar/preview.png',Buffer.from(screenshot.result.data,'base64'));
await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
console.log('Mobile',await ev('({width:innerWidth,body:document.body.scrollWidth,table:document.querySelector(".scroll").scrollWidth})'));
console.log('Feed response',await ev('fetch("all.ics").then(async r=>({status:r.status,type:r.headers.get("content-type"),valid:(await r.text()).startsWith("BEGIN:VCALENDAR")}))'));
ws.close();
