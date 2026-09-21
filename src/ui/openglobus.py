"""Reusable OpenGlobus 3D globe renderer for EOR Atlas.

The renderer mirrors the OpenGlobus setup used successfully in the
Competency Assessment System while keeping the EOR Atlas data flow in Python.
Streamlit supplies records; the browser iframe renders the interactive globe.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
import streamlit.components.v1 as components


OPEN_GLOBUS_VERSION = "0.28.7"

# components.html runs the map inside a sandboxed iframe.  The
# OpenGlobus sandbox site is intended for its own example pages and can reject
# module imports from an embedded Streamlit origin.  Use package CDNs that are
# designed to serve ES modules cross-origin instead.
OPEN_GLOBUS_CANDIDATES = [
    {
        "name": "jsDelivr",
        "js": f"https://cdn.jsdelivr.net/npm/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/og.es.js",
        "css": f"https://cdn.jsdelivr.net/npm/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/og.css",
        "resources": f"https://cdn.jsdelivr.net/npm/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/res",
        "fonts": f"https://cdn.jsdelivr.net/npm/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/res/fonts",
        "skybox": f"https://cdn.jsdelivr.net/npm/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/res/skybox/",
    },
    {
        "name": "unpkg",
        "js": f"https://unpkg.com/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/og.es.js",
        "css": f"https://unpkg.com/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/og.css",
        "resources": f"https://unpkg.com/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/res",
        "fonts": f"https://unpkg.com/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/res/fonts",
        "skybox": f"https://unpkg.com/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/res/skybox/",
    },
    {
        "name": "esm.sh",
        "js": f"https://esm.sh/@openglobus/og@{OPEN_GLOBUS_VERSION}",
        "css": f"https://cdn.jsdelivr.net/npm/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/og.css",
        "resources": f"https://cdn.jsdelivr.net/npm/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/res",
        "fonts": f"https://cdn.jsdelivr.net/npm/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/res/fonts",
        "skybox": f"https://cdn.jsdelivr.net/npm/@openglobus/og@{OPEN_GLOBUS_VERSION}/lib/res/skybox/",
    },
]

# Retained for compatibility with callers/tests that referenced the original
# single-endpoint constants.
OPEN_GLOBUS_JS = OPEN_GLOBUS_CANDIDATES[0]["js"]
OPEN_GLOBUS_CSS = OPEN_GLOBUS_CANDIDATES[0]["css"]
OPEN_GLOBUS_RESOURCES = OPEN_GLOBUS_CANDIDATES[0]["resources"]
OPEN_GLOBUS_FONTS = OPEN_GLOBUS_CANDIDATES[0]["fonts"]
OPEN_GLOBUS_SKYBOX = OPEN_GLOBUS_CANDIDATES[0]["skybox"]


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _normalise_records(
    dataframe: pd.DataFrame,
    *,
    latitude: str,
    longitude: str,
    name: str,
    value: str | None = None,
    value_label: str = "Value",
    detail_columns: Sequence[tuple[str, str]] = (),
) -> list[dict[str, Any]]:
    if dataframe is None or dataframe.empty:
        return []

    required = {latitude, longitude, name}
    missing = sorted(required.difference(dataframe.columns))
    if missing:
        raise ValueError(
            f"OpenGlobus data is missing required columns: {', '.join(missing)}"
        )

    records: list[dict[str, Any]] = []
    for _, row in dataframe.iterrows():
        lat = _safe_float(row.get(latitude))
        lon = _safe_float(row.get(longitude))
        label = _safe_text(row.get(name))
        if lat is None or lon is None or not label:
            continue

        magnitude = _safe_float(row.get(value)) if value else None
        details: dict[str, str] = {}
        for display_label, column in detail_columns:
            details[display_label] = _safe_text(row.get(column), "—")

        records.append(
            {
                "name": label,
                "latitude": lat,
                "longitude": lon,
                "value": magnitude,
                "value_label": value_label,
                "details": details,
            }
        )
    return records


def _build_openglobus_html(
    records: Iterable[Mapping[str, Any]],
    *,
    title: str,
    subtitle: str,
    height: int = 560,
    center_lat: float = 4.2,
    center_lon: float = 102.0,
    camera_height: float = 11000000,
    show_labels: bool = True,
) -> str:
    safe_height = max(520, int(height))
    record_list = [dict(record) for record in records]
    payload = json.dumps(record_list, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )

    template = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{width:100%;height:100%;margin:0;padding:0;overflow:hidden;background:transparent;font-family:Inter,Arial,sans-serif}
#shell{position:relative;width:100%;height:__HEIGHT__px;min-height:520px;overflow:hidden;border-radius:16px;background:radial-gradient(circle at 50% 42%,#ffffff 0%,#edf5f5 60%,#dfeaec 100%);box-shadow:inset 0 0 0 1px rgba(18,47,53,.08)}
#globus{position:absolute;inset:0;width:100%;height:100%}
#hud{position:absolute;left:16px;top:14px;z-index:40;padding:10px 13px;border-radius:11px;background:rgba(255,255,255,.9);backdrop-filter:blur(9px);box-shadow:0 6px 22px rgba(18,47,53,.12);color:#183238;pointer-events:none}
#hud .title{font-size:13px;font-weight:750}.subtitle{margin-top:3px;font-size:10px;color:#63767a;max-width:520px}
#status{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);z-index:60;padding:12px 16px;border-radius:10px;background:rgba(255,255,255,.96);box-shadow:0 8px 28px rgba(18,47,53,.18);font-size:13px;color:#183238}
#status.hidden{display:none}
#details{position:absolute;right:16px;top:16px;z-index:50;width:min(330px,calc(100% - 32px));max-height:calc(100% - 32px);overflow:auto;box-sizing:border-box;padding:14px;border-radius:13px;background:rgba(255,255,255,.95);backdrop-filter:blur(10px);box-shadow:0 10px 30px rgba(18,47,53,.18);color:#183238;display:none}
#details.visible{display:block}
#details .close{float:right;border:0;background:transparent;cursor:pointer;font-size:20px;color:#52676b}
#details h3{margin:0 30px 3px 0;font-size:17px}
.muted{font-size:10px;color:#63767a}
.kpi{margin:12px 0 10px;padding:10px;border-radius:10px;background:#f5f7f9}
.kpi strong{font-size:19px}.detail-row{padding:7px 0;border-top:1px solid #e7eeee;font-size:11px;line-height:1.35}.detail-label{color:#63767a}.detail-value{font-weight:650;color:#183238}
#controls{position:absolute;left:16px;bottom:16px;z-index:45;display:flex;gap:7px;padding:8px;border-radius:11px;background:rgba(255,255,255,.9);backdrop-filter:blur(8px);box-shadow:0 8px 25px rgba(18,47,53,.13)}
#controls button{border:1px solid #d4e0e2;border-radius:8px;padding:7px 10px;background:#fff;color:#183238;font-size:10px;font-weight:700;cursor:pointer}
#controls button:hover{border-color:#00a19c}
#attribution{position:absolute;right:11px;bottom:9px;z-index:40;padding:4px 7px;border-radius:6px;background:rgba(255,255,255,.7);color:#556a6e;font-size:8px}
#attribution a{color:#37666b;text-decoration:none}
@media(max-width:700px){#details{width:calc(100% - 32px);max-height:47%;top:auto;bottom:64px}#attribution{display:none}}
</style>
</head>
<body>
<div id="shell">
  <div id="globus"></div>
  <div id="hud">
    <div class="title">🌍 __TITLE__</div>
    <div class="subtitle">__SUBTITLE__</div>
  </div>
  <div id="status">Loading 3D Earth…</div>
  <div id="details">
    <button class="close" id="closeDetails">×</button>
    <h3 id="detailName">Selected record</h3>
    <div class="muted" id="detailValue"></div>
    <div class="kpi"><strong id="detailLatLon">—</strong><div class="muted">latitude / longitude</div></div>
    <div id="detailRows"></div>
    <button id="flyTo" style="width:100%;margin-top:10px;padding:8px;border:1px solid #00a19c;border-radius:8px;background:#00a19c;color:#fff;font-weight:700;cursor:pointer">📍 Fly to location</button>
  </div>
  <div id="controls">
    <button id="resetView">↺ Reset globe</button>
    <button id="closeDetailControl">× Close detail</button>
  </div>
  <div id="attribution">OpenGlobus · Bing Maps imagery · EOR Atlas</div>
</div>

<script type="module">
const records = __PAYLOAD__;
const assetCandidates = __ASSET_CANDIDATES__;
const status = document.getElementById("status");
const details = document.getElementById("details");
const detailName = document.getElementById("detailName");
const detailValue = document.getElementById("detailValue");
const detailLatLon = document.getElementById("detailLatLon");
const detailRows = document.getElementById("detailRows");
let globe = null;
let markerLayer = null;
let selectedRecord = null;
let rendererReady = false;
let startupStage = "initializing";

function showRuntimeFailure(error, stage){
  const message = error && error.message ? error.message : String(error);
  console.error("OpenGlobus runtime failure:", error);
  if (!rendererReady) {
    status.innerHTML = "<b>OpenGlobus failed to start</b><br><span style='font-size:11px'>" +
      escapeHtml(message) +
      "</span><br><span style='font-size:10px;color:#63767a'>Stage: " +
      escapeHtml(stage || startupStage) +
      "</span>";
  }
}

window.addEventListener("error", event => {
  if (event && event.error) showRuntimeFailure(event.error, "browser runtime");
});

window.addEventListener("unhandledrejection", event => {
  if (event && event.reason) showRuntimeFailure(event.reason, "async runtime");
});

// These constructors are used by helper functions defined outside boot().
// Keep them at module scope because the OpenGlobus module is loaded
// dynamically at runtime.
let OGEntity = null;
let OGLonLat = null;

const center = {lat: __CENTER_LAT__, lon: __CENTER_LON__, height: __CAMERA_HEIGHT__};
const showLabels = __SHOW_LABELS__;
const markerMaxValue = records.reduce((maxValue, record) => {
  const number = Number(record.value);
  return Number.isFinite(number) && number > maxValue ? number : maxValue;
}, 1);

function escapeHtml(value){
  return String(value).replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[ch]));
}

function formatValue(value){
  if(value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString(undefined,{maximumFractionDigits:2}) : String(value);
}

function markerSvg(value, selected){
  const maxValue = markerMaxValue;
  const numeric = Number(value);
  const ratio = Number.isFinite(numeric) ? Math.sqrt(Math.max(numeric,0))/Math.sqrt(maxValue) : .35;
  const radius = 8 + Math.max(.18,Math.min(1,ratio))*12;
  const size = Math.ceil(radius*2+10);
  const fill = selected ? "#20419A" : "#00A19C";
  const cx = size/2, cy = radius+5;
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="'+size+'" height="'+size+'" viewBox="0 0 '+size+' '+size+'">'+
    '<circle cx="'+cx+'" cy="'+cy+'" r="'+radius+'" fill="'+fill+'" fill-opacity=".94" stroke="#fff" stroke-width="3"/>'+
    '<circle cx="'+cx+'" cy="'+cy+'" r="'+Math.max(3,radius*.28)+'" fill="#fff"/></svg>';
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}

function renderDetails(record){
  selectedRecord = record;
  detailName.textContent = record.name;
  detailValue.textContent = record.value === null
    ? ""
    : String(record.value_label || "Value") + ": " + formatValue(record.value);
  detailLatLon.textContent = Number(record.latitude).toFixed(4) + " / " + Number(record.longitude).toFixed(4);
  detailRows.innerHTML = Object.entries(record.details || {}).map(([label,value]) =>
    '<div class="detail-row"><span class="detail-label">'+escapeHtml(label)+': </span><span class="detail-value">'+escapeHtml(value || "—")+'</span></div>'
  ).join("");
  details.classList.add("visible");
  renderLayer();
}

function renderLayer(){
  if(!markerLayer) return;
  const entities = records.map(record => {
    const selected = selectedRecord && selectedRecord.name === record.name && selectedRecord.latitude === record.latitude && selectedRecord.longitude === record.longitude;
    const valueText = record.value === null ? "" : " · " + formatValue(record.value);
    const entityOptions = {
      name: record.name,
      lonlat: [record.longitude, record.latitude],
      billboard: {
        src: markerSvg(record.value, selected),
        size: [46,46],
        offset: [0,20]
      },
      properties: record
    };

    if (showLabels || selected) {
      entityOptions.label = {
        text: record.name + valueText,
        size: selected ? 15 : 11,
        offset: [0,30,0],
        color: selected ? "rgba(32,65,154,.98)" : "rgba(24,50,56,.94)",
        outlineColor: "rgba(255,255,255,.96)",
        outline: 2
      };
    }

    return new OGEntity(entityOptions);
  });
  markerLayer.setEntities(entities);
}

function flyToRecord(record){
  if(!globe || !globe.planet || !globe.planet.camera) return;
  globe.planet.camera.flyLonLat(new OGLonLat(record.longitude,record.latitude,Math.max(800000,center.height/3)),{duration:900});
}

function clearDetails(){
  selectedRecord = null;
  details.classList.remove("visible");
  renderLayer();
}

document.getElementById("closeDetails").addEventListener("click",clearDetails);
document.getElementById("closeDetailControl").addEventListener("click",clearDetails);
document.getElementById("flyTo").addEventListener("click",()=>{if(selectedRecord) flyToRecord(selectedRecord)});
document.getElementById("resetView").addEventListener("click",()=>{
  clearDetails();
  if(globe && globe.planet && globe.planet.camera){
    globe.planet.camera.setLonLat(new OGLonLat(center.lon,center.lat,center.height));
  }
});

const OPEN_GLOBUS_IMPORT_TIMEOUT_MS = 8000;

function importWithTimeout(url){
  return Promise.race([
    import(url),
    new Promise((_, reject) => {
      window.setTimeout(
        () => reject(new Error("Timed out loading OpenGlobus module after " + OPEN_GLOBUS_IMPORT_TIMEOUT_MS + " ms.")),
        OPEN_GLOBUS_IMPORT_TIMEOUT_MS
      );
    })
  ]);
}

async function loadOpenGlobus() {
  const failures = [];

  for (const candidate of assetCandidates) {
    try {
      status.textContent = "Loading OpenGlobus · " + candidate.name + "…";
      const module = await importWithTimeout(candidate.js);

      // CSS is cosmetic; append it only after the matching JS bundle loads so
      // a blocked stylesheet cannot prevent the globe from booting.
      const stylesheet = document.createElement("link");
      stylesheet.rel = "stylesheet";
      stylesheet.href = candidate.css;
      document.head.appendChild(stylesheet);

      return {module, candidate};
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      failures.push(candidate.name + ": " + message);
    }
  }

  throw new Error(
    "All OpenGlobus asset hosts failed. " + failures.join(" | ")
  );
}

async function boot() {
try {
  startupStage = "loading OpenGlobus module";
  const {module: openGlobus, candidate} = await loadOpenGlobus();
  const { Globe, GlobusRgbTerrain, Bing, scene, Vector, Entity, LonLat } = openGlobus;
  OGEntity = Entity;
  OGLonLat = LonLat;

  const resourceRoot = candidate.resources.replace(/\\/+$|\/$/g, "");
  const skybox = scene.SkyBox.createDefault(resourceRoot + "/");

  startupStage = "creating globe";
  globe = new Globe({
    target: "globus",
    skybox,
    name: "EOR Atlas",
    terrain: new GlobusRgbTerrain(),
    layers: [new Bing()],
    sun: {active: true},
    atmosphereEnabled: true,
    resourcesSrc: resourceRoot,
    fontsSrc: candidate.fonts,
    navigation: {mode: "lockNorth", inertia: .18, zoomSpeed: 1.15},
    autoActivate: false
  });

  startupStage = "initializing WebGL renderer";
  globe.renderer.initialize();
  const handler = globe.renderer && globe.renderer.handler;
  if (!globe.renderer.isInitialized() || !handler || !handler.isInitialized() || !handler.gl) {
    throw new Error(
      "WebGL could not be initialized in the Streamlit iframe. " +
      "Check browser WebGL/GPU availability."
    );
  }

  startupStage = "setting initial camera";
  globe.planet.camera.setLonLat(new OGLonLat(center.lon,center.lat,center.height));

  startupStage = "creating marker layer";
  markerLayer = new Vector("EOR Atlas Records", {
    entities: [],
    pickingEnabled: true,
    async: false
  });

  startupStage = "adding marker layer to globe";
  markerLayer.addTo(globe.planet);

  startupStage = "binding map interaction";
  if(globe.renderer && globe.renderer.events){
    globe.renderer.events.on("lclick", event => {
      const picked = event.pickingObject;
      if(!picked || !picked.properties || !picked.properties.name) return;
      renderDetails(picked.properties);
      flyToRecord(picked.properties);
    });
  }

  startupStage = "rendering map entities";
  renderLayer();

  startupStage = "starting renderer";
  if(globe.renderer && globe.renderer.events){
    const markRendererReady = () => {
      rendererReady = true;
      globe.renderer.events.off("postdraw", markRendererReady);
    };
    globe.renderer.events.on("postdraw", markRendererReady);
  }

  globe.start();
  rendererReady = true;
  status.classList.add("hidden");

  window.setTimeout(() => {
    if (!globe || !globe.renderer || !globe.renderer.handler || !globe.renderer.handler.isInitialized()) {
      showRuntimeFailure(
        new Error("OpenGlobus renderer stopped before producing a frame."),
        "renderer startup"
      );
    }
  }, 5000);
} catch(error){
  console.error("OpenGlobus initialization failed:",error);
  showRuntimeFailure(error, startupStage);
}
}

boot();
</script>
</body>
</html>"""

    asset_candidates = json.dumps(OPEN_GLOBUS_CANDIDATES, ensure_ascii=False, separators=(",", ":"))

    return (
        template.replace("__CSS__", OPEN_GLOBUS_CSS)
        .replace("__JS__", OPEN_GLOBUS_JS)
        .replace("__RESOURCES__", OPEN_GLOBUS_RESOURCES)
        .replace("__FONTS__", OPEN_GLOBUS_FONTS)
        .replace("__SKYBOX__", OPEN_GLOBUS_SKYBOX)
        .replace("__ASSET_CANDIDATES__", asset_candidates)
        .replace("__HEIGHT__", str(safe_height))
        .replace("__CENTER_LAT__", str(float(center_lat)))
        .replace("__CENTER_LON__", str(float(center_lon)))
        .replace("__CAMERA_HEIGHT__", str(float(camera_height)))
        .replace("__SHOW_LABELS__", "true" if show_labels else "false")
        .replace("__TITLE__", _safe_text(title, "EOR Atlas Globe"))
        .replace("__SUBTITLE__", _safe_text(subtitle, "Interactive OpenGlobus map"))
        .replace("__PAYLOAD__", payload)
    )


def render_openglobus_map(
    dataframe: pd.DataFrame,
    *,
    latitude: str,
    longitude: str,
    name: str,
    value: str | None = None,
    value_label: str = "Value",
    detail_columns: Sequence[tuple[str, str]] = (),
    title: str = "EOR Atlas Globe",
    subtitle: str = "Interactive 3D EOR portfolio map",
    height: int = 560,
    camera_height: float = 11000000,
    show_labels: bool = True,
) -> None:
    """Render a workbook/dataframe-backed OpenGlobus map inside Streamlit."""
    records = _normalise_records(
        dataframe,
        latitude=latitude,
        longitude=longitude,
        name=name,
        value=value,
        value_label=value_label,
        detail_columns=detail_columns,
    )
    if not records:
        raise ValueError("OpenGlobus map data cannot be empty.")

    center_lat = sum(float(item["latitude"]) for item in records) / len(records)
    center_lon = sum(float(item["longitude"]) for item in records) / len(records)

    components.html(
        _build_openglobus_html(
            records,
            title=title,
            subtitle=subtitle,
            height=height,
            center_lat=center_lat,
            center_lon=center_lon,
            camera_height=camera_height,
            show_labels=show_labels,
        ),
        height=max(520, int(height)),
        scrolling=False,
    )


__all__ = [
    "OPEN_GLOBUS_VERSION",
    "OPEN_GLOBUS_CANDIDATES",
    "render_openglobus_map",
    "_build_openglobus_html",
    "_normalise_records",
]
