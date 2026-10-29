const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=fs.existsSync('home_assistant/jarvis_ui/www/jarvis/jarvis-household.js')?'home_assistant/jarvis_ui/www/jarvis/jarvis-household.js':'jarvis_ui/www/jarvis/jarvis-household.js';
const source=fs.readFileSync(path,'utf8').replace(/^import .*;\r?\n/gm,'');
class Element {attachShadow(){this.shadowRoot={querySelector:()=>null};}}
class Old extends Element {constructor(){super();this.attachShadow();this.section='today';this.period='today';this.page=0;this.serial=0;this.data={schema_version:1};this.loading=false;}}
const registry=new Map([['jarvis-household-card',Old]]);
function upgrade(){vm.runInNewContext(source,{HTMLElement:Element,customElements:{whenDefined:()=>({then:f=>f()}),get:n=>registry.get(n),define:(n,c)=>registry.set(n,c)},Date,setInterval,clearInterval,document:{hidden:false}});}
const old=new Old(),hass={user:{id:'fictional'},callWS:()=>{throw Error('No test network');}};old._hass=hass;
upgrade();assert.equal(registry.get('jarvis-household-card'),Old);assert.equal(old.uiRevision,2026102901);
let renders=0;old.render=()=>{renders++;};old.hass=hass;assert.equal(old.section,'planner');assert.equal(renders,1);
const form={typed:'Unsaved fictional appointment'};old.shadowRoot.querySelector=()=>form;old.hass=hass;upgrade();old.hass=hass;
assert.equal(form.typed,'Unsaved fictional appointment');assert.equal(renders,1);
assert.ok(fs.readFileSync(path,'utf8').includes("import './jarvis-planner.js?v=04580'"));
console.log('Household loader PASS: existing registry upgraded, old instance opens planner, repeated module/hass updates preserve form.');
