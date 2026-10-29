const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const uiRoot=fs.existsSync(path.join(root,'home_assistant'))?path.join(root,'home_assistant/jarvis_ui/www/jarvis'):path.join(root,'jarvis_ui/www/jarvis');
const source=filename=>fs.readFileSync(path.join(uiRoot,filename),'utf8').replace(/^import .*;\r?\n/gm,'');
const baseline=process.argv.includes('--baseline');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const results=[];
  for(const [width,height] of [[320,640],[360,800],[390,844],[412,915],[844,390],[1280,800]]){
   const page=await browser.newPage({viewport:{width,height}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/*',route=>route.request().resourceType()==='document'?route.fulfill({contentType:'text/html',body:'<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{margin:0;width:100%;height:100%;background:#031623}</style>'}):route.abort());
   await page.goto('http://jarvis-layout.test/jarvis-yoga-test/home');
   await page.evaluate(()=>{customElements.define('ha-card',class extends HTMLElement{});customElements.define('ha-icon',class extends HTMLElement{connectedCallback(){this.style.cssText='display:inline-block;width:var(--mdc-icon-size,24px);height:var(--mdc-icon-size,24px);flex-shrink:0';}});});
   const hotUpgrade=width===390&&!baseline&&fs.existsSync(path.join(root,'.tmp/mobile-baseline'));
   for(const filename of ['jarvis-planner.js','jarvis-household.js','jarvis-yoga.js'])await page.addScriptTag({content:'(()=>{'+((baseline||hotUpgrade)?fs.readFileSync(path.join(root,'.tmp/mobile-baseline',filename),'utf8').replace(/^import .*;\r?\n/gm,''):source(filename))+'})()'});
   await page.evaluate(()=>{
    window.fakePeople={benny:'Benny',linda:'Linda',emrik:'Emrik',mia:'Mia'};
    const days=['Today','Tomorrow'].map((label,i)=>({label,date:'2026-10-'+(29+i),state:'ready',coverage:'Connected calendar plans.',checked_at:new Date().toISOString(),people:Object.entries(fakePeople).map(([id,name])=>({id,name,summary:name+' has an activity at 17:00. '.repeat(8),routines:['Usual weekday routine.'],attention:['Allow time for getting ready.'],departures:[{text:'If leaving from home, aim for 16:41. This is a planning estimate.'}]}))}));
    window.fakeData={schema_version:1,read_only:true,revision:36,planner:{members:Object.entries(fakePeople).map(([id,name])=>({id,name})),categories:['school','sport']},assistant:{people:fakePeople,learning_enabled:true,retention:'Until corrected or deleted',transport_preference:'Driving first',household_planning:{status:'ready',days,source_health:{work:{name:'Work Reach',status:'fresh',last_success:new Date().toISOString()},family:{name:'Household',status:'failed',last_success:new Date().toISOString()},travel:{name:'Jarvis Travels',status:'stale',last_success:new Date().toISOString()}}},memories:[],travel_briefs:[],improvements:[]},today:{cards:[]}};
    window.fakeHass={connected:true,user:{id:'fixture'},states:{},services:{},callWS:async request=>request.type==='jarvis_conversation/household'?fakeData:request.type==='jarvis_conversation/planner'?{schema_version:1,read_only:true,start:request.payload.start,ready:true,events:[],categories:['school','sport'],members:fakeData.planner.members}:[]};
    const P=customElements.get('jarvis-yoga-dashboard-card');P.prototype.loadContext=async()=>{};P.prototype.loadBattery=async()=>{};
    window.dash=document.createElement('jarvis-yoga-dashboard-card');dash.setConfig({rooms:[],security:[],interior:[],exterior:[],appliances:[],energy:[],calendars:[]});document.body.append(dash);dash.hass=fakeHass;
   });
   if(hotUpgrade){
    await page.evaluate(()=>{dash.page='household';dash.render();});
    const planner=page.locator('jarvis-planner-card');await planner.getByRole('button',{name:'Add appointment',exact:true}).click();
    await planner.locator('[name="title"]').fill('Unsaved fixture appointment');
    await page.evaluate(()=>{window.existingPlanner=dash.shadowRoot.querySelector('jarvis-household-card').shadowRoot.querySelector('jarvis-planner-card');});
    for(const filename of ['jarvis-household.js','jarvis-yoga.js'])await page.addScriptTag({content:'(()=>{'+source(filename)+'})()'});
    await page.evaluate(()=>{dash.hass=fakeHass;});
    assert.equal(await planner.locator('[name="title"]').inputValue(),'Unsaved fixture appointment');
    assert.equal(await page.evaluate(()=>existingPlanner===dash.shadowRoot.querySelector('jarvis-household-card').shadowRoot.querySelector('jarvis-planner-card')),true);
   }
   const nav=page.locator('jarvis-yoga-dashboard-card').locator('[data-nav="household"]');
   const bounds=await nav.boundingBox();
   assert.ok(bounds.x>=0&&bounds.x+bounds.width<=width+1&&bounds.y+bounds.height<=height,`Household navigation clipped at ${width}x${height}: ${JSON.stringify(bounds)}`);
   await nav.click();
   const house=page.locator('jarvis-household-card');await house.locator('[data-assistant]').click();
   await house.locator('[data-agenda-person]').selectOption('mia');await house.locator('[data-agenda-day]').selectOption('tomorrow');
   await house.getByRole('heading',{name:'Tomorrow · Mia',exact:true}).waitFor({timeout:2000});
   const geometry=await page.evaluate(()=>{
    const dash=document.querySelector('jarvis-yoga-dashboard-card'),h=dash.shadowRoot.querySelector('jarvis-household-card'),r=h.shadowRoot,view=r.querySelector('.view'),cards=r.querySelector('.cards');
    const controls=[...r.querySelectorAll('button,select')].map(x=>({text:x.textContent.trim().slice(0,30),left:x.getBoundingClientRect().left,right:x.getBoundingClientRect().right}));
    const b=cards.getBoundingClientRect();return {overflow:view.scrollWidth>view.clientWidth+1,controls,cardHeight:b.height,cardTop:b.top,cardBottom:b.bottom};
   });
   assert.equal(geometry.overflow,false,`Household width overflow at ${width}: ${JSON.stringify(geometry)}`);
   assert.ok(geometry.cardHeight>=60,`No room for plans at ${width}x${height}: ${JSON.stringify(geometry)}`);
   assert.ok(geometry.controls.every(b=>b.left>=-1&&b.right<=width+1),`Clipped controls at ${width}: ${JSON.stringify(geometry)}`);
   if([390,1280].includes(width)){await page.screenshot({path:path.join(root,`.tmp/mobile-layout-${width}.png`)});}
   // Refresh must keep a user's current reading position.
   await house.locator('[data-agenda-person]').selectOption('all');
   const scroll=await page.evaluate(()=>{const h=dash.shadowRoot.querySelector('jarvis-household-card'),box=h.shadowRoot.querySelector('.cards');box.scrollTop=120;const before=box.scrollTop;h.render();return [before,h.shadowRoot.querySelector('.cards').scrollTop];});
   assert.ok(scroll[0]>0&&scroll[0]===scroll[1],'Plan scroll position changed during refresh');
   // Direct HA panel entry point: starts at Assistant and can return to planner.
   await page.evaluate(()=>{dash.remove();const h=document.createElement('jarvis-household-card');h.setConfig({layout:'standalone',initial_section:'assistant'});document.body.append(h);h.hass=fakeHass;window.panel=h;});
   const direct=page.locator('jarvis-household-card');await direct.getByRole('heading',{name:'Today · Mia',exact:true}).waitFor();
   assert.ok((await direct.boundingBox()).height<=height);
   await direct.getByRole('button',{name:'Open household planner',exact:true}).click();await direct.locator('[data-assistant]').waitFor();
   assert.deepEqual(errors,[],`Browser errors at ${width}`);results.push({width,height,household_reachable:true,assistant_filters:true,no_horizontal_clipping:true,scroll_preserved:true,direct_panel:true});await page.close();
  }
  fs.writeFileSync(path.join(root,'.tmp/mobile-layout-results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
