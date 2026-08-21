(function(){
  'use strict';
  const STORAGE_KEY='dak-kommuneindsigt-personal-view-v1';
  const PARAM='pv';
  let applying=false;

  function encodeState(state){
    const json=JSON.stringify(state),bytes=new TextEncoder().encode(json);let binary='';
    bytes.forEach(b=>binary+=String.fromCharCode(b));
    return btoa(binary).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  }
  function decodeState(value){
    try{let b64=value.replace(/-/g,'+').replace(/_/g,'/');while(b64.length%4)b64+='=';const binary=atob(b64),bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));return JSON.parse(new TextDecoder().decode(bytes));}catch(_){return null;}
  }
  function sharedState(){return decodeState(new URLSearchParams(location.search).get(PARAM)||'');}
  function storedState(){try{return JSON.parse(localStorage.getItem(STORAGE_KEY)||'null');}catch(_){return null;}}
  function moduleKey(h,index){return h.dataset.personalViewKey||(h.dataset.personalViewKey='section-'+(index+1));}
  function modules(){
    const main=document.querySelector('main');if(!main)return[];
    const headings=[...main.querySelectorAll(':scope > h2')];
    return headings.map((h,index)=>{
      const nodes=[h];let node=h.nextElementSibling;
      while(node&&node.tagName!=='H2'){nodes.push(node);node=node.nextElementSibling;}
      return{key:moduleKey(h,index),label:h.textContent.trim(),nodes};
    });
  }
  function hiddenKeys(){return modules().filter(m=>m.nodes.every(n=>n.hidden)).map(m=>m.key);}
  function currentState(){
    return{
      v:1,
      municipality:document.getElementById('municipalitySelect')?.value||'',
      comparison:document.getElementById('comparisonSelect')?.value||'',
      months:(document.querySelector('.range button.active')?.dataset.months||'36'),
      hidden:hiddenKeys()
    };
  }
  function save(){if(applying)return;try{localStorage.setItem(STORAGE_KEY,JSON.stringify(currentState()));}catch(_){}}
  function applyVisibility(hidden){
    const set=new Set(Array.isArray(hidden)?hidden:[]);
    modules().forEach(m=>m.nodes.forEach(n=>n.hidden=set.has(m.key)));
    document.querySelectorAll('[data-pv-module]').forEach(input=>input.checked=!set.has(input.value));
  }
  function refreshChecks(){
    const host=document.getElementById('pvModules');if(!host)return;
    host.innerHTML=modules().map(m=>`<label class="pv-option"><input type="checkbox" data-pv-module value="${m.key}" ${m.nodes.every(n=>n.hidden)?'':'checked'}><span>${m.label}</span></label>`).join('');
    host.querySelectorAll('[data-pv-module]').forEach(input=>input.addEventListener('change',()=>{
      const mod=modules().find(m=>m.key===input.value);if(!mod)return;mod.nodes.forEach(n=>n.hidden=!input.checked);save();
    }));
  }
  function applyState(state){
    if(!state)return;applying=true;
    const municipality=document.getElementById('municipalitySelect');
    if(state.municipality&&municipality&&[...municipality.options].some(o=>o.value===state.municipality)){
      municipality.value=state.municipality;if(typeof municipality.onchange==='function')municipality.onchange();
    }
    const comparison=document.getElementById('comparisonSelect');
    if(state.comparison&&comparison&&[...comparison.options].some(o=>o.value===state.comparison)){
      comparison.value=state.comparison;if(typeof comparison.onchange==='function')comparison.onchange({target:comparison});
    }
    const range=[...document.querySelectorAll('.range button')].find(b=>b.dataset.months===String(state.months));if(range)range.click();
    applyVisibility(state.hidden||[]);refreshChecks();applying=false;save();
  }
  function injectStyle(){
    const style=document.createElement('style');
    style.textContent='.pv-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.pv-details{position:relative}.pv-details>summary,.pv-btn{list-style:none;cursor:pointer;border:1px solid #d6dfd9;border-radius:8px;background:#fff;color:var(--ink);padding:9px 11px;font:inherit;font-weight:650}.pv-details>summary::-webkit-details-marker{display:none}.pv-details[open]>summary{border-color:var(--green)}.pv-panel{position:absolute;z-index:80;top:calc(100% + 6px);right:0;width:min(360px,88vw);background:#fff;border:1px solid #dfe5e1;border-radius:10px;box-shadow:0 12px 30px rgba(15,43,54,.18);padding:12px}.pv-panel strong{display:block;margin-bottom:8px}.pv-option{display:flex;gap:8px;align-items:center;padding:6px 2px;font-size:.84rem}.pv-option input{accent-color:var(--green2)}.pv-note{font-size:.76rem;color:var(--muted);margin:8px 0 2px}.pv-feedback{font-size:.78rem;color:var(--green2);font-weight:650}.pv-btn:hover,.pv-details>summary:hover{background:#f7faf8}@media(max-width:560px){.pv-tools{width:100%}.pv-panel{position:fixed;left:16px;right:16px;top:20%;width:auto;max-height:65vh;overflow:auto}}';document.head.appendChild(style);
  }
  function injectControls(){
    const toolbar=document.querySelector('.toolbar');if(!toolbar||document.getElementById('pvControls'))return;
    const tools=document.createElement('div');tools.className='pv-tools';tools.id='pvControls';
    tools.innerHTML='<details class="pv-details" id="pvDetails"><summary>Tilpas visning</summary><div class="pv-panel"><strong>Vælg hvad du vil se</strong><div id="pvModules"></div><div class="pv-note">Dine valg gemmes kun i denne browser.</div></div></details><button class="pv-btn" id="pvShare" type="button">Del min visning</button><button class="pv-btn" id="pvReset" type="button">Nulstil</button><span class="pv-feedback" id="pvFeedback"></span>';
    const updated=document.getElementById('updated');toolbar.insertBefore(tools,updated||null);refreshChecks();
    const details=document.getElementById('pvDetails');
    details?.addEventListener('mouseleave',()=>details.removeAttribute('open'));
    document.addEventListener('pointerdown',e=>{if(details?.open&&!details.contains(e.target))details.removeAttribute('open');});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&details?.open)details.removeAttribute('open');});
    document.getElementById('pvShare').addEventListener('click',async()=>{
      const url=new URL(location.href);url.searchParams.set(PARAM,encodeState(currentState()));
      try{await navigator.clipboard.writeText(url.toString());document.getElementById('pvFeedback').textContent='Link kopieret';}
      catch(_){prompt('Kopiér dette link',url.toString());}
      setTimeout(()=>{const f=document.getElementById('pvFeedback');if(f)f.textContent='';},2500);
    });
    document.getElementById('pvReset').addEventListener('click',()=>{localStorage.removeItem(STORAGE_KEY);const url=new URL(location.href);url.searchParams.delete(PARAM);location.replace(url.toString());});
  }
  function bindSave(){
    document.getElementById('municipalitySelect')?.addEventListener('change',()=>setTimeout(save,0));
    document.getElementById('comparisonSelect')?.addEventListener('change',()=>setTimeout(save,0));
    document.querySelector('.range')?.addEventListener('click',e=>{if(e.target.closest('button'))setTimeout(save,0);});
  }
  function ready(){return typeof DATA!=='undefined'&&DATA&&document.getElementById('municipalitySelect')?.options.length>0;}
  function start(){if(!ready()){setTimeout(start,80);return;}injectStyle();injectControls();bindSave();const state=sharedState()||storedState();if(state)applyState(state);else{refreshChecks();save();}}
  start();
})();
