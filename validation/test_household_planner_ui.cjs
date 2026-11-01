const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const sourcePath=fs.existsSync('home_assistant/jarvis_ui/www/jarvis/jarvis-planner.js')?'home_assistant/jarvis_ui/www/jarvis/jarvis-planner.js':'jarvis_ui/www/jarvis/jarvis-planner.js';
const source=fs.readFileSync(sourcePath,'utf8');
let Card;const registry=new Map();
vm.runInNewContext(source,{HTMLElement:class{attachShadow(){this.shadowRoot={querySelector:()=>null,querySelectorAll:()=>[]};}},
 customElements:{whenDefined:()=>({then:fn=>fn()}),get:n=>registry.get(n),define:(n,c)=>{registry.set(n,c);Card=c;}},Date,Intl,crypto:require('node:crypto').webcrypto,setInterval,clearInterval,document:{hidden:false}});
function fixture(){const c=new Card();c.isConnected=true;c.render=()=>{};c.day='2026-11-05';c.autoToday=false;c.span=1;c._directory={members:[{id:'mia',name:'Mia'},{id:'linda',name:'Linda'}]};return c;}
(async()=>{
 let c=fixture(),calls=[];c.member='linda';c._hass={callWS:async req=>{calls.push(req);return {schema_version:1,read_only:true,ready:true,start:c.day,events:[]};}};
 await c.load();assert.equal(calls[0].type,'jarvis_conversation/planner');assert.deepEqual([...calls[0].payload.members],['linda']);
 c._hass.callWS=async()=>{throw Error('offline');};await c.load();assert.equal(c.data,null);assert.match(c.error,/unknown, not empty/);
 c=fixture();calls=[];c.draft={title:'Fictional club',members:['mia'],category:'sport',start:'2026-11-05T17:00',end:'2026-11-05T18:00',all_day:false,location:'',notes:''};c.capture=()=>{};
 c._hass={callWS:async req=>{calls.push(req);return req.action==='review'?{state:'review',token:'fixture-token',appointment:c.draft,overlaps:[]}:{state:'confirmed',message:'Fictional success'};}};
 await c.requestReview();assert.deepEqual(calls.map(c=>c.action),['review']);assert.equal(c.mode,'review');
 c.load=async()=>{};await Promise.all([c.save(),c.save()]);assert.deepEqual(calls.map(c=>c.action),['review','confirm']);assert.deepEqual(Object.keys(calls[1].payload),['token']);
 c=fixture();c.review={state:'review',token:'fictional-token',appointment:{}};c._hass={callWS:async()=>{throw Error('unknown network delivery');}};
 await c.save();assert.equal(c.review.uncertain,true);let sent=0;c._hass.callWS=async()=>{sent++;};await c.save();assert.equal(sent,0);
 c=fixture();c.data={events:[{members:[],category:'other'},{members:['mia'],category:'sport'}]};c.member='unassigned';assert.equal(c.events().length,1);
 assert.ok(!source.includes('localStorage')&&!source.includes('sessionStorage'));assert.ok(source.includes('overflow:auto'));assert.ok(source.includes('Europe/Oslo'));
 console.log('Planner UI PASS: explicit review, single submit, uncertain-send hold, member filters, offline clearing, no browser storage.');
})().catch(e=>{console.error(e);process.exitCode=1;});
