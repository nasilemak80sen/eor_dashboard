"""Challenge and lesson-learned data access."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from config.settings import settings


_FIELD_ALIASES = {"field", "field name", "oil field"}
_AREA_ALIASES = {"area", "field area", "challenge area", "category", "challenge category"}
_CHALLENGE_ALIASES = {"challenge", "challenges", "challenge description", "issue", "issues"}
_LESSON_ALIASES = {"lesson", "lessons", "lesson learnt", "lessons learnt", "lesson learned", "lessons learned", "learning"}


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    for token in ["_", "-", "/", "(", ")"]:
        text = text.replace(token, " ")
    return " ".join(text.split())


def _find_column(columns: list[str], aliases: set[str]) -> str | None:
    normalised = {_norm(column): column for column in columns}
    for alias in aliases:
        if alias in normalised:
            return normalised[alias]
    for column in columns:
        candidate = _norm(column)
        if any(alias in candidate for alias in aliases):
            return column
    return None


def _candidate_paths() -> list[Path]:
    return [
        settings.data_dir / "Challenges.xlsx",
        settings.project_root / "Challenges.xlsx",
    ]


@st.cache_data(show_spinner=False)
def load_challenges() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load and normalize the complete challenge/lesson register."""
    errors: list[str] = []
    for path in _candidate_paths():
        if not path.is_file():
            continue
        try:
            workbook = pd.ExcelFile(path, engine="openpyxl")
            sheet_name = workbook.sheet_names[0]
            raw = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
            raw = raw.dropna(how="all").copy()
            raw.columns = [str(column).strip() for column in raw.columns]
            columns = list(raw.columns)

            field_col = _find_column(columns, _FIELD_ALIASES)
            area_col = _find_column(columns, _AREA_ALIASES)
            challenge_col = _find_column(columns, _CHALLENGE_ALIASES)
            lesson_col = _find_column(columns, _LESSON_ALIASES)
            missing = [
                label for label, column in {
                    "Field": field_col,
                    "Challenge": challenge_col,
                    "Lesson": lesson_col,
                }.items()
                if column is None
            ]
            if missing:
                raise ValueError(
                    f"Could not resolve required columns {missing}. Available columns: {columns}"
                )

            out = pd.DataFrame({
                "Field": raw[field_col].astype(str).str.strip(),
                "Area": raw[area_col].astype(str).str.strip() if area_col else "General",
                "Challenge": raw[challenge_col].astype(str).str.strip(),
                "Lesson": raw[lesson_col].astype(str).str.strip(),
            })
            out = out.replace({"nan": None, "None": None, "": None})
            out = out.dropna(subset=["Field", "Challenge", "Lesson"])
            out = out[out["Field"].str.strip().ne("")]
            out = out[out["Challenge"].str.strip().ne("")]
            out = out[out["Lesson"].str.strip().ne("")]
            out["Area"] = out["Area"].replace({None: "General"}).fillna("General")
            out = out.drop_duplicates().reset_index(drop=True)

            metadata = {
                "source_name": path.name,
                "source_path": str(path),
                "sheet_name": sheet_name,
                "rows": len(out),
                "columns": columns,
            }
            return out, metadata
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    raise FileNotFoundError(
        "Could not load the challenge register. Expected data/Challenges.xlsx. "
        + (" | ".join(errors) if errors else "No challenge workbook was found.")
    )
