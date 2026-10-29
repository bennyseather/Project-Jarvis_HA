const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=fs.existsSync('home_assistant/jarvis_ui/www/jarvis/jarvis-household.js')?'home_assistant/jarvis_ui/www/jarvis/jarvis-household.js':'jarvis_ui/www/jarvis/jarvis-household.js';
const registry=new Map();
vm.runInNewContext(fs.readFileSync(path,'utf8').replace(/^import .*;\r?\n/gm,''),{
 HTMLElement:class {attachShadow(){this.shadowRoot={};}},customElements:{whenDefined:()=>({then:fn=>fn()}),get:n=>registry.get(n),define:(n,c)=>registry.set(n,c)},Date,setInterval,clearInterval,document:{hidden:false}});
const card=new (registry.get('jarvis-household-card'))();card.section='assistant';
const people={benny:'Benny',mia:'Mia'};
const plan={status:'ready',days:[{label:'Today',date:'2026-10-29',state:'ready',checked_at:'2026-10-29T11:00:00+01:00',coverage:'Connected calendars.',coordination:['Check shared transport if needed.'],people:[{id:'mia',name:'Mia',summary:'Gymnastics at17:00.',departures:[{text:'If leaving from home, aim for16:41.'}],attention:['Sixty-minute recorded gap.'],routines:['Usual school.']},{id:'benny',name:'Benny',summary:'No extra appointments returned.',routines:[]}]},{label:'Tomorrow',date:'2026-10-30',state:'ready',people:[{id:'mia',name:'Mia',summary:'No extra appointments returned.'}]}]};
assert.equal(card.agendaCards(plan,people).length,3);
card.agendaPerson='mia';assert.equal(card.agendaCards(plan,people).length,2);assert.match(card.agendaCards(plan,people)[1].title,/Mia/);
card.agendaDay='tomorrow';assert.match(card.agendaCards(plan,people)[1].lines[0],/No extra/);
const old=JSON.parse(JSON.stringify(plan));old.days[1].state='needs_check';assert.equal(card.agendaCards(old,people).length,1,'Withhold old people even if a bad projection retains them');
assert.match(card.agendaCards({status:'disabled'},people)[0].lines[0],/not enabled/);
card.data={assistant:{people,household_planning:plan,memories:[],travel_briefs:[],improvements:[]}};assert.ok(card.cards().some(c=>c.title==='Tomorrow · Mia'));
assert.match(fs.readFileSync(path,'utf8'),/data-agenda-person/);
assert.match(fs.readFileSync(path,'utf8'),/scrollTop=oldScroll/);
console.log('Household agenda UI: day/person filters, disabled/stale handling and scroll preservation PASS');
