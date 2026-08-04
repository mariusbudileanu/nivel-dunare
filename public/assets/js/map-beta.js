import { MAP_CONFIG, formatDate, formatNumber } from "./config.js";
import { applyTranslations, countryName, qualityLabel, stationTypeLabel, statusLabel, t } from "./i18n.js";

let map;
let primaryLayer;
let fallbackLayer;
const markers = new Map();
let onSelectStation = () => {};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

function trendClass(properties) {
  if (properties.quality_flag === "suspect") return "suspect";
  if (properties.quality_flag === "provisional") return "provisional";
  if (["stale", "suspended", "unavailable"].includes(properties.source_status)) return properties.source_status;
  if (properties.scope === "international") return properties.source_status === "partial" ? "partial" : "international";
  const value = Number(properties.variation_cm_24h);
  return value > 0 ? "up" : value < 0 ? "down" : "still";
}

function markerIcon(properties, selected = false) {
  return L.divIcon({
    className: "station-marker-wrap",
    html: `<div class="station-marker ${trendClass(properties)}${selected ? " selected" : ""}" aria-hidden="true"></div>`,
    iconSize: [18, 18], iconAnchor: [9, 9], popupAnchor: [0, -10],
  });
}

function valueLine(label, value, unit = "") {
  if (value === null || value === undefined || value === "") return "";
  return `<p><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value)}${unit ? ` ${escapeHtml(unit)}` : ""}</p>`;
}

function popupHtml(properties) {
  const isInternational = properties.scope === "international";
  const variation = properties.variation_cm_24h == null ? null : Number(properties.variation_cm_24h);
  const observation = properties.water_level || properties.discharge || properties.water_temperature;
  const localName = properties.station_name_local && properties.station_name_local !== properties.display_name
    ? `<p class="popup-local-name">${escapeHtml(properties.station_name_local)}</p>` : "";
  const sourceLink = properties.source_url
    ? `<p><a href="${escapeHtml(properties.source_url)}" target="_blank" rel="noopener">${escapeHtml(t("officialSource"))}</a></p>` : "";
  let timeLines = "";
  if (isInternational && observation) {
    if (observation.measurement_date && !observation.measurement_datetime_local && !observation.measurement_datetime_utc) {
      timeLines += valueLine(t("date"), formatDate(observation.measurement_date));
    } else {
      const localValue = observation.measurement_datetime_local || observation.measurement_time_original;
      if (localValue) {
        const zone = observation.measurement_timezone || "";
        timeLines += valueLine(t("sourceTime"), `${formatDate(localValue, true, zone)}${zone ? ` (${zone})` : ""}`);
      }
      if (observation.measurement_datetime_utc) timeLines += valueLine(t("utcTime"), `${formatDate(observation.measurement_datetime_utc, true, "UTC")} UTC`);
    }
  } else if (properties.measurement_datetime) {
    timeLines = valueLine(t("lastObservation"), formatDate(properties.measurement_datetime, true));
  }
  const captureLine = isInternational && properties.capture_datetime_utc
    ? valueLine(t("captureTime"), `${formatDate(properties.capture_datetime_utc, true, "UTC")} UTC`) : "";
  const qualityLine = isInternational && observation?.canonical_quality_flag
    ? `<p><strong>${escapeHtml(t("observationQuality"))}:</strong> <span class="status-tag ${escapeHtml(observation.canonical_quality_flag)}">${escapeHtml(qualityLabel(observation.canonical_quality_flag))}</span></p>` : "";
  return `<div class="station-popup">
    <h3>${escapeHtml(properties.display_name)}</h3>${localName}
    <p>${escapeHtml(countryName(properties.country_code))} · ${escapeHtml(properties.source_label || properties.source_name || "")}</p>
    ${isInternational ? valueLine(t("stationType"), stationTypeLabel(properties.station_type)) : ""}
    ${isInternational && properties.river_name ? valueLine(t("riverLabel"), t("river")) : ""}
    ${properties.river_km == null ? "" : `<p>${escapeHtml(t("kilometre"))} ${formatNumber(properties.river_km)}</p>`}
    ${valueLine(t("currentLevel"), properties.level_cm == null ? null : formatNumber(properties.level_cm), "cm")}
    ${valueLine(t("variation24"), variation == null ? null : `${variation > 0 ? "+" : ""}${formatNumber(variation)}`, "cm")}
    ${valueLine(t("temperature"), properties.water_temperature_c == null ? null : formatNumber(properties.water_temperature_c, 1), "°C")}
    ${valueLine(t("discharge"), properties.discharge_m3_s == null ? null : formatNumber(properties.discharge_m3_s), "m³/s")}
    ${properties.forecast_count ? valueLine(t("availableForecasts"), formatNumber(properties.forecast_count)) : ""}
    ${timeLines}${captureLine}${qualityLine}
    ${properties.country_code === "AT" ? `<p class="warning-copy">! ${escapeHtml(t("austriaTestSourceWarning"))}</p>` : ""}
    ${isInternational ? `<p><strong>${escapeHtml(t("sourceStatus"))}:</strong> <span class="status-tag ${escapeHtml(properties.source_status)}">${escapeHtml(statusLabel(properties.source_status))}</span></p>` : ""}
    ${sourceLink}
    <button class="button primary compact" type="button" data-open-station="${escapeHtml(properties.station_id)}">${escapeHtml(t("openAnalysis"))}</button>
  </div>`;
}

function bindPopup(marker) { marker.bindPopup(popupHtml(marker.properties), { maxWidth: 310 }); }
function bindOpenAnalysisButton(root) {
  const button = root?.querySelector("[data-open-station]");
  button?.addEventListener("click", () => onSelectStation(button.dataset.openStation));
}

export function initMap(elementId, geojson, selectCallback) {
  onSelectStation = selectCallback;
  map = L.map(elementId, { zoomControl: true, attributionControl: true, preferCanvas: true }).setView(MAP_CONFIG.center, MAP_CONFIG.zoom);
  primaryLayer = L.tileLayer(MAP_CONFIG.tiles, { attribution: MAP_CONFIG.attribution, maxZoom: 19 }).addTo(map);
  fallbackLayer = L.tileLayer(MAP_CONFIG.fallbackTiles, { attribution: MAP_CONFIG.fallbackAttribution, maxZoom: 19 });
  primaryLayer.on("tileerror", () => { if (!map.hasLayer(fallbackLayer)) { map.removeLayer(primaryLayer); fallbackLayer.addTo(map); } });
  const bounds = [];
  geojson.features.forEach(feature => {
    const [lng, lat] = feature.geometry.coordinates;
    const properties = feature.properties;
    const marker = L.marker([lat, lng], { icon: markerIcon(properties), keyboard: true, title: properties.display_name })
      .on("click", () => onSelectStation(properties.station_id));
    marker.properties = properties; bindPopup(marker); marker.addTo(map); markers.set(properties.station_id, marker); bounds.push([lat, lng]);
  });
  map.on("popupopen", event => {
    const popup = event.popup.getElement(); applyTranslations(popup);
    bindOpenAnalysisButton(popup);
  });
  if (bounds.length) map.fitBounds(bounds, { padding: [24, 24] });
  return map;
}

export function filterMap(predicate) {
  markers.forEach(marker => {
    const visible = predicate(marker.properties);
    if (visible && !map.hasLayer(marker)) marker.addTo(map);
    if (!visible && map.hasLayer(marker)) map.removeLayer(marker);
  });
}

export function refreshMapLanguage() {
  markers.forEach(marker => { marker.setTooltipContent?.(marker.properties.display_name); bindPopup(marker); });
  if (map?._popup?._source) {
    map._popup.setContent(popupHtml(map._popup._source.properties));
    bindOpenAnalysisButton(map._popup.getElement());
  }
}

export function selectMapStation(stationId, { pan = true, openPopup = false } = {}) {
  markers.forEach(marker => marker.setIcon(markerIcon(marker.properties, marker.properties.station_id === stationId)));
  const marker = markers.get(stationId); if (!marker || !map.hasLayer(marker)) return;
  marker.setZIndexOffset(1000); if (pan) map.panTo(marker.getLatLng(), { animate: true, duration: .35 }); if (openPopup) marker.openPopup();
}

export function resetMap() {
  const bounds = [...markers.values()].filter(marker => map.hasLayer(marker)).map(marker => marker.getLatLng());
  if (bounds.length) map.fitBounds(bounds, { padding: [24, 24] });
}

export function findStation(query) {
  const normalized = query.trim().toLocaleLowerCase();
  const marker = [...markers.values()].find(item => map.hasLayer(item) && `${item.properties.display_name} ${item.properties.station_name_local || ""}`.toLocaleLowerCase().includes(normalized));
  return marker ? { properties: marker.properties } : null;
}

export function refreshMapSize() { setTimeout(() => map?.invalidateSize(), 80); }
