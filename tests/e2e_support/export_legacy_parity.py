"""Generate temporary expected outputs via the current Streamlit service entrypoints for approved cases."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "approved_reservoir_cases.json"

def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not FIXTURE.is_file():
        args.output.write_text(json.dumps({"available": False, "reason": "Approved reservoir fixture not supplied; real-case parity is blocked.", "cases": []}), encoding="utf-8")
        print("Approved reservoir fixture absent; real-case parity will be skipped and remains blocked.")
        return 0

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = fixture.get("cases", [])
    if not cases:
        raise SystemExit("Approved reservoir fixture exists but contains no cases.")
    for case in cases:
        for field in ("id", "approved_by", "approved_on", "source", "formation", "inputs"):
            if not case.get(field):
                raise SystemExit(f"Case {case.get('id', '<unnamed>')}: missing required provenance/input field {field!r}.")

    sys.path.insert(0, str(ROOT / "src"))
    import app_2 as legacy_app
    import hybrid_app as legacy_hybrid_app
    legacy_services = legacy_hybrid_app.initialize_services()
    expected = []
    for case in cases:
        values = case["inputs"]
        formation = case["formation"]
        screen = legacy_app.ExcelScreeningService().screen(values, formation)
        hybrid = legacy_hybrid_app.run_eor_intelligence(legacy_services, values, formation)
        expected.append({
            "id": case["id"],
            "field_id": case.get("field_id"),
            "formation": formation,
            "inputs": values,
            "screening": screen,
            "hybrid": {
                "screening": hybrid["screening"],
                "hybrid": hybrid["hybrid"],
                "model_info": hybrid["model_info"],
            },
        })
    args.output.write_text(json.dumps({"available": True, "cases": expected}, default=_json_default), encoding="utf-8")
    print(f"Generated temporary legacy expectations for {len(expected)} approved case(s); case values are not written to workflow logs.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
