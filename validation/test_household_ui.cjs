const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const registry=new Map();
const sourcePath=fs.existsSync('home_assistant/jarvis_ui/www/jarvis/jarvis-household.js')?'home_assistant/jarvis_ui/www/jarvis/jarvis-household.js':'jarvis_ui/www/jarvis/jarvis-household.js';
vm.runInNewContext(fs.readFileSync(sourcePath,'utf8').replace(/^import .*;\r?\n/gm,''),{
 HTMLElement:class {attachShadow(){this.shadowRoot={};}},
 customElements:{whenDefined:()=>({then:fn=>fn()}),get:n=>registry.get(n),define:(n,c)=>registry.set(n,c)},Date,
 setInterval,clearInterval,document:{hidden:false}
});
const Card=registry.get('jarvis-household-card');
const card=new Card();card.section='profiles';card.isConnected=true;card.render=()=>{};
(async()=>{
 let requests=[];
 card._hass={callWS:async request=>{requests.push(request);return {schema_version:1,read_only:true,profiles:[{name:'Test',details:{routine:'x'.repeat(400)}}]};}};
 await card.load();assert.equal(requests[0].type,'jarvis_conversation/household');
 assert.ok(card.cards().length>1);assert.ok(card.cards().every(c=>c.lines.length<=4));
 card._hass.callWS=async()=>{throw Error('offline');};await card.load();
 assert.equal(card.data,null);assert.match(card.error,/unavailable/);
 card._hass.callWS=async()=>({schema_version:1,read_only:false});await card.load();assert.equal(card.data,null);
 card.period='tomorrow';card.section='today';
 card._hass.callWS=async request=>{assert.equal(request.period,'tomorrow');return {schema_version:1,read_only:true,today:{cards:[]}};};
 await card.load();assert.equal(card.data,null,'Never show today as tomorrow from an old server');
 card._hass.callWS=async()=>({schema_version:1,read_only:true,planning:{period:'tomorrow',days:[{date:'2026-09-28',cards:[{title:'Future date',lines:['Confirmed schedule, not attendance']}]}]}});
 await card.load();assert.equal(card.cards()[0].title,'Future date');
 console.log('Household UI: pagination, read-only request, offline clearing and invalid response PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
