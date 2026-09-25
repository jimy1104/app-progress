/* ===== Modo servidor: conecta la interfaz con la API real (solo si window.GR_SERVER) ===== */
(function(){
if(!window.GR_SERVER) return;

let TOKEN=null, USER=null, FAMS=[], FILE=null, JOB=null, RES=null, POLL=null, T0=0, PAGS=0;
const FAMNAME={CM:'Contratos Menores de Bienes y Servicios',LS:'Contratación de Locadores de Servicios'};
const CUT_MAP={tdr:'tdr',req:'requerimiento',pago:'pago',os:'os'};
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>'S/ '+Number(v||0).toLocaleString('es-PE',{minimumFractionDigits:2,maximumFractionDigits:2});

function ss(k,v){try{ if(v===undefined) return sessionStorage.getItem(k); if(v===null) sessionStorage.removeItem(k); else sessionStorage.setItem(k,v);}catch(e){return null;}}

async function api(path,opt={}){
  opt.headers=Object.assign({},opt.headers||{}, TOKEN?{'Authorization':'Bearer '+TOKEN}:{});
  const r=await fetch(path,opt);
  let data={}; try{data=await r.json();}catch(e){}
  if(r.status===401 && TOKEN){ toast('Tu sesión expiró. Vuelve a ingresar.','warn'); salir(); throw new Error('401'); }
  if(!r.ok) throw new Error(data.error||('Error '+r.status));
  return data;
}
const withT=u=>u+(u.includes('?')?'&':'?')+'t='+encodeURIComponent(TOKEN);

/* ---------- login ---------- */
document.querySelectorAll('.proto-tag').forEach(e=>e.style.display='none');
window.doLogin=async function(){
  const body = role==='admin'
    ? {rol:'admin',usuario:$('a-user').value.trim(),password:$('a-pass').value,master:$('a-master').value}
    : {rol:'trabajador',nombre:$('w-name').value.trim(),password:$('w-pass').value};
  try{
    const d=await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    iniciar(d); ['a-pass','a-master','w-pass'].forEach(i=>$(i).value='');
  }catch(e){ if(e.message!=='401') toast(e.message,'warn'); }
};
function iniciar(d){
  TOKEN=d.token; USER=d.usuario; FAMS=d.familias; ss('gr_tok',TOKEN);
  if(USER.rol==='admin'){ show('admin'); document.querySelector('#admin .userchip .nm').textContent=USER.nombre; }
  else{
    $('w-chip-name').textContent=USER.nombre; $('w-chip-area').textContent=USER.area||'Trabajador';
    $('w-av').textContent=initials(USER.nombre); $('w-back').style.display='none';
    resetWorker(); show('worker');
  }
}
function salir(){ TOKEN=null; USER=null; ss('gr_tok',null); detenerPoll(); show('login'); }
window.logout=salir;
window.adminProcesar=function(){
  $('w-chip-name').textContent=USER.nombre; $('w-chip-area').textContent='Administrador · CM y Locadores';
  $('w-av').textContent='AD'; $('w-back').style.display=''; resetWorker(); show('worker');
};
// sesión guardada (al recargar la página)
(async function(){ const t=ss('gr_tok'); if(!t) return; TOKEN=t;
  try{ const d=await api('/api/me'); iniciar({token:t,usuario:d.usuario,familias:d.familias}); }catch(e){ TOKEN=null; ss('gr_tok',null); } })();

/* ---------- subprocesos permitidos por la cuenta ---------- */
const _reset=window.resetWorker;
window.resetWorker=function(){
  subprocs.length=0; (FAMS.length?FAMS:['CM','LS']).forEach(f=>subprocs.push([f,FAMNAME[f]]));
  renderSubprocs(); FILE=null; JOB=null; RES=null; detenerPoll(); _reset();
  if(subprocs.length===1){ const el=document.querySelector('#subprocGrid .sp'); if(el) pickSub(0,el); }
};

/* ---------- archivo real ---------- */
const inp=document.createElement('input'); inp.type='file'; inp.accept='.pdf,.zip'; inp.style.display='none';
document.body.appendChild(inp);
inp.addEventListener('change',()=>{ if(inp.files[0]) elegir(inp.files[0]); inp.value=''; });
window.fakePick=function(){ inp.click(); };
document.addEventListener('drop',e=>{ if(e.target.closest && e.target.closest('#dz')){ e.preventDefault(); e.stopPropagation();
  $('dz').classList.remove('drag'); const f=e.dataTransfer.files[0]; if(f) elegir(f);} },true);
function elegir(f){
  const n=f.name.toLowerCase();
  if(!(n.endsWith('.pdf')||n.endsWith('.zip'))){ toast('Sube un archivo .pdf o .zip.','warn'); return; }
  if(f.size>300*1024*1024){ toast('El archivo supera 300 MB.','warn'); return; }
  FILE=f; hasFile=true;
  $('fileslot').innerHTML=`<div class="filecard"><div class="fi">${n.endsWith('.zip')?'ZIP':'PDF'}</div>
    <div><div class="fn">${esc(f.name)}</div><div class="fm">${(f.size/1048576).toFixed(1)} MB</div></div>
    <div class="spacer"></div><button class="btn ghost sm" onclick="fakePick()">Cambiar</button>
    <button class="btn sm" onclick="goStep(2)">Continuar →</button></div>`;
  $('dz').style.display='none';
  if(window.mostrarLoteCard) window.mostrarLoteCard(f);
}

/* ---------- procesar ---------- */
window.startProcess=async function(mode){
  if(!FILE){ toast('Primero sube el expediente.','warn'); goStep(1); return; }
  if(!selSub){ toast('Elige el subproceso (es obligatorio).','warn'); return; }
  if(mode==='full' && !selDocs.length){ toast('Marca al menos un documento para cortar, o usa "Detectar riesgo".','warn'); return; }
  const fd=new FormData(); fd.append('file',FILE); fd.append('familia',selSub[0]);
  if(mode==='full') selDocs.forEach(k=>fd.append('cortar',CUT_MAP[k]||k));
  procMode=mode; goStep(3);
  $('procTitle').textContent=mode==='full'?'Cortando y verificando expediente':'Detectando riesgo';
  $('procEst').textContent='Subiendo el archivo…'; $('procMsg').textContent='Enviando el expediente al servidor…';
  $('procSteps').innerHTML=['Subir el expediente','Leer con OCR (Azure Document Intelligence)','Identificar documentos'+(mode==='full'?' y cortarlos':''),'Contrastar con la matriz de riesgos']
    .map((s,i)=>`<div class="ps" id="ps${i}"><div class="pi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 12l5 5L20 6"/></svg></div>${s}</div>`).join('');
  pasos(0); ring(2);
  try{
    const d=await subir(fd);
    JOB=d.id; PAGS=d.meta.paginas||1; T0=Date.now();
    $('procEst').textContent=`${PAGS} páginas · número de consulta ${JOB}`;
    pasos(1); POLL=setInterval(consultar,2500); consultar();
  }catch(e){ if(e.message!=='401'){ toast(e.message,'warn'); goStep(2);} }
};
function subir(fd){ // XHR para mostrar el avance de la subida
  return new Promise((ok,ko)=>{ const x=new XMLHttpRequest(); x.open('POST','/api/jobs');
    x.setRequestHeader('Authorization','Bearer '+TOKEN);
    x.upload.onprogress=e=>{ if(e.lengthComputable){ ring(2+8*e.loaded/e.total); $('procMsg').textContent=`Subiendo… ${Math.round(100*e.loaded/e.total)}%`; } };
    x.onload=()=>{ let d={}; try{d=JSON.parse(x.responseText);}catch(e){}
      if(x.status===401){ salir(); ko(new Error('401')); } else if(x.status>=200&&x.status<300) ok(d); else ko(new Error(d.error||('Error '+x.status))); };
    x.onerror=()=>ko(new Error('No se pudo conectar con el servidor.')); x.send(fd); });
}
function ring(p){ p=Math.max(0,Math.min(100,p)); $('ringFg').style.strokeDashoffset=264-264*p/100; $('procPct').textContent=Math.floor(p)+'%'; }
function pasos(n){ document.querySelectorAll('#procSteps .ps').forEach((e,i)=>{ e.classList.toggle('done',i<n); e.classList.toggle('cur',i===n); }); }
function detenerPoll(){ if(POLL){ clearInterval(POLL); POLL=null; } }
async function consultar(){
  if(!JOB) return;
  try{
    const d=await api('/api/jobs/'+JOB), m=d.meta;
    $('procMsg').textContent=(m.etapa_txt||'Procesando')+'…';
    const est=Math.max(25,PAGS*1.6), el=(Date.now()-T0)/1000;
    if(m.etapa==='ocr'||m.etapa==='en_cola'){ pasos(1); ring(10+70*Math.min(.97,el/est)); }
    else if(m.etapa==='segmentando'){ pasos(2); ring(85); }
    else if(m.etapa==='riesgo'){ pasos(3); ring(93); }
    if(m.estado==='listo'){ detenerPoll(); pasos(4); ring(100); $('procMsg').textContent='Completado'; RES=d.resultado; setTimeout(()=>showResults(),400); }
    if(m.estado==='error'){ detenerPoll(); $('procMsg').textContent='No se pudo procesar';
      $('procEst').innerHTML=`<span style="color:var(--red)">${esc(m.error)}</span><br><button class="btn sm" style="margin-top:12px" onclick="goStep(2)">Volver a intentar</button>`; }
  }catch(e){ /* reintenta en el siguiente ciclo */ }
}

/* ---------- resultados ---------- */
const ORD={'MUY ALTO':0,'ALTO':1,'MEDIO':2};
window.showResults=function(){
  if(!RES) return;
  goStep(4);
  risks=[...RES.riesgos].sort((a,b)=>(a.nivel!=='rojo')-(b.nivel!=='rojo')||(ORD[a.nivel_matriz]??3)-(ORD[b.nivel_matriz]??3));
  const nR=risks.filter(r=>r.nivel==='rojo').length, nA=risks.length-nR, ver=RES.verificados||[];
  const cal=RES.calidad||{};
  $('resSub').textContent=`${RES.subproceso} · ${RES.archivo} · ${RES.paginas} páginas · lectura OCR ${(100*(RES.conf_ocr||0)).toFixed(1)}% de palabras seguras (${RES.provider==='azure-document-intelligence'?'Azure':RES.provider})`
    +((cal.hojas_en_blanco||[]).length?` · ${cal.hojas_en_blanco.length} reverso(s) en blanco`:'');
  document.querySelector('#ws4 .counts').innerHTML=
    `<span><b style="color:var(--red)">${nR}</b> confirmados</span><span><b style="color:var(--amber)">${nA}</b> por revisar</span>`+
    `<span><b style="color:var(--ok)">${ver.length}</b> verificados sin observación</span><span><b>${RES.cortes.length}</b> documentos cortados</span>`;
  const lg=document.querySelector('#ws4 .legend');
  if(lg) lg.innerHTML=`<span class="lg"><span class="sw" style="background:var(--red)"></span>Rojo — confirmado: se revisó dos veces con lectura clara</span>
    <span class="lg"><span class="sw" style="background:var(--amber-accent)"></span>Amarillo — por revisar: lectura dudosa o requiere criterio</span>`;
  extras(ver);
  detalleOCR();
  $('riskList').innerHTML=risks.length?risks.map(card).join(''):
    `<div class="card" style="text-align:center;color:var(--muted)">No se identificaron riesgos para este subproceso con la lectura obtenida.</div>`;
};
function detalleOCR(){
  const o=RES.ocr||{}; const host=$('resSub'); if(!host) return;
  const bajo=(o.paginas_bajo_umbral||[]).length, mej=(o.paginas_mejoradas||[]).length;
  const ver=(RES.calidad||{}).verificadas||0;
  if(!o.relecturas && !bajo) return;
  const det=document.createElement('div'); det.className='rsub'; det.style.marginTop='6px';
  det.innerHTML=`Lectura reforzada: se releyeron ${o.relecturas||0} página(s) con la imagen limpia y sin sellos`
    + (ver?` (${ver} palabras confirmadas por dos lecturas)`:'')
    + (mej?`, mejoraron ${mej}`:'')
    + (bajo?` · <b>${bajo} página(s) con palabras dudosas (menos del ${Math.round((o.umbral||0.95)*100)}% seguras)</b>: ${(o.paginas_bajo_umbral||[]).slice(0,15).join(', ')}${bajo>15?'…':''} — conviene mirarlas.`:' · todas las páginas por encima del objetivo.');
  host.after(det);
}
function extras(ver){
  let box=$('srvExtra'); if(!box){ box=document.createElement('div'); box.id='srvExtra';
    document.querySelector('#ws4 .result-head').after(box); }
  const c=RES.contexto||{}, ac=RES.acumulado_previo||{};
  const COL=['#2f6fde','#16a34a','#d97706','#9333ea','#dc2626','#0891b2','#65a30d','#db2777','#4f46e5','#b45309'];
  const docs=(RES.documentos||[]).map((s,i)=>{
    const rs=(s.riesgos||[]), nr=rs.filter(r=>r.nivel==='rojo').length;
    const chips=rs.map(r=>`<span class="tag ${r.nivel==='rojo'?'revw':'cut'}" title="${esc(r.hecho)}">${esc(r.id)}</span>`).join(' ');
    return `<div class="blitem" style="border-left:4px solid ${COL[i%COL.length]}"><b>pág. ${s.pagina_ini}${s.pagina_fin!==s.pagina_ini?'–'+s.pagina_fin:''}</b> — ${esc(s.etiqueta)}`
      +((s.blancas||[]).length?` <span class="rsub">(reverso en blanco: ${s.blancas.join(', ')})</span>`:'')
      +(s.revisar?` <span class="tag cut" title="La frontera de este documento tiene poca evidencia">revisar corte</span>`:'')
      +(rs.length?`<br><span class="rsub">${rs.length} riesgo(s)${nr?`, <b style="color:var(--red)">${nr} confirmado(s)</b>`:''}:</span> ${chips}`:'<br><span class="rsub">sin riesgos ubicados en este documento</span>')
      +`</div>`;}).join('');
  const mapa=(RES.mapa_paginas||[]).map(p=>{
    const c=p.documento==null?'#cbd5e1':COL[p.documento%COL.length], blanca=/blanco/.test(p.rol);
    return `<a href="${withT('/api/jobs/'+JOB+'/expediente.pdf')}#page=${p.pagina}" target="_blank" rel="noopener" title="Hoja ${p.pagina}: ${esc(p.etiqueta||'sin documento')} · ${esc(p.rol)}"
      style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:34px;margin:2px;border-radius:4px;font-size:11px;text-decoration:none;
      ${blanca?`background:repeating-linear-gradient(45deg,#fff,#fff 3px,${c}33 3px,${c}33 6px);color:${c};border:1px dashed ${c}`:`background:${c};color:#fff`};${p.rol==='inicio'?'box-shadow:inset 0 3px 0 rgba(0,0,0,.35)':''}">${p.pagina}</a>`;}).join('');
  const descargas=`${RES.buscable?`<a class="btn ghost sm" href="${withT('/api/jobs/'+JOB+'/buscable.pdf')}">⬇ Expediente buscable (PDF con texto)</a>`:''}
     <a class="btn ghost sm" href="${withT('/api/jobs/'+JOB+'/texto.txt')}">⬇ Todo el texto leído (.txt)</a>`;
  const EST={'confirmado':['✓','var(--ok)'],'corregido':['✎','var(--amber)'],'dudoso':['?','var(--red)'],'sin confirmar':['?','var(--amber)'],'en conflicto':['!','var(--red)'],'lectura descartada':['✗','var(--muted)']};
  const vals=(RES.validaciones||[]).map(v=>{const e=EST[v.estado]||['·','var(--muted)'];
    return `<div class="rsub" style="margin-top:4px"><b style="color:${e[1]}">${e[0]} ${esc(v.dato)} ${esc(v.estado)}</b>${v.valor!=null?' — '+esc(v.dato==='monto'?money(v.valor):v.valor):''}${v.corregido_de?` (se leyó «${esc(v.dato==='monto'?money(v.corregido_de):v.corregido_de)}»)`:''} · ${esc(v.detalle||'')}</div>`;}).join('');
  const cortes=(RES.cortes||[]).map(x=>`<a class="btn ghost sm" href="${withT('/api/jobs/'+JOB+'/corte/'+x.i)}">⬇ ${esc(x.etiqueta)} (pág. ${x.pagina_ini}–${x.pagina_fin})</a>`).join(' ');
  const verif=ver.map(v=>`<div class="blitem" style="border-color:var(--ok)"><b>${esc(v.id)}</b> — ${esc(v.hecho)}<br><span class="rsub">✓ ${esc(v.motivo)}</span></div>`).join('');
  box.innerHTML=`<div class="card">
     <div class="clabel">Datos leídos de la orden</div>
     <div class="cdesc" style="margin-bottom:8px">Se usan para el acumulado anual de fraccionamiento (8 UIT = S/ 44,000). Verifíquelos: si el OCR leyó mal, el cálculo cambia.</div>
     <div class="bllist">
       <div class="blitem"><b>Orden</b> — ${c.os?'N° '+esc(c.os):'<i>no se pudo leer</i>'} &nbsp; <b>RUC</b> — ${esc(c.ruc)||'<i>no leído</i>'} &nbsp; <b>Monto</b> — ${c.monto?money(c.monto):'<i>no leído</i>'}</div>
       <div class="blitem"><b>Objeto</b> — ${esc(c.objeto)||'<i>no leído</i>'}</div>
       <div class="blitem"><b>Acumulado previo del mismo objeto (${esc(c.anio)})</b> — ${ac.ordenes||0} orden(es), ${money(ac.monto)}</div>
     </div>${vals?`<div class="clabel" style="margin-top:12px">Validación cruzada de los datos</div>${vals}`:''}</div>
   <div class="card"><div class="clabel">Mapa del expediente — qué es cada hoja</div>
     <div class="cdesc" style="margin:4px 0 6px">Cada color es un documento; la raya de arriba marca su primera hoja; las rayadas son reversos en blanco. Clic para abrir esa hoja.</div>
     <div style="display:flex;flex-wrap:wrap">${mapa}</div>
     <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">${descargas}</div></div>
   <div class="card"><div class="clabel">Documentos identificados en el expediente</div><div class="bllist" style="margin-top:8px">${docs||'<span class="rsub">No se identificaron cabeceras de documentos.</span>'}</div>
     ${cortes?`<div class="clabel" style="margin-top:16px">Documentos cortados</div><div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">${cortes}</div>`:''}</div>
   ${ver.length?`<details class="card"><summary class="clabel" style="cursor:pointer">✓ Controles verificados sin observación (${ver.length})</summary><div class="bllist" style="margin-top:10px">${verif}</div></details>`:''}`;
}
function card(r,i){
  const rojo=r.nivel==='rojo';
  const bl=(r.base_legal||[]).map(b=>`<div class="blitem"><b>${esc(b.dispositivo)}</b>${b.contenido?' — '+esc(b.contenido):''}</div>`).join('');
  const ev=r.evidencia?`<div class="cita">${esc(r.evidencia)}</div>`:'';
  const ej=r.ejemplo?`<div class="rsection"><div class="rlab">${IC.shield}Caso real donde ocurrió (exp. ${esc(r.ejemplo.expedientes)})</div><p>${esc((r.ejemplo.hecho||'').slice(0,600))}${(r.ejemplo.hecho||'').length>600?'…':''}</p></div>`:'';
  return `<div class="risk ${rojo?'red':'amber'}"><div class="rbar"></div>
    <div class="risk-top"><div class="rdot">${rojo?'⚠':'?'}</div><div style="flex:1">
      <div class="rttl">${esc(r.hecho)}</div>
      <div class="rmeta"><span class="rbadge">${rojo?'Confirmado':'Por revisar'}</span>
        <span class="tag ${r.nivel_matriz==='MUY ALTO'?'revw':'cut'}">Nivel ${esc(r.nivel_matriz)}</span>
        <span class="rsub mono">${esc(r.id)}${(r.ubicaciones&&r.ubicaciones.length)?' · pág. '+r.ubicaciones.map(u=>u.pagina).slice(0,4).join(', ')+(r.ubicaciones.length>4?'…':''):' · sin renglón (ausencia)'}</span>
        ${r.documento?`<span class="rsub">· en: <b>${esc(r.documento)}</b>${(r.documento_paginas||[]).length?` (pág. ${r.documento_paginas[0]}${r.documento_paginas[1]!==r.documento_paginas[0]?'–'+r.documento_paginas[1]:''})`:''}</span>`:''}</div></div></div>
    <div class="risk-body">
      <div class="rsection"><div class="rlab">${IC.law}Marco legal</div><div class="bllist">${bl}</div></div>
      <div class="rsection"><div class="rlab">${IC.doc}El hecho — dónde está el riesgo</div><p>${esc(r.nota)}</p>${ev}</div>
      ${ej}
    </div>
    <div class="locbox" id="loc${i}"></div>
    <div class="risk-actions">
      <button class="btn subtle sm" onclick="toggleLoc(${i})">${IC.pin}Ubicar en el documento${(r.ubicaciones&&r.ubicaciones.length)?' ('+r.ubicaciones.length+')':''}</button>
      <button class="btn ghost sm" onclick="openDrawer(${i})">${IC.shieldsm}Tomar medidas de control</button>
    </div></div>`;
}
window.toggleLoc=function(i){
  const r=risks[i], box=$('loc'+i);
  if(box.classList.contains('show')){ box.classList.remove('show'); return; }
  const us=r.ubicaciones||[];
  if(!us.length){
    box.innerHTML=`<div class="lrow"><span class="pgtag">Sin renglón</span>
      <span>${r.nota&&/No obra|no se ubic/i.test(r.nota)
        ? 'Este hallazgo es por AUSENCIA: no hay un renglón que señalar porque el documento no aparece en el expediente.'
        : 'Este riesgo requiere criterio: revise el expediente con el procedimiento de auditoría.'}</span></div>
      <div class="lactions"><a class="btn ghost sm" target="_blank" rel="noopener" href="${withT('/api/jobs/'+JOB+'/expediente.pdf')}">Abrir el expediente completo</a></div>`;
    box.classList.add('show'); return;
  }
  const chips=us.map((u,k)=>`<button class="btn ${k?'ghost':''} sm" onclick="verUbic(${i},${k})" id="ub${i}_${k}">Pág. ${u.pagina}</button>`).join(' ');
  box.innerHTML=`<div class="lrow"><span class="pgtag">${us.length} ubicación${us.length===1?'':'es'}</span>
      <span>Se resalta el renglón exacto donde el programa lo encontró.</span></div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">${chips}</div>
    <div id="ubv${i}"></div>`;
  box.classList.add('show'); verUbic(i,0);
};
window.verUbic=function(i,k){
  const r=risks[i], u=(r.ubicaciones||[])[k]; if(!u) return;
  (r.ubicaciones||[]).forEach((_,j)=>{ const b=$('ub'+i+'_'+j); if(b) b.className='btn '+(j===k?'':'ghost ')+'sm'; });
  const b=u.bbox||[0,0,1,0.02], p=u.pagina;
  $('ubv'+i).innerHTML=`
    ${u.texto?`<div class="cita" style="margin-top:10px;border-color:var(--amber-accent);background:var(--amber-bg)">«${esc(u.texto)}»${u.documento?`<br><span class="rsub">Hoja ${p} · ${esc(u.documento)}</span>`:''}</div>`:''}
    <div style="position:relative;margin-top:10px;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff">
      <img src="${withT('/api/jobs/'+JOB+'/pagina/'+p+'.png')}" style="width:100%;display:block" alt="Página ${p}" loading="lazy">
      <div style="position:absolute;left:${Math.max(0,b[0]*100-0.6)}%;top:${Math.max(0,b[1]*100-0.4)}%;
        width:${Math.min(100,(b[2]-b[0])*100+1.2)}%;height:${Math.max(1.0,(b[3]-b[1])*100+0.8)}%;
        background:rgba(226,164,0,.25);outline:2px solid #e2a400;border-radius:2px;box-shadow:0 0 0 9999px rgba(0,0,0,.06)"></div>
    </div>
    <div class="lactions">
      <a class="btn sm" href="${withT('/api/jobs/'+JOB+'/pagina/'+p+'.pdf')}">Descargar solo esta página</a>
      <a class="btn ghost sm" target="_blank" rel="noopener" href="${withT('/api/jobs/'+JOB+'/expediente.pdf')}#page=${p}">Abrir el expediente en la pág. ${p}</a>
    </div>`;
};
window.openDrawer=function(i){
  const r=risks[i];
  $('drawerSub').textContent=r.hecho;
  const pasos=(r.control||'').split(/(?:^|\s)-\s+/).map(s=>s.trim()).filter(Boolean);
  const bl=(r.base_legal||[]).map(b=>`<div class="blitem"><b>${esc(b.dispositivo)}</b>${b.contenido?' — '+esc(b.contenido):''}</div>`).join('');
  let h=`<div class="medida"><div class="mh"><div class="mnum">§</div><div class="mt">Plan de control a implementar</div></div>`;
  (pasos.length?pasos:[r.control||'—']).forEach((p,n)=>h+=`<div class="mrow"><div class="mlab">Acción ${n+1}</div><p>${esc(p)}</p></div>`);
  h+=`<div class="mrow"><div class="mlab">Quién ejecuta</div><p>${esc(r.ejecuta)||'—'}</p></div><div class="mrow"><div class="mlab">Quién supervisa</div><p>${esc(r.supervisa)||'—'}</p></div></div>`;
  if(r.como_verificar) h+=`<div class="medida"><div class="mh"><div class="mnum">?</div><div class="mt">Cómo verificarlo (procedimiento de auditoría)</div></div><div class="mrow"><p>${esc(r.como_verificar)}</p></div></div>`;
  h+=`<div class="medida"><div class="mh"><div class="mnum">⚖</div><div class="mt">Fundamento legal</div></div><div class="bllist">${bl}</div></div>`;
  if(r.ejemplo) h+=`<div class="medida"><div class="mh"><div class="mnum">✓</div><div class="mt">Medidas aplicadas en un caso real</div></div>
     <div class="mrow"><div class="mlab">Correctiva</div><p>${esc(r.ejemplo.medida_correctiva)||'—'}</p></div>
     <div class="mrow"><div class="mlab">Preventiva</div><p>${esc(r.ejemplo.medida_preventiva)||'—'}</p></div></div>`;
  $('drawerBody').innerHTML=h; $('drawer').classList.add('show'); $('drawerOverlay').classList.add('show');
};
window.downloadExcel=function(){ if(!JOB) return; window.location.href=withT('/api/jobs/'+JOB+'/excel'); toast('Descargando el Excel…','ok'); };
window.cleanQuery=async function(){
  if(!JOB){ resetWorker(); return; }
  if(!confirm('¿Eliminar esta consulta? Se borran el expediente, los cortes y los resultados guardados.')) return;
  try{ await api('/api/jobs/'+JOB,{method:'DELETE'}); toast('Consulta eliminada. No quedó nada guardado.','ok');
    const ex=$('srvExtra'); if(ex) ex.innerHTML=''; setTimeout(()=>resetWorker(),500);
    if(USER&&USER.rol==='admin') cargarAdmin(); }catch(e){ toast(e.message,'warn'); }
};

/* ---------- administrador ---------- */
async function cargarAdmin(){
  try{
    const [a,j,u]=await Promise.all([api('/api/admin/actividad'),api('/api/jobs'),api('/api/admin/usuarios')]);
    const hoy=new Date().toLocaleDateString('en-CA');   // fecha local (Lima), no UTC
    const v=document.querySelectorAll('#tab-actividad .stat .v'), k=document.querySelectorAll('#tab-actividad .stat .k');
    const nHoy=j.jobs.filter(x=>(x.creado||'').startsWith(hoy)).length;
    [[ 'Consultas hoy',nHoy],['En proceso',j.jobs.filter(x=>x.estado==='procesando'||x.estado==='en_cola').length],
     ['Usuarios registrados',u.usuarios.length],['Copias temporales',j.jobs.length]].forEach((s,i)=>{k[i].textContent=s[0]; v[i].textContent=s[1];});
    document.querySelector('#tab-actividad .panel-head .tstamp').textContent='Actualizado '+new Date().toLocaleTimeString('es-PE',{hour:'2-digit',minute:'2-digit'});
    $('actbody').innerHTML=a.actividad.slice(0,120).map(x=>`<tr><td><b>${esc(x.usuario)}</b></td><td>${esc(x.area)}</td>
      <td><span class="tag ${/Error|fallido/.test(x.accion)?'risk':(/Limpi|Elimin/.test(x.accion)?'clean':'consulta')}">${esc(x.accion)}</span>${x.detalle?`<div class="rsub">${esc(x.detalle)}</div>`:''}</td>
      <td class="mono">${esc(x.expediente)}</td><td class="tstamp">${esc(x.t)}</td></tr>`).join('')||`<tr><td colspan="5" style="text-align:center;color:var(--faint);padding:30px">Sin actividad todavía.</td></tr>`;
    window._jobs=j.jobs;
    $('filesbody').innerHTML=j.jobs.map((x,i)=>`<tr><td class="mono"><b>${esc(x.resumen&&x.resumen.os?'OS '+x.resumen.os:x.archivo)}</b><div class="rsub">${esc(x.archivo)}</div></td>
      <td>${esc(x.usuario)}</td><td><span class="tag ${x.estado==='listo'?'cut':(x.estado==='error'?'risk':'consulta')}">${esc(x.estado==='listo'?(x.resumen?`${x.resumen.rojo} conf. · ${x.resumen.amarillo} rev.`:'Listo'):(x.estado==='error'?'Error':'Procesando'))}</span></td>
      <td class="tstamp">${esc(x.creado)}</td><td><div class="rowact" style="justify-content:flex-end">
      ${x.estado==='listo'?`<button class="iconbtn" title="Ver resultados" onclick="verJob('${x.id}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg></button>`:''}
      <button class="iconbtn del" title="Eliminar" onclick="borrarJob('${x.id}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg></button></div></td></tr>`).join('')
      ||`<tr><td colspan="5" style="text-align:center;color:var(--faint);padding:34px">No hay copias temporales guardadas.</td></tr>`;
    $('ucount').textContent=u.usuarios.length+' usuario'+(u.usuarios.length===1?'':'s');
    $('usersbody').innerHTML=u.usuarios.map(x=>`<tr><td><b>${esc(x.nombre)}</b></td><td>${esc(x.area)}</td>
      <td><span class="mono rsub">•••••••• (cifrada)</span></td><td class="tstamp">${esc(x.creado)}</td>
      <td><div class="rowact" style="justify-content:flex-end">
      <button class="iconbtn" title="Generar nueva contraseña" onclick="resetUser('${x.id}','${esc(x.nombre)}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 019-9 9 9 0 016.7 3M21 12a9 9 0 01-9 9 9 9 0 01-6.7-3"/><path d="M17 6h3V3M7 18H4v3"/></svg></button>
      <button class="iconbtn del" title="Eliminar" onclick="delUserSrv('${x.id}','${esc(x.nombre)}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg></button></div></td></tr>`).join('')
      ||`<tr><td colspan="5" style="text-align:center;color:var(--faint);padding:34px">Aún no hay trabajadores. Usa «Crear usuario».</td></tr>`;
  }catch(e){ if(e.message!=='401') toast(e.message,'warn'); }
}
const _tab=window.adminTab; window.adminTab=function(t,el){ _tab(t,el); if(USER&&USER.rol==='admin') cargarAdmin(); };
window.verJob=async function(id){
  try{ const d=await api('/api/jobs/'+id); JOB=id; RES=d.resultado;
    $('w-chip-name').textContent=USER.nombre; $('w-chip-area').textContent='Revisión de consulta'; $('w-av').textContent='AD'; $('w-back').style.display='';
    show('worker'); showResults(); }catch(e){ toast(e.message,'warn'); }
};
window.borrarJob=async function(id){ if(!confirm('¿Eliminar esta copia temporal y sus archivos?')) return;
  try{ await api('/api/jobs/'+id,{method:'DELETE'}); toast('Copia eliminada.','ok'); cargarAdmin(); }catch(e){ toast(e.message,'warn'); } };
// crear usuario: la contraseña la genera el servidor y se muestra una sola vez
$('nu-area').innerHTML=['Contratos Menores de Bienes y Servicios','Contratación de Locadores de Servicios','Ambos subprocesos'].map(a=>`<option>${a}</option>`).join('');
window.openUserModal=function(){ $('nu-name').value=''; $('nu-pass').textContent='se genera al crear';
  const b=document.querySelector('#userModal .genpass button'); if(b) b.style.display='none';
  const f=document.querySelector('#userModal .modal-foot .btn:not(.ghost)'); f.textContent='Crear cuenta'; f.onclick=crearUsuarioSrv;
  $('userModal').classList.add('show'); };
async function crearUsuarioSrv(){
  try{ const d=await api('/api/admin/usuarios',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nombre:$('nu-name').value,area:$('nu-area').value})});
    $('nu-pass').textContent=d.password;
    const f=document.querySelector('#userModal .modal-foot .btn:not(.ghost)'); f.textContent='Listo, ya la anoté'; f.onclick=()=>{ closeUserModal(); };
    toast('Usuario creado. Anota la contraseña: solo se muestra una vez.','ok'); cargarAdmin();
  }catch(e){ toast(e.message,'warn'); } }
window.createUser=crearUsuarioSrv;
window.resetUser=async function(id,n){ if(!confirm('¿Generar una nueva contraseña para '+n+'? La anterior dejará de funcionar.')) return;
  try{ const d=await api('/api/admin/usuarios/'+id+'/reset',{method:'POST'}); prompt('Nueva contraseña de '+n+' (cópiala, solo se muestra una vez):',d.password); }catch(e){ toast(e.message,'warn'); } };
window.delUserSrv=async function(id,n){ if(!confirm('¿Eliminar la cuenta de '+n+'?')) return;
  try{ await api('/api/admin/usuarios/'+id,{method:'DELETE'}); toast(n+' fue eliminado.','ok'); cargarAdmin(); }catch(e){ toast(e.message,'warn'); } };
const bl=document.querySelector('#tab-archivos .panel-head .btn'); if(bl){ bl.textContent='Limpiar las de más de 24 h';
  bl.onclick=async()=>{ if(!confirm('¿Eliminar todas las copias temporales con más de 24 horas?')) return;
    try{ const d=await api('/api/admin/limpiar',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"horas":24}'}); toast(d.eliminadas+' copia(s) eliminada(s).','ok'); cargarAdmin(); }catch(e){ toast(e.message,'warn'); } }; }
// admin: al volver al panel, refrescar
const _show=window.show; window.show=function(id){ _show(id); if(id==='admin'&&USER&&USER.rol==='admin') cargarAdmin(); };

// ---------------- Sistema y respaldo ----------------
async function pintarSistema(){
  const tag=$('ocrTag'), info=$('ocrInfo'); if(!tag) return;
  try{
    const c=await api('/api/config'); const o=c.ocr||{};
    const nombre={azure:'Azure (en la nube)',local:'OCR local, en esta PC',cache:'Caché de pruebas'}[o.motor]||o.motor;
    tag.textContent=o.listo?'Listo':'Falta configurar'; tag.className='tag '+(o.listo?'ok':'revw');
    info.innerHTML='<b>'+nombre+'</b> — '+(o.detalle||'')+
      (o.listo?'':'<div style="margin-top:8px">Instala Tesseract con el idioma español y vuelve a abrir la aplicación. '+
        'El instalador para Windows está en <span class="mono">github.com/UB-Mannheim/tesseract/wiki</span> (marca «Spanish» al instalar).</div>')+
      '<div style="margin-top:8px">Carpeta de datos: <span class="mono">'+(c.data_dir||'')+'</span></div>';
  }catch(e){ info.textContent=e.message; }
}
window.descargarRespaldo=function(){ location.href=withT('/api/admin/respaldo'); toast('Guarda ese ZIP en un lugar seguro.','ok'); };
window.restaurarRespaldo=async function(inp){
  const f=inp.files[0]; inp.value=''; if(!f) return;
  if(!confirm('Restaurar el respaldo reemplaza las cuentas y el acumulado actuales. ¿Continuar?')) return;
  const fd=new FormData(); fd.append('archivo',f);
  try{ const d=await api('/api/admin/restaurar',{method:'POST',body:fd});
    toast('Restaurado: '+d.restaurados.join(', '),'ok'); cargarAdmin();
  }catch(e){ toast(e.message,'warn'); } };
const _tab2=window.adminTab; window.adminTab=function(t,el){ _tab2(t,el); if(t==='sistema') pintarSistema(); };

/* ---------- varios expedientes de una vez ---------- */
let LOTE=null, POLLL=null;
window.toggleLote=function(el){ el.classList.toggle('on'); };
function esLote(){ const c=$('chipLote'); return !!(c&&c.classList.contains('on')); }
const _elegir2=window.mostrarLoteCard=function(f){
  const card=$('loteCard'); if(!card) return;
  const zip=/\.zip$/i.test(f.name);
  card.style.display=zip?'':'none';
  if(!zip){ const c=$('chipLote'); if(c) c.classList.remove('on'); }
};
window.startProcessLote=async function(mode){
  const fd=new FormData(); fd.append('file',FILE); fd.append('familia',selSub[0]);
  if(mode==='full') selDocs.forEach(k=>fd.append('cortar',CUT_MAP[k]||k));
  goStep(3);
  $('procTitle').textContent='Procesando varios expedientes';
  $('procMsg').textContent='Enviando el ZIP al servidor…'; $('procEst').textContent='';
  $('procSteps').innerHTML=['Subir el ZIP','Separar los expedientes','Procesar uno por uno','Armar el resumen del lote']
    .map((s,i)=>`<div class="ps" id="ps${i}"><div class="pi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 12l5 5L20 6"/></svg></div>${s}</div>`).join('');
  pasos(0); ring(2);
  try{
    const d=await new Promise((ok,ko)=>{ const x=new XMLHttpRequest(); x.open('POST','/api/lotes');
      x.setRequestHeader('Authorization','Bearer '+TOKEN);
      x.upload.onprogress=e=>{ if(e.lengthComputable){ ring(2+8*e.loaded/e.total); $('procMsg').textContent=`Subiendo… ${Math.round(100*e.loaded/e.total)}%`; } };
      x.onload=()=>{ let r={}; try{r=JSON.parse(x.responseText);}catch(e){}
        if(x.status===401){ salir(); ko(new Error('401')); } else if(x.status>=200&&x.status<300) ok(r); else ko(new Error(r.error||('Error '+x.status))); };
      x.onerror=()=>ko(new Error('No se pudo conectar con el servidor.')); x.send(fd); });
    LOTE=d.lote; pasos(2); pintarLote(d.estado); goStep(5);
    POLLL=setInterval(consultarLote,3000); consultarLote();
  }catch(e){ if(e.message!=='401'){ toast(e.message,'warn'); goStep(2);} }
};
async function consultarLote(){
  if(!LOTE) return;
  try{ const d=await api('/api/lotes/'+LOTE); pintarLote(d);
    if(d.terminado){ clearInterval(POLLL); POLLL=null; }
  }catch(e){}
}
function pintarLote(d){
  if(!d) return;
  $('loteSub').innerHTML=`${esc(d.archivo||'')} · <b>${d.total}</b> expedientes · `+
    (d.terminado?`terminado (${d.listos} procesados${d.errores?', '+d.errores+' con error':''})`
                :`procesando… ${d.listos} de ${d.total} listos`);
  $('lotebody').innerHTML=d.hijos.map((h,i)=>{
    const r=h.resumen||{}; const fin=h.estado==='listo';
    const est=h.estado==='error'?`<span class="tag revw">Error</span>`
      :fin?`<span class="tag ok">Listo</span>`
      :`<span class="tag">${esc(h.etapa_txt||'En fila')}</span>`;
    return `<tr><td>${i+1}</td><td>${esc(h.archivo)}${r.os?` <span class="mono">OS ${esc(r.os)}</span>`:''}</td>
      <td>${h.paginas||''}</td><td>${est}</td>
      <td>${fin?`<b style="color:var(--red)">${r.rojo||0}</b>`:'—'}</td>
      <td>${fin?`<b style="color:var(--amber)">${r.amarillo||0}</b>`:'—'}</td>
      <td style="text-align:right">${fin?`<button class="btn subtle sm" onclick="verExpedienteLote('${h.id}')">Ver detalle</button>`:
        (h.estado==='error'?`<span style="color:var(--red);font-size:12px">${esc(h.error||'')}</span>`:'')}</td></tr>`;
  }).join('')||`<tr><td colspan="7">Sin expedientes.</td></tr>`;
  const b=$('btnLoteExcel'); if(b) b.disabled=!d.listos;
  const dl=$('deslindeBoxLote'); if(dl&&!dl.innerHTML){ const o=$('deslindeBox'); if(o) dl.innerHTML=o.innerHTML; }
}
window.descargarExcelLote=function(){ if(LOTE) location.href=withT('/api/lotes/'+LOTE+'/excel'); };
window.verExpedienteLote=async function(jid){
  try{ const d=await api('/api/jobs/'+jid); JOB=jid; RES=d.resultado; showResults();
    const bar=document.querySelector('#ws4 .export-bar');
    if(bar && !bar.querySelector('.volver-lote')){
      const b=document.createElement('button'); b.className='btn ghost volver-lote'; b.textContent='← Volver al lote';
      b.onclick=()=>goStep(5); bar.insertBefore(b,bar.children[1]); }
  }catch(e){ toast(e.message,'warn'); } };
// enganches: mostrar la tarjeta de lote al elegir ZIP y desviar el procesamiento
const _sp=window.startProcess;
window.startProcess=function(mode){
  if(!FILE){ toast('Primero sube el expediente.','warn'); goStep(1); return; }
  if(!selSub){ toast('Elige el subproceso (es obligatorio).','warn'); return; }
  if(mode==='full' && !selDocs.length){ toast('Marca al menos un documento para cortar, o usa "Detectar riesgo".','warn'); return; }
  if(esLote()) return startProcessLote(mode);
  return _sp(mode);
};
const _rw=window.resetWorker;
window.resetWorker=function(){ LOTE=null; if(POLLL){ clearInterval(POLLL); POLLL=null; }
  const c=$('chipLote'); if(c) c.classList.remove('on');
  const lc=$('loteCard'); if(lc) lc.style.display='none';
  const vb=document.querySelector('#ws4 .volver-lote'); if(vb) vb.remove();
  _rw(); };
})();
