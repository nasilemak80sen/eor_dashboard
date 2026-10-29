"""UI-independent deterministic engineering screening service."""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence
import numpy as np
SCREENING_TOOL_SHEET = "Screening"
def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None: return default
    try: result = float(value)
    except (TypeError, ValueError): return default
    return result if np.isfinite(result) else default
def _normalise_text(value: Any) -> str:
    if value is None: return ""
    text = str(value).strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(text.split())
class ExcelScreeningService:
    """Workbook-parity deterministic EOR screening."""

    @staticmethod
    def _yes(value: Any) -> bool:
        return _normalise_text(value) == "yes"

    @staticmethod
    def _no(value: Any) -> bool:
        return _normalise_text(value) == "no"

    @staticmethod
    def _eq(value: Any, target: str) -> bool:
        return _normalise_text(value) == _normalise_text(target)

    @staticmethod
    def _in(value: Any, options: Sequence[str]) -> bool:
        return _normalise_text(value) in {
            _normalise_text(x) for x in options
        }

    @staticmethod
    def _gor_category(gor: Optional[float]) -> str:
        if gor is None:
            return ""
        if gor >= 1000:
            return "High"
        if gor >= 300:
            return "Moderate"
        return "Low"

    def prepare_inputs(
        self,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        values = dict(inputs)
        gor = _safe_float(
            values.get("produced_gor_scf_stb")
        )
        numeric_cat = self._gor_category(gor)

        if numeric_cat:
            values["gor_category_numeric"] = numeric_cat
            values["produced_gor_category"] = numeric_cat

        external_hc = self._yes(
            values.get("hc_gas_availability")
        )
        direct_gas = self._yes(
            values.get("gas_availability")
        )
        reinjectable = self._yes(
            values.get("gas_reinjectable")
        )

        cat = values.get(
            "produced_gor_category"
        ) or numeric_cat

        if external_hc:
            values["hc_source_status"] = "Available"
        elif (
            not direct_gas
            and self._in(cat, ["High", "Moderate"])
            and reinjectable
        ):
            values["hc_source_status"] = "Conditional"
        else:
            values["hc_source_status"] = "Unavailable"

        return values

    @staticmethod
    def _result(
        technique: str,
        critical_fail: bool,
        causes: List[str],
        score: float,
        max_delta_rf: float,
        values: Dict[str, Any],
        conditional: Optional[List[str]] = None,
    ) -> Dict[str, Any]:

        conditional = conditional or []

        if critical_fail:
            status = "FAIL (critical)"
            suitability = "Not suitable"
            score = 0.0
            delta_rf = 0.0
        else:
            status = "CONDITIONAL" if conditional else "PASS"
            if score >= 80:
                suitability = "Highly suitable"
            elif score >= 50:
                suitability = "Potentially suitable"
            else:
                suitability = "Marginal"
            delta_rf = (
                score / 100.0
            ) * max_delta_rf

        drive = (
            _safe_float(
                values.get("drive_multiplier"),
                1.0,
            )
            or 1.0
        )
        maturity = (
            _safe_float(
                values.get("maturity_factor"),
                1.0,
            )
            or 1.0
        )

        delta_rf *= drive * maturity

        base_rf = (
            _safe_float(
                values.get("base_rf_pct"),
                0.0,
            )
            or 0.0
        )

        final_rf = base_rf + delta_rf

        ooip = (
            _safe_float(
                values.get("ooip_mmstb"),
                0.0,
            )
            or 0.0
        )

        eur = ooip * final_rf / 100.0

        reasons = list(causes) + list(conditional)

        return {
            "EOR Technique": technique,
            "Critical Fail": bool(critical_fail),
            "Cause of Fail/Pass": (
                "; ".join(reasons)
                if reasons
                else "All critical criteria passed"
            ),
            "Score (%)": float(score),
            "Status": status,
            "Suitability": suitability,
            "ΔRF_EOR (%)": float(delta_rf),
            "Final RF (%)": float(final_rf),
            "EUR (MMstb)": float(eur),
        }

    def screen(
        self,
        raw_inputs: Dict[str, Any],
        formation: str,
    ) -> Dict[str, Any]:

        v = self.prepare_inputs(raw_inputs)

        api = _safe_float(v.get("api"), 0) or 0
        visc = _safe_float(v.get("visc_cp"), 0) or 0
        depth = _safe_float(v.get("depth_ft"), 0) or 0
        temp = _safe_float(v.get("temperature_c"), 0) or 0
        perm = _safe_float(v.get("perm_md"), 0) or 0
        tds = _safe_float(v.get("salinity_ppm"), 0) or 0
        hardness = _safe_float(v.get("hardness_ppm"), 0) or 0
        water_cut = _safe_float(v.get("water_cut_pct"), 0) or 0

        waterflood = self._yes(v.get("waterflood_history"))
        mobility_ok = self._in(v.get("mobility_ratio"), ["Favorable", "Neutral"])
        water_fac = self._yes(v.get("water_injection_facilities"))
        gas_fac = self._yes(v.get("gas_injection_facilities"))
        gas_inj = self._in(v.get("gas_injectivity"), ["Good", "Fair"])
        water_inj = self._in(v.get("water_injectivity"), ["Good", "Fair"])
        gravity_ok = self._in(v.get("gravity_override_risk"), ["Low", "Medium"])
        gravity_high = self._eq(v.get("gravity_override_risk"), "High")

        hc_source_ok = (
            self._in(v.get("hc_source_status"), ["Available", "Conditional"])
            or self._yes(v.get("hc_gas_availability"))
        )
        gas_source_ok = self._yes(v.get("gas_availability")) or hc_source_ok

        gor_category = str(v.get("produced_gor_category") or "")
        gor_weight = 1.0 if gor_category == "High" else 0.5 if gor_category == "Moderate" else 0.0
        source_conditional = (
            not self._yes(v.get("hc_gas_availability"))
            and gor_category in {"High", "Moderate"}
            and self._yes(v.get("gas_reinjectable"))
        )

        results = []

        causes = []
        for bad, msg in [
            (api < 25, "API <25°"),
            (visc > 10, "Viscosity >10 cP"),
            (depth < 2500, "Depth <2500 ft"),
            (not self._yes(v.get("co2_availability")), "CO2 unavailable"),
            (not self._yes(v.get("mmp_satisfied")), "MMP not satisfied"),
        ]:
            if bad:
                causes.append(msg)
        score = 100 * sum([
            api >= 25, visc <= 10, depth >= 2500,
            self._yes(v.get("co2_availability")),
            self._yes(v.get("mmp_satisfied")), waterflood, mobility_ok,
        ]) / 7
        results.append(self._result("CO2 Miscible Flood", bool(causes), causes, score, 15, v))

        causes, conditional = [], []
        for bad, msg in [
            (api < 25, "API <25°"),
            (visc > 10, "Viscosity >10 cP"),
            (not self._yes(v.get("co2_availability")), "CO2 unavailable"),
            (not self._yes(v.get("mmp_satisfied")), "MMP not satisfied"),
            (not water_fac, "Water injection facilities unavailable"),
            (not gas_fac, "Gas injection facilities unavailable"),
        ]:
            if bad:
                causes.append(msg)
        if gravity_high:
            conditional.append("Conditional: gravity override risk high")
        score = 100 * sum([
            api >= 25, visc <= 10, self._yes(v.get("co2_availability")),
            self._yes(v.get("mmp_satisfied")), water_fac, gas_fac,
            waterflood, gas_inj, water_inj, gravity_ok,
        ]) / 10
        results.append(self._result("CO2 WAG", bool(causes), causes, score, 18, v, conditional))

        causes, conditional = [], []
        for bad, msg in [
            (api < 25, "API <25°"),
            (visc > 10, "Viscosity >10 cP"),
            (depth < 2500, "Depth <2500 ft"),
            (not self._yes(v.get("mmp_satisfied")), "MMP not satisfied"),
            (not hc_source_ok, "HC gas source unavailable"),
        ]:
            if bad:
                causes.append(msg)
        if source_conditional:
            conditional.append("Conditional: produced GOR supports HC gas reinjection/recycling")
        score = 100 * sum([
            api >= 25, visc <= 10, depth >= 2500,
            self._yes(v.get("mmp_satisfied")), hc_source_ok,
            waterflood, mobility_ok, gor_weight,
        ]) / 8
        results.append(self._result("HC Gas Miscible Flood", bool(causes), causes, score, 14, v, conditional))

        causes, conditional = [], []
        for bad, msg in [
            (api < 25, "API <25°"),
            (visc > 10, "Viscosity >10 cP"),
            (not self._yes(v.get("mmp_satisfied")), "MMP not satisfied"),
            (not hc_source_ok, "HC gas source unavailable"),
            (not water_fac, "Water injection facilities unavailable"),
            (not gas_fac, "Gas injection facilities unavailable"),
        ]:
            if bad:
                causes.append(msg)
        if source_conditional:
            conditional.append("Conditional: produced GOR supports HC gas reinjection/recycling")
        if gravity_high:
            conditional.append("Conditional: gravity override risk high")
        score = 100 * sum([
            api >= 25, visc <= 10, self._yes(v.get("mmp_satisfied")),
            hc_source_ok, water_fac, gas_fac, waterflood, gas_inj,
            water_inj, gravity_ok, gor_weight,
        ]) / 11
        results.append(self._result("HC Gas WAG", bool(causes), causes, score, 17, v, conditional))

        causes, conditional = [], []
        for bad, msg in [
            (api < 15, "API <15°"), (visc > 35, "Viscosity >35 cP"),
            (not gas_source_ok, "Gas source unavailable"),
        ]:
            if bad:
                causes.append(msg)
        if source_conditional:
            conditional.append("Conditional: produced GOR supports gas recycling")
        score = 100 * sum([
            api >= 15, visc <= 35, gas_source_ok, waterflood,
            mobility_ok, gor_weight,
        ]) / 6
        results.append(self._result("Immiscible Gas Flood", bool(causes), causes, score, 8, v, conditional))

        causes, conditional = [], []
        for bad, msg in [
            (api < 15, "API <15°"), (visc > 35, "Viscosity >35 cP"),
            (not gas_source_ok, "Gas source unavailable"),
            (not water_fac, "Water injection facilities unavailable"),
            (not gas_fac, "Gas injection facilities unavailable"),
        ]:
            if bad:
                causes.append(msg)
        if source_conditional:
            conditional.append("Conditional: produced GOR supports gas recycling")
        if gravity_high:
            conditional.append("Conditional: gravity override risk high")
        score = 100 * sum([
            api >= 15, visc <= 35, gas_source_ok, waterflood,
            water_fac, gas_fac, gas_inj, water_inj, gravity_ok, gor_weight,
        ]) / 10
        results.append(self._result("Immiscible Gas WAG", bool(causes), causes, score, 12, v, conditional))

        causes = []
        for bad, msg in [
            (temp > 70, "Temperature >70°C"), (tds > 70000, "TDS >70,000 ppm"),
            (hardness > 500, "Hardness >500 ppm"), (perm < 50, "Permeability <50 mD"),
            (self._yes(v.get("oxygen_present")), "Oxygen present in polymer system"),
        ]:
            if bad:
                causes.append(msg)
        score = 100 * sum([
            temp <= 70, tds <= 70000, hardness <= 500, perm >= 50,
            not self._yes(v.get("oxygen_present")), water_cut >= 50, mobility_ok,
        ]) / 7
        results.append(self._result("Polymer (HPAM)", bool(causes), causes, score, 10, v))

        causes = []
        for bad, msg in [
            (temp > 120, "Temperature >120°C"), (tds > 250000, "TDS >250,000 ppm"),
            (hardness > 5000, "Hardness >5,000 ppm"), (perm < 30, "Permeability <30 mD"),
            (self._yes(v.get("oxygen_present")), "Oxygen present in polymer system"),
        ]:
            if bad:
                causes.append(msg)
        score = 100 * sum([
            temp <= 120, tds <= 250000, hardness <= 5000, perm >= 30,
            not self._yes(v.get("oxygen_present")), water_cut >= 50, mobility_ok,
        ]) / 7
        results.append(self._result("Polymer (ATBS)", bool(causes), causes, score, 12, v))

        causes = []
        for bad, msg in [
            (api < 20, "API <20°"), (visc > 35, "Viscosity >35 cP"),
            (temp > 100, "Temperature >100°C"), (tds > 100000, "TDS >100,000 ppm"),
            (self._eq(v.get("adsorption_risk"), "High"), "Surfactant adsorption risk high"),
            (self._eq(v.get("water_handling"), "High"), "Produced-water handling complexity high"),
        ]:
            if bad:
                causes.append(msg)
        score = 100 * sum([
            api >= 20, visc <= 35, temp <= 100, tds <= 100000,
            self._in(v.get("adsorption_risk"), ["Low", "Medium"]),
            self._in(v.get("water_handling"), ["Low", "Medium"]),
            self._in(v.get("rock_type"), ["Sandstone", "Carbonate", "Carbonates"]),
            water_cut >= 50,
        ]) / 8
        results.append(self._result("SP", bool(causes), causes, score, 15, v))

        causes = []
        for bad, msg in [
            (api < 22, "API <22°"), (visc > 30, "Viscosity >30 cP"),
            (temp > 90, "Temperature >90°C"), (tds > 10000, "TDS >10,000 ppm"),
            (hardness > 50, "Hardness >50 ppm"),
            (not self._eq(v.get("rock_type"), "Sandstone"), "Rock type is not Sandstone"),
        ]:
            if bad:
                causes.append(msg)
        score = 100 * sum([
            api >= 22, visc <= 30, temp <= 90, tds <= 10000, hardness <= 50,
            self._eq(v.get("rock_type"), "Sandstone"),
            self._in(v.get("water_handling"), ["Low", "Medium"]), water_cut >= 50,
        ]) / 8
        results.append(self._result("ASP", bool(causes), causes, score, 20, v))

        causes = []
        for bad, msg in [
            (visc < 100, "Viscosity <100 cP"), (depth > 3000, "Depth >3000 ft"),
            (perm < 500, "Permeability <500 mD"),
        ]:
            if bad:
                causes.append(msg)
        score = 100 * sum([visc >= 100, depth <= 3000, perm >= 500, self._no(v.get("offshore"))]) / 4
        results.append(self._result("CSS", bool(causes), causes, score, 15, v))

        causes = []
        for bad, msg in [
            (visc < 100, "Viscosity <100 cP"), (depth > 3000, "Depth >3000 ft"),
            (perm < 1000, "Permeability <1000 mD"),
        ]:
            if bad:
                causes.append(msg)
        score = 100 * sum([visc >= 100, depth <= 3000, perm >= 1000, self._no(v.get("offshore"))]) / 4
        results.append(self._result("Steam Flood", bool(causes), causes, score, 18, v))

        causes = []
        for bad, msg in [
            (visc < 10 or visc > 200, "Viscosity outside 10–200 cP"),
            (perm < 200, "Permeability <200 mD"),
        ]:
            if bad:
                causes.append(msg)
        score = 100 * sum([10 <= visc <= 200, perm >= 200, self._no(v.get("offshore"))]) / 3
        results.append(self._result("ISC", bool(causes), causes, score, 10, v))

        ranked = sorted(enumerate(results), key=lambda x: (-x[1]["Score (%)"], x[0]))

        return {
            "status": "OK",
            "formation": formation,
            "inputs": v,
            "results": [x[1] for x in ranked],
            "source_sheet": SCREENING_TOOL_SHEET,
        }
