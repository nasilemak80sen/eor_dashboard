export type Formation = "Sandstone" | "Carbonate" | "Carbonates" | "Unconsolidated sands";
export type EvaluationMode = "engineering" | "hybrid";
export interface ReservoirInputs { depth_ft:number; reservoir_pressure:number; temperature_c:number; visc_cp:number; api:number; perm_md:number; porosity_frac:number; porosity_pct:number; so_pct:number }
export interface EvaluationRequest { field_id?:string; formation:Formation; inputs:ReservoirInputs; include_probabilities:boolean }
export interface EvaluationResponse { run_id:string; mode:EvaluationMode; field_id?:string|null; formation:string; screening:Record<string,unknown>; hybrid?:Record<string,unknown>|null; model?:Record<string,unknown>|null; history?:Record<string,unknown>|null }
export interface HistoryRecord { id:number; timestamp?:string|null; formation?:string|null; status?:string|null; recommended_technique?:string|null; recommendation_status?:string|null; recommendation_score?:number|null; recommendation_mode?:string|null; user?:string|null }
export interface ApiHealth { status?:string; ready?:boolean; workbook_ready?:boolean; model_ready?:boolean; history?:{configured?:boolean;readable?:boolean;schema_valid?:boolean;record_count?:number|null} }
const rawBase = import.meta.env.VITE_EOR_API_BASE_URL?.trim() || "http://127.0.0.1:8000";
export const defaultApiBase = rawBase.replace(/\/+$/, "");
export class ApiError extends Error { constructor(message:string, public status:number, public code:string, public correlationId:string|null) { super(message); this.name="ApiError"; } }
async function request<T>(path:string, token:string, init:RequestInit={}):Promise<T> {
 const headers=new Headers(init.headers); headers.set("Accept","application/json");
 if(init.body) headers.set("Content-Type","application/json");
 if(token.trim()) headers.set("Authorization","Bearer "+token.trim());
 let response:Response;
 try { response=await fetch(defaultApiBase+path,{...init,headers,cache:"no-store"}); }
 catch { throw new ApiError("Could not reach the EOR Atlas API. Check the backend URL, server and CORS configuration.",0,"network_error",null); }
 const correlationId=response.headers.get("X-Correlation-ID");
 const payload:unknown=await response.json().catch(()=>null);
 if(!response.ok) {
  const root=payload&&typeof payload==="object"?payload as Record<string,unknown>:{};
  const err=root.error&&typeof root.error==="object"?root.error as Record<string,unknown>:{};
  throw new ApiError(typeof err.message==="string"?err.message:"Request failed with HTTP "+response.status+".",response.status,typeof err.code==="string"?err.code:"request_failed",correlationId);
 }
 return payload as T;
}
export const api={
 live:()=>request<{status:string}>("/api/v1/health/live",""),
 ready:(token:string)=>request<ApiHealth>("/api/v1/health/ready",token),
 evaluate:(mode:EvaluationMode,body:EvaluationRequest,token:string)=>request<EvaluationResponse>(mode==="engineering"?"/api/v1/screening/evaluate":"/api/v1/intelligence/evaluate",token,{method:"POST",body:JSON.stringify(body)}),
 history:(token:string,limit=20,offset=0)=>request<HistoryRecord[]>("/api/v1/history?limit="+limit+"&offset="+offset,token)
};