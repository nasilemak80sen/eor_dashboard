"""Decision-centric UI primitives for EOR Atlas."""
from __future__ import annotations
from html import escape
from typing import Any, Iterable
import pandas as pd
import streamlit as st

_STYLE = """
<style>
.atlas-decision-hero{background:linear-gradient(135deg,#0E3038,#123F48);border-radius:20px;padding:1.35rem 1.4rem;color:#fff;box-shadow:0 16px 34px rgba(15,57,65,.14);margin:.35rem 0 1rem}.atlas-decision-kicker{font-size:.66rem;font-weight:700;letter-spacing:.12em;color:#A7F3D0;text-transform:uppercase}.atlas-decision-title{font-size:.74rem;font-weight:600;color:rgba(255,255,255,.72);margin-top:.35rem}.atlas-decision-technique{font-size:2rem;font-weight:700;line-height:1.1;margin-top:.2rem}.atlas-decision-subtitle{color:rgba(255,255,255,.72);font-size:.78rem;margin-top:.4rem}.atlas-decision-score-row{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.6rem;margin-top:1rem}.atlas-decision-score-row>div{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.09);border-radius:12px;padding:.65rem .7rem}.atlas-decision-score-row span{display:block;font-size:.57rem;letter-spacing:.08em;color:rgba(255,255,255,.55);font-weight:700}.atlas-decision-score-row strong{display:block;font-size:.94rem;margin-top:.2rem;color:#fff}.atlas-inline-status.pass{color:#A7F3D0}.atlas-inline-status.conditional{color:#FDE68A}.atlas-inline-status.fail{color:#FECACA}.atlas-trace-step{display:flex;gap:.85rem;align-items:flex-start;padding:.75rem .85rem;background:#fff;border:1px solid #E4E7EC;border-radius:14px;margin:.35rem 0}.atlas-trace-number{width:30px;height:30px;border-radius:50%;background:#EAF7F6;color:#0F4B4A;display:flex;align-items:center;justify-content:center;font-size:.68rem;font-weight:700;flex:0 0 30px}.atlas-trace-label{font-size:.6rem;letter-spacing:.1em;color:#667085;font-weight:700}.atlas-trace-title{font-size:.9rem;font-weight:700;color:#182230;margin-top:.08rem}.atlas-trace-meta{font-size:.75rem;color:#667085;margin-top:.12rem}.atlas-next-step{display:flex;gap:.7rem;align-items:flex-start;background:#fff;border:1px solid #E4E7EC;border-radius:12px;padding:.72rem .8rem;margin:.45rem 0}.atlas-next-step>span{width:24px;height:24px;border-radius:50%;background:#EAF7F6;color:#0F4B4A;font-size:.68rem;font-weight:700;display:flex;align-items:center;justify-content:center;flex:0 0 24px}@media(max-width:900px){.atlas-decision-score-row{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _style() -> None:
    st.markdown(_STYLE, unsafe_allow_html=True)


def fmt_score(value: Any) -> str:
    try:return f"{float(value):.1%}"
    except (TypeError,ValueError):return "—"


def status_class(status: Any) -> str:
    return {"PASS":"pass","CONDITIONAL":"conditional","FAIL":"fail"}.get(str(status or "").upper(),"neutral")


def decision_hero(recommendation: dict[str,Any] | None, quality: str = "Decision available") -> None:
    _style()
    if not recommendation:
        st.warning("No eligible technique was produced by the current decision path."); return
    technique=recommendation.get("EOR Technique","N/A"); status=recommendation.get("Engineering Status","—")
    st.markdown(f'''<div class="atlas-decision-hero"><div class="atlas-decision-kicker">FINAL DECISION</div><div class="atlas-decision-title">Recommended EOR Technique</div><div class="atlas-decision-technique">{escape(str(technique))}</div><div class="atlas-decision-subtitle">Engineering Gate → CatBoost → Decision Fusion</div><div class="atlas-decision-score-row"><div><span>HYBRID</span><strong>{fmt_score(recommendation.get("Hybrid Score"))}</strong></div><div><span>CATBOOST</span><strong>{fmt_score(recommendation.get("CatBoost Probability"))}</strong></div><div><span>ENGINEERING</span><strong>{fmt_score(recommendation.get("Engineering Score"))}</strong></div><div><span>GATE</span><strong class="atlas-inline-status {status_class(status)}">{escape(str(status))}</strong></div><div><span>QUALITY</span><strong>{escape(quality)}</strong></div></div></div>''',unsafe_allow_html=True)


def decision_trace(screening:dict[str,Any]|None, ml_top3:Iterable[Any]|None, ranking:Iterable[dict[str,Any]]|None)->None:
    _style(); ranking=list(ranking or []); ml_top3=list(ml_top3 or []); st.markdown("### Decision Trace"); st.caption("Production decision chain shown as an auditable sequence.")
    stages=[("01","INPUT","Reservoir context","Submitted reservoir properties"),("02","ENGINEERING GATE","Excel screening","Deterministic feasibility"),("03","MODEL","CatBoost",f"{len(ml_top3)} top model signals" if ml_top3 else "Model signal evaluated during fusion"),("04","FUSION","Decision Fusion",f"{len(ranking)} ranked techniques" if ranking else "Engineering + model reconciliation"),("05","FINAL","Hybrid ranking",str(ranking[0].get("EOR Technique")) if ranking else "Awaiting recommendation")]
    for number,label,title,meta in stages: st.markdown(f'''<div class="atlas-trace-step"><div class="atlas-trace-number">{number}</div><div><div class="atlas-trace-label">{escape(label)}</div><div class="atlas-trace-title">{escape(title)}</div><div class="atlas-trace-meta">{escape(meta)}</div></div></div>''',unsafe_allow_html=True)


def why_why_not(ranking:Iterable[dict[str,Any]],max_items:int=3)->None:
    rows=list(ranking or [])[:max_items]
    if not rows:return
    st.markdown("### Why / Why Not"); tabs=st.tabs([f"#{i+1} {row.get('EOR Technique','Technique')}" for i,row in enumerate(rows)])
    for i,(tab,row) in enumerate(zip(tabs,rows)):
        with tab:
            cols=st.columns(4); cols[0].metric("Engineering",fmt_score(row.get("Engineering Score"))); cols[1].metric("CatBoost",fmt_score(row.get("CatBoost Probability"))); cols[2].metric("Hybrid",fmt_score(row.get("Hybrid Score"))); cols[3].metric("Gate",row.get("Engineering Status","—"))
            status=str(row.get("Engineering Status","")).upper()
            if status=="PASS":st.success("Engineering gate is satisfied under the current criteria.")
            elif status=="CONDITIONAL":st.warning("Technically plausible, but a conditional engineering penalty applies.")
            else:st.error("Engineering gate is not satisfied under the current criteria.")
            st.info("Selected because it has the strongest combined hybrid position." if i==0 else "Lower than the leading recommendation in the current hybrid ranking.")


def data_quality(values:dict[str,Any]|None)->str:
    values=values or {}; core=("depth_ft","reservoir_pressure","temperature_c","visc_cp","api","perm_md","porosity_pct","so_pct"); count=sum(values.get(k) is not None for k in core); quality="HIGH" if count==len(core) else ("MEDIUM" if count>=6 else "LIMITED")
    st.markdown("### Data & Assumption Quality"); st.caption("Known inputs are explicit; unavailable optional inputs are not fabricated.")
    rows=[{"Parameter":label,"State":"Provided" if values.get(key) is not None else "Unavailable"} for label,key in [("Depth","depth_ft"),("Pressure","reservoir_pressure"),("Temperature","temperature_c"),("Viscosity","visc_cp"),("API","api"),("Permeability","perm_md"),("Porosity","porosity_pct"),("Current So","so_pct")]]
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True); return quality


def next_steps(recommendation:dict[str,Any]|None)->None:
    technique=str((recommendation or {}).get("EOR Technique","the selected technique")); status=str((recommendation or {}).get("Engineering Status","")).upper(); actions=["Validate the highest-impact engineering assumptions before concept selection.",f"Review technical evidence and constraints specific to {technique}."]
    if status=="CONDITIONAL":actions.insert(1,"Resolve the conditional engineering criteria before advancing the technique.")
    elif status=="FAIL":actions.insert(1,"Do not advance the technique without addressing the failed engineering gate.")
    else:actions.insert(1,"Progress to laboratory, subsurface and facility feasibility validation as appropriate.")
    st.markdown("### Recommended Next Steps")
    for i,action in enumerate(actions,1):st.markdown(f'<div class="atlas-next-step"><span>{i}</span><div>{escape(action)}</div></div>',unsafe_allow_html=True)


def view_mode(key:str)->str:
    return st.radio("View",["Engineering","Leadership"],horizontal=True,key=key)
