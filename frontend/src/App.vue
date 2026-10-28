<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api, ApiError, defaultApiBase, type ApiHealth, type EvaluationMode, type EvaluationResponse, type Formation, type HistoryRecord, type ReservoirInputs } from "./api";
type View = "screening" | "hybrid" | "history";
const view=ref<View>("screening"), token=ref(""), apiLive=ref("checking"), health=ref<ApiHealth|null>(null), busy=ref(false), errorMessage=ref(""), correlationId=ref("");
const result=ref<EvaluationResponse|null>(null), historyRows=ref<HistoryRecord[]>([]), historyBusy=ref(false), historyError=ref("");
const fieldId=ref(""), formation=ref<Formation>("Sandstone"), includeProbabilities=ref(true);
const inputs=reactive<ReservoirInputs>({depth_ft:5000,reservoir_pressure:2500,temperature_c:95,visc_cp:2,api:35,perm_md:100,porosity_frac:0.2,porosity_pct:20,so_pct:55});
const fields:{key:keyof ReservoirInputs;label:string;unit:string;min:number;max:number;step:number}[]=[
 {key:"depth_ft",label:"Mid-depth",unit:"ft",min:1,max:100000,step:1},{key:"reservoir_pressure",label:"Reservoir pressure",unit:"psi",min:0,max:100000,step:1},
 {key:"temperature_c",label:"Temperature",unit:"°C",min:-100,max:500,step:0.1},{key:"visc_cp",label:"Oil viscosity",unit:"cP",min:0.0001,max:1000000,step:0.1},
 {key:"api",label:"Oil gravity",unit:"°API",min:0,max:100,step:0.1},{key:"perm_md",label:"Permeability",unit:"mD",min:0.0001,max:1000000000,step:0.1},
 {key:"porosity_pct",label:"Porosity",unit:"%",min:0,max:100,step:0.1},{key:"so_pct",label:"Oil saturation",unit:"%",min:0,max:100,step:0.1}
];
const title=computed(()=>view.value==="screening"?"Engineering screening":view.value==="hybrid"?"Hybrid intelligence":"Run history");
const subtitle=computed(()=>view.value==="screening"?"Evaluate candidate EOR techniques against the existing engineering rules.":view.value==="hybrid"?"Compare engineering screening with the existing ML-assisted hybrid evaluation.":"Browse existing records in read-only mode. This interface does not save new evaluations.");
const gateRows=computed(()=>Array.isArray(result.value?.screening?.results)?result.value.screening.results as Record<string,unknown>[]:[]);
const topRecommendation=computed(()=>{const r=result.value?.hybrid?.recommendation;return r&&typeof r==="object"?r as Record<string,unknown>:null;});
function display(v:unknown):string{return v===null||v===undefined||v===""?"Not provided":typeof v==="object"?JSON.stringify(v,null,2):String(v);}
function technique(r:Record<string,unknown>):string{return String(r["EOR Technique"]??r.technique??r.Technique??"Unnamed technique");}
function status(r:Record<string,unknown>):string{return String(r.Status??r.status??"Not reported");}
function score(r:Record<string,unknown>):string{const s=r["Score (%)"]??r.score;return typeof s==="number"?s.toFixed(1)+"%":display(s);}
function validate():string|null {
 if(Math.abs(inputs.porosity_frac*100-inputs.porosity_pct)>0.11)return "Porosity fraction and percentage do not match.";
 for(const f of fields){const v=inputs[f.key];if(!Number.isFinite(v)||v<f.min||v>f.max)return f.label+" must be between "+f.min+" and "+f.max+" "+f.unit+".";}
 if(inputs.visc_cp<=0||inputs.perm_md<=0||inputs.depth_ft<=0)return "Depth, viscosity and permeability must be greater than zero.";
 return null;
}
async function checkApi(){try{await api.live();apiLive.value="online";}catch{apiLive.value="offline";}try{health.value=await api.ready(token.value);}catch{health.value=null;}}
async function evaluate(mode:EvaluationMode){
 errorMessage.value="";correlationId.value="";result.value=null;const invalid=validate();if(invalid){errorMessage.value=invalid;return;}busy.value=true;
 try{const body={field_id:fieldId.value.trim()||undefined,formation:formation.value,inputs:{...inputs,porosity_frac:Number((inputs.porosity_pct/100).toFixed(6))},include_probabilities:includeProbabilities.value};result.value=await api.evaluate(mode,body,token.value);await checkApi();}
 catch(e){if(e instanceof ApiError){errorMessage.value=e.message+" ("+e.code+", HTTP "+e.status+")";correlationId.value=e.correlationId||"";}else errorMessage.value="The evaluation could not be completed.";}
 finally{busy.value=false;}
}
async function loadHistory(){historyBusy.value=true;historyError.value="";try{historyRows.value=await api.history(token.value);}catch(e){historyRows.value=[];historyError.value=e instanceof Error?e.message:"History could not be loaded.";}finally{historyBusy.value=false;}}
function choose(next:View){view.value=next;errorMessage.value="";if(next==="history")void loadHistory();}
function syncPorosity(){inputs.porosity_frac=Number((inputs.porosity_pct/100).toFixed(6));}
onMounted(()=>{void checkApi();});
</script>
<template>
<div class="shell">
 <header class="topbar"><a class="brand" href="#" @click.prevent="choose('screening')"><span class="mark">EA</span><span><b>EOR Atlas</b><small>ENGINEERING DECISION SUPPORT</small></span></a><div class="topright"><span class="pill" :class="apiLive"><i></i>API {{apiLive}}</span><span class="environment">VUE PREVIEW</span></div></header>
 <div class="layout">
  <aside class="sidebar"><p class="eyebrow">WORKSPACE</p>
   <button class="nav" :class="{active:view==='screening'}" @click="choose('screening')">01&nbsp; Engineering screening</button>
   <button class="nav" :class="{active:view==='hybrid'}" @click="choose('hybrid')">02&nbsp; Hybrid intelligence</button>
   <button class="nav" :class="{active:view==='history'}" @click="choose('history')">03&nbsp; Run history</button>
   <div class="guardrail"><b>Engineering-first</b><p>Hard engineering exclusions remain authoritative. ML confidence cannot reverse a failed engineering gate.</p></div>
   <div class="connection"><label for="apiurl">API base URL</label><input id="apiurl" :value="defaultApiBase" readonly/><label for="token">Bearer token <small>optional in development</small></label><textarea id="token" v-model="token" rows="3" autocomplete="off" spellcheck="false" placeholder="Paste a development token if required"></textarea><p>Token remains in page memory only and is not saved to browser storage.</p><button class="button quiet full" @click="checkApi">Check connection</button></div>
  </aside>
  <main class="content">
   <div class="heading"><div><p class="eyebrow">EOR ATLAS / {{view.toUpperCase()}}</p><h1>{{title}}</h1><p class="subtitle">{{subtitle}}</p></div><span class="phase">PHASES 5–6</span></div>
   <div v-if="apiLive==='offline'" class="notice warning"><b>API unreachable</b><p>Start FastAPI and confirm the backend URL and CORS allow-list.</p></div>
   <div v-if="apiLive==='online'&&!health" class="notice info">The API responds, but readiness could not be confirmed. Protected endpoints may require a valid bearer token.</div>
   <div v-if="health?.ready" class="readiness">● Engine ready <span>Workbook {{health.workbook_ready?'ready':'not confirmed'}}</span><span>Model {{health.model_ready?'ready':'not confirmed'}}</span></div>
   <template v-if="view!=='history'">
    <section class="panel"><div class="panelhead"><div><h2>Reservoir profile</h2><p>Evaluate a profile through the existing Python API.</p></div><small>INPUTS / 01</small></div>
     <form @submit.prevent="evaluate(view==='hybrid'?'hybrid':'engineering')">
      <div class="field wide"><label for="fieldid">Field / asset identifier <small>optional</small></label><input id="fieldid" v-model="fieldId" maxlength="200" placeholder="Internal asset reference"/></div>
      <div class="field formation"><label for="formation">Formation</label><select id="formation" v-model="formation"><option>Sandstone</option><option>Carbonate</option><option>Carbonates</option><option>Unconsolidated sands</option></select></div>
      <div class="fields"><div v-for="f in fields" :key="f.key" class="field"><label :for="f.key">{{f.label}} <small>{{f.unit}}</small></label><input :id="f.key" v-model.number="inputs[f.key]" type="number" :min="f.min" :max="f.max" :step="f.step" required @input="f.key==='porosity_pct'&&syncPorosity()"/></div></div>
      <div class="formfoot"><label class="check"><input v-model="includeProbabilities" type="checkbox"/> Include model probabilities where supported</label><button class="button primary" type="submit" :disabled="busy">{{busy?'Evaluating…':view==='hybrid'?'Run hybrid evaluation':'Run engineering screening'}} ↗</button></div>
     </form><p class="disclaimer">Prefilled values are illustrative test inputs, not approved reservoir data or validated golden cases.</p>
    </section>
    <div v-if="errorMessage" class="notice error" role="alert"><b>Evaluation could not be completed</b><p>{{errorMessage}}</p><small v-if="correlationId">Correlation ID: {{correlationId}}</small></div>
    <template v-if="result">
     <div class="summary"><div><small>RUN ID</small><b class="mono">{{result.run_id}}</b></div><div><small>MODE</small><b>{{result.mode}}</b></div><div><small>FORMATION</small><b>{{result.formation}}</b></div><div><small>PERSISTENCE</small><b>Not saved</b></div></div>
     <section v-if="view==='hybrid'&&topRecommendation" class="recommendation"><div><small>HYBRID RECOMMENDATION</small><h2>{{display(topRecommendation['EOR Technique']??topRecommendation.technique??topRecommendation.name)}}</h2></div><p>Review the engineering gate and supporting evidence before acting on this recommendation.</p></section>
     <section class="panel"><div class="panelhead"><div><h2>Engineering gate results</h2><p>Returned by the existing Python screening service.</p></div><small>{{gateRows.length}} ROWS</small></div>
      <div v-if="gateRows.length" class="tablewrap"><table><thead><tr><th>Technique</th><th>Status</th><th>Score</th></tr></thead><tbody><tr v-for="(row,i) in gateRows" :key="technique(row)+'-'+i"><td><b>{{technique(row)}}</b></td><td><span class="resultstatus" :class="{fail:status(row).toLowerCase().includes('fail'),pass:status(row).toLowerCase().includes('pass')}">{{status(row)}}</span></td><td>{{score(row)}}</td></tr></tbody></table></div><p v-else class="empty">No tabular technique rows found. Inspect the complete payload below.</p>
     </section>
     <section v-if="view==='hybrid'&&result.model" class="panel"><div class="panelhead"><div><h2>Model metadata</h2><p>Supplied by the existing inference service.</p></div></div><pre>{{JSON.stringify(result.model,null,2)}}</pre></section>
     <details class="panel"><summary>Inspect complete API response</summary><pre>{{JSON.stringify(result,null,2)}}</pre></details>
    </template>
   </template>
   <section v-else class="panel"><div class="panelhead"><div><h2>Existing records</h2><p>Read-only access. New evaluations are not persisted by this migration.</p></div><button class="button quiet" :disabled="historyBusy" @click="loadHistory">{{historyBusy?'Loading…':'Refresh'}}</button></div>
    <div v-if="historyError" class="notice warning">{{historyError}}</div><p v-else-if="historyBusy" class="empty">Loading history…</p><p v-else-if="!historyRows.length" class="empty">No history records returned, or history is not configured for this environment.</p>
    <div v-else class="tablewrap"><table><thead><tr><th>Run</th><th>Timestamp</th><th>Formation</th><th>Technique</th><th>Status</th><th>Score</th><th>Mode</th></tr></thead><tbody><tr v-for="r in historyRows" :key="r.id"><td class="mono">#{{r.id}}</td><td>{{r.timestamp||'Not recorded'}}</td><td>{{r.formation||'—'}}</td><td>{{r.recommended_technique||'—'}}</td><td>{{r.recommendation_status||r.status||'—'}}</td><td>{{typeof r.recommendation_score==='number'?r.recommendation_score.toFixed(1)+'%':'—'}}</td><td>{{r.recommendation_mode||'—'}}</td></tr></tbody></table></div>
   </section>
   <footer><span>ENGINEERING-FIRST DECISION SUPPORT</span><span>Vue 3 · TypeScript · FastAPI</span></footer>
  </main>
 </div>
</div>
</template>