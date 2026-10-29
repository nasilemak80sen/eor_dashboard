export type Formation = "Sandstone" | "Carbonate" | "Carbonates" | "Unconsolidated sands";
export type EvaluationMode = "engineering" | "hybrid";

export interface ReservoirInputs {
  depth_ft:number; reservoir_pressure:number; temperature_c:number; visc_cp:number; api:number; perm_md:number; porosity_frac:number; porosity_pct:number; so_pct:number;
  salinity_ppm:number; hardness_ppm:number; rock_type:string; net_pay_m:number; heterogeneity:string; gas_availability:string; oxygen_present:string;
  ooip_mmstb:number; base_rf_pct:number; drive_mechanism:string; drive_multiplier:number; co2_availability:string; mmp_satisfied:string; waterflood_history:string;
  water_cut_pct:number; field_maturity:string; maturity_factor:number; mobility_ratio:string; adsorption_risk:string; water_handling:string; offshore:string;
  water_injection_facilities:string; gas_injection_facilities:string; wag_ratio:string; gas_injectivity:string; water_injectivity:string; gravity_override_risk:string;
  hc_gas_availability:string; produced_gor_category:string; gas_reinjectable:string; produced_gor_scf_stb:number|null; sorw_pct:number|null;
}

export interface EvaluationRequest {
  field_id?:string;
  formation:Formation;
  inputs:ReservoirInputs;
  include_probabilities:boolean;
}
export interface EvaluationResponse {
  run_id:string;
  mode:EvaluationMode;
  field_id?:string|null;
  formation:string;
  screening:Record<string,unknown>;
  hybrid?:Record<string,unknown>|null;
  model?:Record<string,unknown>|null;
  history?:Record<string,unknown>|null;
}
export interface HistoryRecord {
  id:number;
  timestamp?:string|null;
  formation?:string|null;
  status?:string|null;
  recommended_technique?:string|null;
  recommendation_status?:string|null;
  recommendation_score?:number|null;
  recommendation_mode?:string|null;
  user?:string|null;
}

const sampleRows:Record<string,unknown>[] = [
  {"EOR Technique":"Miscible HC",Status:"MOCK PASS","Score (%)":82.0,Suitability:"Illustrative", "Cause of Fail/Pass":"Synthetic row for interface testing only."},
  {"EOR Technique":"Polymer",Status:"MOCK PASS","Score (%)":76.0,Suitability:"Illustrative", "Cause of Fail/Pass":"Synthetic row for interface testing only."},
  {"EOR Technique":"Miscible CO2",Status:"MOCK CONDITIONAL","Score (%)":64.0,Suitability:"Illustrative", "Cause of Fail/Pass":"Synthetic row for interface testing only."},
  {"EOR Technique":"Steam",Status:"MOCK CONDITIONAL","Score (%)":59.0,Suitability:"Illustrative", "Cause of Fail/Pass":"Synthetic row for interface testing only."},
  {"EOR Technique":"Combustion",Status:"MOCK FAIL","Score (%)":31.0,Suitability:"Illustrative", "Cause of Fail/Pass":"Synthetic row for interface testing only."},
  {"EOR Technique":"Hot water",Status:"MOCK CONDITIONAL","Score (%)":52.0,Suitability:"Illustrative", "Cause of Fail/Pass":"Synthetic row for interface testing only."},
  {"EOR Technique":"HC immiscible",Status:"MOCK PASS","Score (%)":70.0,Suitability:"Illustrative", "Cause of Fail/Pass":"Synthetic row for interface testing only."},
  {"EOR Technique":"Nitrogen immiscible",Status:"MOCK CONDITIONAL","Score (%)":46.0,Suitability:"Illustrative", "Cause of Fail/Pass":"Synthetic row for interface testing only."},
  {"EOR Technique":"Miscible acid gas",Status:"MOCK FAIL","Score (%)":27.0,Suitability:"Illustrative", "Cause of Fail/Pass":"Synthetic row for interface testing only."}
];

export const DEMO_HISTORY:HistoryRecord[] = [
  {id:1001,timestamp:"2026-10-20 09:15",formation:"Sandstone",recommended_technique:"Polymer",recommendation_status:"DEMO ONLY",recommendation_score:76,recommendation_mode:"ENGINEERING",status:"SYNTHETIC"},
  {id:1002,timestamp:"2026-10-18 14:40",formation:"Carbonate",recommended_technique:"Miscible CO2",recommendation_status:"DEMO ONLY",recommendation_score:64,recommendation_mode:"HYBRID",status:"SYNTHETIC"},
  {id:1003,timestamp:"2026-10-14 11:05",formation:"Unconsolidated sands",recommended_technique:"Steam",recommendation_status:"DEMO ONLY",recommendation_score:59,recommendation_mode:"ENGINEERING",status:"SYNTHETIC"}
];

/**
 * Returns synthetic presentation fixtures only.
 * This must never be described as the active engineering or ML calculation.
 */
export function runDemoEvaluation(mode:EvaluationMode, request:EvaluationRequest):EvaluationResponse {
  const results = sampleRows.map(row => ({...row}));
  const recommendation = {"EOR Technique":"Polymer","Hybrid Score":0.71,"Status":"SYNTHETIC DEMO"};
  const ranking = [
    {"Rank":1,"EOR Technique":"Polymer","Hybrid Score":0.71,"Engineering Status":"MOCK PASS"},
    {"Rank":2,"EOR Technique":"Miscible HC","Hybrid Score":0.68,"Engineering Status":"MOCK PASS"},
    {"Rank":3,"EOR Technique":"Miscible CO2","Hybrid Score":0.55,"Engineering Status":"MOCK CONDITIONAL"}
  ];
  return {
    run_id:"POC-"+Date.now().toString(36).toUpperCase(),
    mode,
    field_id:request.field_id || null,
    formation:request.formation,
    screening:{results,source:"synthetic-ui-fixture",read_only:true},
    hybrid:mode==="hybrid"?{recommendation,ranking,explanation:"Synthetic UI fixture. Not calculated by the EOR engine."}:null,
    model:request.include_probabilities?{name:"Illustrative model details",source:"synthetic-ui-fixture",active_model_used:false,probabilities:[{technique:"Polymer",value:0.38},{technique:"Miscible HC",value:0.31},{technique:"Miscible CO2",value:0.18}]}:null,
    history:{persisted:false,reason:"POC demo outputs are not persisted."}
  };
}
