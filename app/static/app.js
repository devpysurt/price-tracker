"use strict";
const $ = (selector) => document.querySelector(selector);
const money = (value) => new Intl.NumberFormat("en-US", {style:"currency", currency:"USD"}).format(Number(value));
const date = (value) => new Date(value).toLocaleString();
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let toastTimer;
function message(text, error=false) {
  const box = $("#message"); box.textContent=text; box.hidden=false; box.className=error ? "error" : "";
  clearTimeout(toastTimer); toastTimer=setTimeout(() => {box.hidden=true;}, 7000);
}
async function api(path, options={}) {
  const response=await fetch("/api"+path, {...options, headers:{"Content-Type":"application/json"}});
  if (!response.ok) {
    const data=await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : "Please check your input and try again.");
  }
  return response.status===204 ? null : response.json();
}
async function action(button, task) {
  button.disabled=true;
  try {await task();} catch(error) {message(error.message, true);} finally {button.disabled=false;}
}
function stat(label, value, cls="") {return `<div class="stat"><small>${label}</small><strong class="${cls}">${escapeHTML(value)}</strong></div>`;}
function change(product) {
  const value=product.percentage_change;
  return value===null ? "—" : `${Number(value)>0?"+":""}${Number(value).toFixed(2)}%`;
}
function image(product) {return `<div class="card-image"><img loading="lazy" src="${escapeHTML(product.thumbnail)}" alt="${escapeHTML(product.title)}"></div>`;}
async function loadTracked() {
  const products=await api("/tracked"); $("#count").textContent=products.length;
  $("#tracked").innerHTML=products.length ? products.map(p => `<article class="card">${image(p)}<div class="card-body"><div class="source">${escapeHTML(p.source)}</div><h3>${escapeHTML(p.title)}</h3>${Number(p.current_price)<=Number(p.target_price)?'<span class="badge">Target reached</span>':""}<div class="stats">${stat("Current",money(p.current_price))}${stat("Target",money(p.target_price))}${stat("Change since first check",change(p),Number(p.percentage_change)<0?"down":"")}${stat("Recorded range",`${money(p.minimum_price)} – ${money(p.maximum_price)}`)}</div><div class="muted">Last checked ${date(p.last_checked_at)}</div><div class="card-actions"><a href="/products/${p.id}">View history ↗</a><button class="secondary" data-refresh="${p.id}">Refresh</button><button class="secondary danger" data-delete="${p.id}">Delete</button></div></div></article>`).join("") : '<div class="empty">Your watchlist starts here.<br>Find a product below and set a target price.</div>';
}
let searchSkip=0, searchQuery="", searchVersion=0;
async function loadCatalog() {
  const version=++searchVersion;
  $("#results-label").textContent="Searching the catalog…";
  try {
    const result=await api(`/products/search?q=${encodeURIComponent(searchQuery)}&skip=${searchSkip}&limit=12`);
    if(version!==searchVersion) return;
    $("#results-label").textContent=result.total ? `${result.total} products · showing ${result.skip+1}–${result.skip+result.products.length}` : "No products found. Try another search.";
    $("#results").innerHTML=result.products.map(p => `<article class="card">${image(p)}<div class="card-body"><h3>${escapeHTML(p.title)}</h3><p>${money(p.price)}</p><form class="track-form" data-external="${p.id}"><label for="target-${p.id}">Your target (USD)</label><div class="inline"><input id="target-${p.id}" name="target" aria-label="Target price for ${escapeHTML(p.title)}" type="number" min="0" max="999999999" step="0.01" required value="${(Number(p.price)*.95).toFixed(2)}"><button>+ Track</button></div></form></div></article>`).join("");
    $("#previous").hidden=result.skip===0; $("#next").hidden=result.skip+result.products.length>=result.total;
  } catch(error) {
    if(version!==searchVersion) return;
    $("#results-label").textContent="Catalog unavailable. Use Search to retry.";
    $("#results").replaceChildren(); $("#previous").hidden=true; $("#next").hidden=true; throw error;
  }
}
let chart;
async function loadDetail() {
  const id=$("#product-detail").dataset.id;
  const [p,history]=await Promise.all([api(`/tracked/${id}`),api(`/tracked/${id}/history`)]);
  $("#detail-stats").innerHTML=stat("Current",money(p.current_price))+stat("Target",money(p.target_price))+stat("Lowest recorded",money(p.minimum_price))+stat("Highest recorded",money(p.maximum_price))+stat("First recorded",money(p.first_price))+stat("Change",`${money(p.absolute_change)} (${change(p)})`,Number(p.absolute_change)<0?"down":"");
  $("#last-check").textContent=`Last checked ${date(p.last_checked_at)}`;
  $("#alert-state").textContent=Number(p.current_price)<=Number(p.target_price)?"Target reached":"Watching for a price drop";
  if(document.activeElement!==$("#target")) $("#target").value=p.target_price;
  $("#history-table").innerHTML=[...history].reverse().map(h => `<tr><td>${date(h.checked_at)}</td><td>${money(h.price)}</td></tr>`).join("");
  if(typeof Chart === "undefined") {$("#chart-status").textContent="Chart library could not load. Price history is available in the table below."; return;}
  const data={labels:history.map(h => date(h.checked_at)),datasets:[{label:"Price",data:history.map(h=>Number(h.price)),borderColor:"#087f68",backgroundColor:"#087f6815",fill:true,tension:.15,pointRadius:3},{label:"Target",data:history.map(()=>Number(p.target_price)),borderColor:"#b28548",borderDash:[6,6],pointRadius:0,fill:false}]};
  if(chart) {chart.data=data; chart.update();} else {chart=new Chart($("#history-chart"),{type:"line",data,options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom"}},scales:{y:{ticks:{callback:value=>money(value)}},x:{ticks:{maxTicksLimit:6,maxRotation:0}}}}});}
  $("#chart-status").textContent=`${history.length} checks recorded${history.length===1?" · Refresh to add another point":""}.`;
}
async function init() {
  if($("#tracked")) {
    $("#search-form").addEventListener("submit", e => {e.preventDefault(); searchQuery=$("#query").value.trim(); searchSkip=0; action(e.submitter,loadCatalog);});
    $("#previous").onclick=e=>action(e.currentTarget,async()=>{searchSkip=Math.max(0,searchSkip-12); await loadCatalog();});
    $("#next").onclick=e=>action(e.currentTarget,async()=>{searchSkip+=12; await loadCatalog();});
    $("#results").addEventListener("submit",e=>{e.preventDefault(); const form=e.target; action(e.submitter,async()=>{await api("/tracked",{method:"POST",body:JSON.stringify({external_id:Number(form.dataset.external),target_price:form.elements.target.value})}); await loadTracked(); message("Product added to your watchlist.");});});
    $("#tracked").addEventListener("click",e=>{const b=e.target.closest("button"); if(!b) return;
      if(b.dataset.refresh) action(b,async()=>{await api(`/tracked/${b.dataset.refresh}/refresh`,{method:"POST"});await loadTracked();message("Price updated.");});
      if(b.dataset.delete && confirm("Delete this product and its price history?")) action(b,async()=>{await api(`/tracked/${b.dataset.delete}`,{method:"DELETE"});await loadTracked();message("Product deleted.");});
    });
    const results=await Promise.allSettled([loadTracked(),loadCatalog()]); results.forEach(r=>{if(r.status==="rejected") message(r.reason.message,true);});
  } else if($("#product-detail")) {
    const id=$("#product-detail").dataset.id;
    $("#refresh-product").onclick=e=>action(e.currentTarget,async()=>{await api(`/tracked/${id}/refresh`,{method:"POST"});await loadDetail();message("Price updated.");});
    $("#target-form").onsubmit=e=>{e.preventDefault(); action(e.submitter,async()=>{await api(`/tracked/${id}`,{method:"PATCH",body:JSON.stringify({target_price:$("#target").value})});await loadDetail();message("Target saved.");});};
    $("#delete-product").onclick=e=>{if(confirm("Delete this product and its price history?")) action(e.currentTarget,async()=>{await api(`/tracked/${id}`,{method:"DELETE"});window.location.href="/";});};
    await loadDetail();
  }
  setInterval(()=>{if(document.hidden) return; const task=$("#tracked")?loadTracked:loadDetail; task().catch(error=>message(error.message,true));},30000);
}
init().catch(error=>message(error.message,true));
