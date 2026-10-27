/* Shared household planner and profile view. No browser credentials or storage. */
import './jarvis-planner.js?v=04580';
const escapeHousehold=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const householdLabel=s=>String(s).replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
function householdLines(value,prefix=''){
 if(value==null)return [prefix+': Not recorded / not shared'];
 if(Array.isArray(value))return value.length?value.flatMap((v,i)=>householdLines(v,prefix+(typeof v==='object'?` ${i+1}`:''))):[];
 if(typeof value==='object')return Object.entries(value).flatMap(([k,v])=>householdLines(v,prefix?prefix+' · '+householdLabel(k):householdLabel(k)));
 return [(prefix?prefix+': ':'')+String(value)];
}
class JarvisHouseholdCard extends HTMLElement{
 get uiRevision(){return 2026102703;}
 constructor(){super();this.attachShadow({mode:'open'});this.section='planner';this.period='today';this.page=0;this.serial=0;this.error='';this.loading=false;}
 set hass(hass){const upgrade=this._plannerUiRevision!==2026102703;this._plannerUiRevision=2026102703;if(upgrade&&!this.shadowRoot.querySelector?.('jarvis-planner-card'))this.section='planner';const changed=this._hass?.user?.id!==hass?.user?.id;this._hass=hass;if(changed){this.data=null;this.serial++;this.loading=false;}if(upgrade)this.render();if(!this.data&&!this.loading&&hass)this.load();}
 connectedCallback(){this.render();this.timer=setInterval(()=>{if(!document.hidden)this.load();},60000);}
 disconnectedCallback(){clearInterval(this.timer);this.serial++;this.data=null;this.loading=false;}
 async load(){if(!this._hass||this.loading||!this.isConnected)return;const serial=++this.serial;this.loading=true;this.error='';this.render();try{const data=await this._hass.callWS({type:'jarvis_conversation/household',period:this.period});if(serial!==this.serial||!this.isConnected)return;if(data.schema_version!==1||data.read_only!==true||(this.period!=='today'&&data.planning?.period!==this.period))throw Error('Invalid response');this.data=data;}catch{if(serial!==this.serial)return;this.data=null;this.error='Household information unavailable. Nothing has been changed. Try Refresh.';}finally{if(serial===this.serial){this.loading=false;this.render();}}}
 cards(){const d=this.data;if(!d)return [];let cards=[];
 if(this.section==='today')cards=d.planning?.days?.flatMap(day=>day.cards.map(card=>({...card,title:(d.planning.days.length>1?day.date+' · ':'')+card.title})))||d.today?.cards||[{title:'Household plans',lines:['Overview unavailable.']}];
 if(this.section==='profiles')cards=(d.profiles||[]).map(p=>({title:p.name,lines:householdLines(p.details)}));
 if(this.section==='rooms')cards=(d.rooms||[]).map(r=>({title:r.name||r.id,lines:householdLines(Object.fromEntries(Object.entries(r).filter(([k])=>!['id','name','connects'].includes(k))))}));
 if(this.section==='routines')cards=[{title:'Usual household routines',lines:householdLines(d.routines)},...(d.exceptions||[]).map(r=>({title:'Confirmed override',lines:householdLines({...r,expiry:r.kind==='no_school'?`After ${r.on}, at midnight Europe/Oslo`:'Recurring — no automatic expiry'})}))];
if(this.section==='changes')cards=(d.changes||[]).map(c=>({title:'Revision '+c.revision,lines:[new Date(c.at).toLocaleString('en-GB',{timeZone:'Europe/Oslo'}),c.method,c.actor]}));
 if(this.section==='notes')cards=[...(d.notes||[]).map(n=>({title:'Shared note',lines:[n.text]})),{title:'Relationships',lines:d.relationships||[]},{title:'What this page can tell you',lines:d.limitations||[]}];
 const out=[];for(const c of cards){const lines=(c.lines.length?c.lines:['Not recorded or not approved for shared display.']).flatMap(line=>String(line).match(/.{1,64}(?:\s|$)|.{1,64}/g)||[]);for(let i=0;i<lines.length;i+=4)out.push({title:c.title+(i?' · continued':''),lines:lines.slice(i,i+4)});}return out;
 }
 render(){if(this.section==='planner'){
  let planner=this.shadowRoot.querySelector?.('jarvis-planner-card');
  if(!planner){this.shadowRoot.innerHTML='<style>:host{display:block;height:100%;min-height:0}.planner-view{height:100%;display:flex;flex-direction:column;gap:8px}header{display:flex;justify-content:space-between;color:#dff7ff}button{background:#082d43;color:#dff7ff;border:1px solid #287b94;border-radius:6px;min-height:32px}jarvis-planner-card{min-height:0;flex:1}</style><div class="planner-view"><header><strong>Household planner</strong><button data-info>Household information</button></header><jarvis-planner-card></jarvis-planner-card></div>';planner=this.shadowRoot.querySelector?.('jarvis-planner-card');const button=this.shadowRoot.querySelector?.('[data-info]');if(button)button.onclick=()=>{this.section='today';this.render();};}
  if(planner){planner.directory=this.data?.planner;planner.hass=this._hass;}return;
 }const esc=escapeHousehold,all=this.cards(),size=this.clientWidth&&this.clientWidth<650?2:4,total=Math.max(1,Math.ceil(all.length/size));this.page=Math.min(this.page,total-1);this.shadowRoot.innerHTML=`<style>
 :host{display:block;height:100%;min-height:0;color:#dff7ff;font-family:Arial,sans-serif}*{box-sizing:border-box}.view{height:100%;display:grid;grid-template-rows:auto auto minmax(0,1fr) auto;gap:8px}header,footer{display:flex;align-items:center;justify-content:space-between;gap:8px}header strong{font-size:18px}small{font-size:10px;color:#a7c4d2}nav{display:flex;gap:6px}button{min-height:32px;background:#082d43;border:1px solid #287b94;border-radius:7px;color:inherit;padding:5px 10px;cursor:pointer}button[aria-current=true]{background:#14617b}button:disabled{opacity:.45}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:repeat(2,minmax(0,1fr));gap:8px;min-height:0}article{border:1px solid #287b94;border-radius:9px;background:#042033;padding:10px;min-height:0}h3{margin:0 0 8px;color:#40daff;font-size:14px}p{font-size:12px;line-height:1.35;margin:6px 0;overflow-wrap:anywhere}.error{color:#ff8a94}@media(max-width:650px){.cards{grid-template-columns:1fr}nav button{padding:4px;font-size:10px}p{font-size:11px}}
 </style><div class="view"><header><div><strong>Household information</strong><br><small>Read-only · Norway time · ${this.data?'Revision '+esc(this.data.revision):'Shared access only'}</small></div><label style="display:grid;gap:3px;font-size:10px">Period<select data-period aria-label="Planning period" style="background:#082d43;color:#dff7ff;border:1px solid #287b94;border-radius:6px;min-height:32px">${[['today','Today'],['tomorrow','Tomorrow'],['week_ahead','Next 7 days'],['this_week','Rest of this week'],['next_week','Next week']].map(([v,label])=>`<option value="${v}" ${this.period===v?'selected':''}>${label}</option>`).join('')}</select></label><button data-refresh ${this.loading?'disabled':''}>${this.loading?'Loading…':'Refresh'}</button></header><nav>${['today','profiles','rooms','routines','changes','notes'].map(s=>`<button data-section="${s}" aria-current="${this.section===s}">${s==='today'?'Plans':householdLabel(s)}</button>`).join('')}</nav><div class="cards">${this.error?`<article class="error">${esc(this.error)}</article>`:all.length?all.slice(this.page*size,(this.page+1)*size).map(c=>`<article><h3>${esc(c.title)}</h3>${c.lines.map(l=>`<p>${esc(l)}</p>`).join('')}</article>`).join(''):`<article><p>${this.loading?'Loading the current profile…':'No shared records in this section.'}</p></article>`}</div><footer><small>Routine ≠ attendance. Missing ≠ confirmed absent.</small><div><button data-prev ${!this.page?'disabled':''}>Previous</button> ${this.page+1}/${total} <button data-next ${this.page>=total-1?'disabled':''}>Next</button></div></footer></div>`;
 this.shadowRoot.querySelector('[data-period]').onchange=e=>{this.period=e.target.value;this.section='today';this.page=0;this.serial++;this.data=null;this.loading=false;this.load();};this.shadowRoot.querySelector('[data-refresh]').onclick=()=>this.load();this.shadowRoot.querySelectorAll('[data-section]').forEach(b=>b.onclick=()=>{this.section=b.dataset.section;this.page=0;this.render();});this.shadowRoot.querySelector('[data-prev]').onclick=()=>{this.page--;this.render();};this.shadowRoot.querySelector('[data-next]').onclick=()=>{this.page++;this.render();};
 const back=document.createElement('button');back.textContent='Open household planner';back.onclick=()=>{this.section='planner';this.render();};this.shadowRoot.querySelector('footer').prepend(back);
 }
}
customElements.whenDefined('ha-card').then(()=>{
 const active=customElements.get('jarvis-household-card');
 if(!active)customElements.define('jarvis-household-card',JarvisHouseholdCard);
 else if((active.prototype.uiRevision||0)<2026102703){
  // HA can announce this module to a still-open companion WebView. Upgrade its
  // existing compatible element instead of silently retaining the cached class.
  for(const name of Object.getOwnPropertyNames(JarvisHouseholdCard.prototype)){
   if(name!=='constructor')Object.defineProperty(active.prototype,name,Object.getOwnPropertyDescriptor(JarvisHouseholdCard.prototype,name));
  }
 }
});
