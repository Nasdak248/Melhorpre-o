'use strict';
const $ = s => document.querySelector(s);
const form = $('#route-form');
let token = sessionStorage.getItem('flex-token') || '';
let routes = [], history = [], chart, timer;
const money = v => new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v));
const time = v => new Date(v).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'});
const day = v => v.split('-').reverse().join('/');
function notify(message){ $('#status').textContent=message; $('#status').style.display='block'; clearTimeout(timer); timer=setTimeout(()=>$('#status').style.display='none',7000); }
async function api(path, options={}) {
 const response = await fetch('/api/'+path,{...options,headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json',...options.headers}});
 const data = await response.json();
 if(!response.ok) {
  if(response.status===401){sessionStorage.removeItem('flex-token'); $('#dashboard').hidden=true; $('#login').hidden=false;}
  throw new Error(data.error || 'Não foi possível concluir a operação.');
 }
 return data;
}
function element(tag, text, className){const node=document.createElement(tag); if(text!==undefined) node.textContent=text;if(className) node.className=className;return node;}
function latest(id){return history.filter(h=>String(h.rota_id)===String(id)).at(-1);}
function renderRoutes(){
 $('#total').textContent=routes.length;
 $('#active').textContent=routes.filter(r=>r.ativo).length;
 $('#deals').textContent=routes.filter(r=>{const h=latest(r.id);return h && Number(h.preco)<=Number(r.max_preco_alerta);}).length;
 $('#empty-routes').hidden=routes.length>0;
 $('#routes').replaceChildren();
 for(const route of routes){
  const row=element('article',undefined,'route');
  const name=element('div');name.append(element('h3',route.apelido),element('span',route.origem+' → '+route.destino,'pair'),document.createTextNode(' '),element('span',route.ativo?'Ativa':'Pausada','badge'+(route.ativo?'':' paused')));
  name.append(element('small',day(route.data_inicio)+' a '+day(route.data_fim),'dates'));
  const ceiling=element('div');ceiling.append(element('small','Seu teto de alerta'),element('div',money(route.max_preco_alerta),'price'));
  const quote=element('div');const h=latest(route.id);quote.append(element('small','Última cotação no filtro'),element('div',h?money(h.preco):'Aguardando busca','price'));if(h)quote.append(element('small','Voo '+day(h.data_voo)),element('small',time(h.data_consulta)));
  const actions=element('div',undefined,'actions');
  for(const [label,action] of [['Editar',()=>edit(route)],['Duplicar',()=>edit({...route,id:'',apelido:route.apelido+' (cópia)'})],[route.ativo?'Pausar':'Ativar',()=>toggle(route)],['Excluir',()=>remove(route)]]){
   const button=element('button',label,label==='Excluir'?'danger':'secondary');button.onclick=action;actions.append(button);
  }
  row.append(name,ceiling,quote,actions);$('#routes').append(row);
 }
}
function renderChart(){
 if(chart)chart.destroy();
 $('#empty-chart').hidden=history.length>0;
 if(!window.Chart){notify('Não foi possível carregar o gráfico. Verifique sua conexão.');return;}
 const colors=['#00896f','#6476df','#ed9657','#bc67aa','#309abc','#c2a33e','#6d9c63'];
 const groups=new Map();
 history.forEach(h=>{if(!groups.has(h.rota_id))groups.set(h.rota_id,[]);groups.get(h.rota_id).push({x:new Date(h.data_consulta).getTime(),y:Number(h.preco),flight:h.data_voo});});
 const moments=history.map(h=>new Date(h.data_consulta).getTime());
 const first=moments.length?Math.min(...moments):undefined;
 const last=moments.length?Math.max(...moments):undefined;
 chart=new Chart($('#chart'),{type:'line',data:{datasets:[...groups].map(([id,data],i)=>{
  const r=routes.find(r=>String(r.id)===String(id));return {label:r?`${r.origem} → ${r.destino} · ${r.apelido}`:String(id),data,borderColor:colors[i%colors.length],backgroundColor:colors[i%colors.length],borderWidth:2,pointRadius:3,tension:.2};
 })},options:{animation:false,responsive:true,maintainAspectRatio:false,parsing:false,interaction:{mode:'nearest',intersect:false},plugins:{legend:{position:'bottom',labels:{usePointStyle:true,boxWidth:7,padding:20}},tooltip:{callbacks:{title:items=>time(items[0].parsed.x),label:ctx=>ctx.dataset.label+': '+money(ctx.parsed.y)+' · voo '+day(ctx.raw.flight)}}},scales:{x:{type:'linear',min:moments.length?(first===last?first-3600000:first):undefined,max:moments.length?(first===last?last+3600000:last):undefined,grid:{display:false},ticks:{maxTicksLimit:5,callback:value=>time(value)}},y:{ticks:{callback:v=>money(v)},grid:{color:'#edf2f3'}}}}});
}
async function loadHistory(){const data=await api('historico?dias='+$('#days').value+'&destino='+encodeURIComponent($('#destination').value));history=data.items;$('#chart-note').textContent='Horários de Brasília. Clique na legenda para comparar origens.'+(history.length===data.limite?' Limite de 10.000 pontos atingido; reduza o período.':'');renderRoutes();renderChart();}
async function load(){
 $('#refresh').disabled=true;
 try{
  routes=await api('rotas');
  const selection=$('#destination').value;
  $('#destination').replaceChildren(new Option('Todos',''));
  [...new Set(routes.map(r=>r.destino))].sort().forEach(d=>$('#destination').add(new Option(d,d)));
  $('#destination').value=[...$('#destination').options].some(o=>o.value===selection)?selection:'';
  await loadHistory();$('#login').hidden=true;$('#dashboard').hidden=false;chart?.resize();
 }catch(error){notify(error.message);}finally{$('#refresh').disabled=false;}
}
function edit(route={}){
 form.reset();$('#form-error').textContent='';
 for(const field of ['id','apelido','origem','destino','max_preco_alerta','data_inicio','data_fim'])form.elements[field].value=route[field]??'';
 form.elements.ativo.checked=route.ativo??true;
 $('#editor-title').textContent=route.id?'Editar rota':'Nova rota';$('#editor').showModal();
}
async function toggle(route){try{await api('rotas',{method:'PUT',body:JSON.stringify({...route,ativo:!route.ativo})});await load();}catch(e){notify(e.message);}}
async function remove(route){if(!confirm(`Excluir “${route.apelido}” e todo o histórico desta rota?`))return;try{await api('rotas?id='+route.id,{method:'DELETE'});await load();}catch(e){notify(e.message);}}
form.onsubmit=async event=>{
 event.preventDefault();$('#save').disabled=true;$('#form-error').textContent='';
 const data=Object.fromEntries(new FormData(form));data.ativo=form.elements.ativo.checked;
 data.origem=data.origem.trim().toUpperCase();data.destino=data.destino.trim().toUpperCase();
 try{await api('rotas',{method:data.id?'PUT':'POST',body:JSON.stringify(data)});$('#editor').close();await load();notify('Rota salva. Ela será incluída na próxima execução do robô se estiver ativa.');}catch(e){$('#form-error').textContent=e.message;}finally{$('#save').disabled=false;}
};
for(const [field,list] of [['origem','origin-list'],['destino','destination-list']]){
 let debounce, sequence=0;
 form.elements[field].oninput=()=>{clearTimeout(debounce);const q=form.elements[field].value.trim();const current=++sequence;if(q.length<2)return;
  debounce=setTimeout(async()=>{try{const airports=await api('aeroportos?q='+encodeURIComponent(q));if(current!==sequence)return;$('#'+list).replaceChildren(...airports.map(a=>new Option(`${a.nome} · ${a.cidade}`,a.codigo)));}catch(e){notify(e.message+' Você também pode informar o código IATA diretamente.');}},500);
 };
}
$('#new-route').onclick=()=>edit();$('#close').onclick=()=>$('#editor').close();$('#refresh').onclick=load;
$('#destination').onchange=()=>loadHistory().catch(e=>notify(e.message));$('#days').onchange=$('#destination').onchange;
$('#login-form').onsubmit=e=>{e.preventDefault();token=$('#token').value.trim();sessionStorage.setItem('flex-token',token);$('#token').value='';load();};
$('#logout').onclick=()=>{token='';sessionStorage.removeItem('flex-token');$('#dashboard').hidden=true;$('#login').hidden=false;chart?.destroy();chart=null;routes=[];history=[];$('#routes').replaceChildren();};
if(token)load();
