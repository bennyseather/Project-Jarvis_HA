const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(fs.existsSync('home_assistant/jarvis_ui/www/jarvis/jarvis-ui.js')?'home_assistant/jarvis_ui/www/jarvis/jarvis-ui.js':'jarvis_ui/www/jarvis/jarvis-ui.js','utf8');
const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');

function formatting(){
 const context={entityDomain:id=>String(id||'').split('.')[0]};vm.createContext(context);
 vm.runInContext(source.slice(source.indexOf('function formatState('),source.indexOf('function accent('))+'\nglobalThis.format=formatState;',context);
 return context.format;
}
test('door badges use Open/Closed without converting unavailable or unrelated sensors',()=>{
 const format=formatting(),config={entity:'binary_sensor.fixture',display_class:'door'};
 for(const [state,label] of [['on','Open'],['off','Closed'],['unavailable','unavailable'],['unknown','unknown']])assert.equal(format({state},config),label);
 assert.equal(format({state:'off',attributes:{device_class:'window'}},{entity:'binary_sensor.fixture'}),'Closed');
 assert.equal(format({state:'on',attributes:{device_class:'motion'}},{entity:'binary_sensor.fixture'}),'on');
 assert.equal(format({state:'on',attributes:{battery:75}},{...config,attribute:'battery'}),'75.0');
});
test('seasonal status is explicit and limited to the mower display',()=>{
 const format=formatting();
 assert.equal(format({state:'unavailable'},{entity:'lawn_mower.fixture',out_of_season:true}),'Out of season');
 assert.equal(format({state:'unavailable'},{entity:'lawn_mower.fixture'}),'unavailable');
 assert.equal(format({state:'unavailable'},{entity:'vacuum.fixture',out_of_season:true}),'unavailable');
});

function insight(){
 const viewport={scrollTop:0,setAttribute(){},classList:{contains:()=>true},focus(){this.focused=true;}};
 const root={activeElement:null,querySelector:selector=>selector==='.routines'?viewport:null};
 const context={JarvisBaseCard:class{},escapeHtml:esc,isUnavailable:s=>!s||['unknown','unavailable'].includes(s.state)};
 vm.createContext(context);vm.runInContext(source.slice(source.indexOf('class JarvisLearningInsightsCard'),source.indexOf('class JarvisIconCatalogCard'))+'\nglobalThis.Card=JarvisLearningInsightsCard;',context);
 const card=Object.create(context.Card.prototype);card.shadowRoot=root;card._config={entity:'sensor.fixture'};
 card.shell=markup=>{card.renders=(card.renders||0)+1;card.markup=markup;viewport.scrollTop=0;};
 const hass={states:{'sensor.fixture':{state:'2',attributes:{observed:2,routines:[{description:'Synthetic routine'}]}}}};
 return {card,viewport,root,hass};
}
test('1 Hz unrelated updates do not rebuild Insights or interrupt scrolling',()=>{
 const {card,viewport,hass}=insight();card.hass=hass;viewport.scrollTop=240;
 for(let i=0;i<60;i++)card.hass={...hass,states:{...hass.states,'sensor.unrelated':{state:String(i)}}};
 assert.equal(card.renders,1);assert.equal(viewport.scrollTop,240);
});
test('real Insights changes preserve scroll position and keyboard focus',()=>{
 const {card,viewport,root,hass}=insight();card.hass=hass;viewport.scrollTop=177;root.activeElement=viewport;
 card.hass={states:{'sensor.fixture':{state:'3',attributes:{observed:3,routines:[{description:'Updated fixture'}]}}}};
 assert.equal(card.renders,2);assert.equal(viewport.scrollTop,177);assert.equal(viewport.focused,true);
 assert.match(card.markup,/Updated fixture/);
});

function calendar(){
 let now='2026-10-21T12:00:00Z';
 class Clock extends Date{constructor(...args){super(...(args.length?args:[now]));}static now(){return new Date(now).getTime();}}
 const writes=[],host={scrollTop:0,_html:'',get innerHTML(){return this._html;},set innerHTML(v){this._html=v;writes.push(v);this.scrollTop=0;}};
 const selected={textContent:''},root={querySelector:s=>s==='.calendar-content'?host:s==='.selected-day'?selected:null,contains:n=>n===host};
 const context={JarvisBaseCard:class{},Date:Clock,Intl,escapeHtml:esc,CALENDAR_CACHE:new Map(),DATA_CACHE_TTL:60000,
  setInterval:()=>1,clearInterval(){},document:{hidden:false,addEventListener(){},removeEventListener(){}}};
 vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function jarvisDateKey('),source.indexOf('class JarvisMonthCalendarCard'))+'\nglobalThis.Card=JarvisCalendarCard;globalThis.range=jarvisDayRange;globalThis.key=jarvisDateKey;',context);
 const card=Object.create(context.Card.prototype);card.shadowRoot=root;card._offset=0;
 card._config={entities:['calendar.fixture'],view:'day',appointment_limit:1};
 return {card,host,selected,writes,context,setNow:v=>{now=v;}};
}
test('calendar household midnight and DST windows are correct independent of browser time',()=>{
 const {context}=calendar();
 assert.equal(context.key(new Date('2026-10-21T22:30:00Z'),'Europe/Oslo'),'2026-10-22');
 const autumn=context.range('2026-10-25','Europe/Oslo');assert.equal((autumn.end-autumn.start)/3600000,25);
 assert.equal(autumn.start.toISOString(),'2026-10-24T22:00:00.000Z');
 const spring=context.range('2026-03-29','Europe/Oslo');assert.equal((spring.end-spring.start)/3600000,23);
});
test('whole day includes past, late and all-day entries without appointment cap',async()=>{
 const {card,host}=calendar();let query;
 const entries=[{summary:'All-day fixture',start:{date:'2026-10-21'},end:{date:'2026-10-22'}},
  ...Array.from({length:22},(_,i)=>({summary:`Appointment ${i}`,start:{dateTime:`2026-10-21T${String(i).padStart(2,'0')}:00:00+02:00`},end:{dateTime:`2026-10-21T${String(i).padStart(2,'0')}:30:00+02:00`}}))];
 card._hass={config:{time_zone:'Europe/Oslo'},callApi:async(method,url)=>{query=url;return entries;}};
 await card.loadDayEvents();assert.match(decodeURIComponent(query),/start=2026-10-20T22:00:00.000Z&end=2026-10-21T22:00:00.000Z/);
 assert.equal((host.innerHTML.match(/class="event"/g)||[]).length,23);assert.match(host.innerHTML,/All day/);assert.match(host.innerHTML,/Appointment 21/);
 host.scrollTop=183;await card.loadDayEvents();assert.equal(host.scrollTop,183);
});
test('day rollover returns to today even after manual browsing or tab sleep',()=>{
 const {card,setNow}=calendar();card._checkCalendarDay();card._offset=3;
 setNow('2026-10-21T22:01:00Z');card._checkCalendarDay();assert.equal(card._offset,0);assert.equal(card._calendarToday,'2026-10-22');
});
test('calendar failure is not misrepresented as an empty day',async()=>{
 const {card,host}=calendar();card._hass={config:{time_zone:'Europe/Oslo'},callApi:async()=>{throw Error('offline');}};
 await card.loadDayEvents();assert.match(host.innerHTML,/Calendar unavailable/);assert.doesNotMatch(host.innerHTML,/No calendar entries/);
});
test('older day response cannot replace the newly selected day',async()=>{
 const {card,host,writes}=calendar();let release,calls=0;
 card._hass={config:{time_zone:'Europe/Oslo'},callApi:()=>++calls===1?new Promise(r=>release=r):Promise.resolve([{summary:'New day',start:{date:'2026-10-22'},end:{date:'2026-10-23'}}])};
 const pending=card.loadDayEvents();card._offset=1;card._dayRevision=1;await card.loadDayEvents();
 release([{summary:'Old day',start:{date:'2026-10-21'},end:{date:'2026-10-22'}}]);await pending;await new Promise(setImmediate);
 assert.match(host.innerHTML,/New day/);assert.ok(writes.every(w=>!w.includes('Old day')));
});
