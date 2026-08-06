import { MAP_CONFIG, formatDate, formatNumber } from "./config.js";
import { applyTranslations, coordinateConfidenceLabel, coordinateProvenanceLabel, countryName, frequencyLabel, qualityLabel, stationTypeLabel, statusLabel, t } from "./i18n.js";

let map;
let primaryLayer;
let fallbackLayer;
const markers = new Map();
const markerGroups = [];
let onSelectStation = () => {};
let selectedStationId = null;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

function trendClass(properties) {
  if (properties.quality_flag === "suspect") return "suspect";
  if (properties.quality_flag === "provisional") return "provisional";
  if (properties.freshness_status === "stale") return "stale";
  if (["suspended", "unavailable"].includes(properties.source_status)) return properties.source_status;
  if (properties.scope === "international") return properties.source_status === "partial" ? "partial" : "international";
  const value = Number(properties.variation_cm_24h);
  return value > 0 ? "up" : value < 0 ? "down" : "still";
}

function isApproximate(properties) {
  return properties.coordinate_method === "geocoded_locality" || properties.is_exact_station_location === false;
}

function isManualCoordinate(properties) {
  return properties.coordinate_method === "manually_verified_station_coordinate";
}

function markerIcon(properties, selected = false, count = 1) {
  const approximate = isApproximate(properties);
  return L.divIcon({
    className: "station-marker-wrap",
    html: `<div class="station-marker ${trendClass(properties)}${approximate ? " approximate" : isManualCoordinate(properties) ? " manual-coordinate" : " official-coordinate"}${selected ? " selected" : ""}${count > 1 ? " aggregate" : ""}" aria-hidden="true">${count > 1 ? `<span>${count}</span>` : ""}</div>`,
    iconSize: count > 1 ? [25, 25] : [18, 18], iconAnchor: count > 1 ? [12, 12] : [9, 9], popupAnchor: [0, -10],
  });
}

function valueLine(label, value, unit = "") {
  if (value === null || value === undefined || value === "") return "";
  return `<p><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value)}${unit ? ` ${escapeHtml(unit)}` : ""}</p>`;
}

function rsStreamLine(stream) {
  const latest = stream.latest || {};
  const level = latest.water_level;
  const discharge = latest.discharge;
  const temperature = latest.water_temperature;
  const parts = [t(`stream_${stream.source_stream_type}`)];
  if (stream.is_primary_stream) parts.push(t("primaryStream"));
  if (stream.observation_frequency) parts.push(frequencyLabel(stream.observation_frequency));
  if (level?.value !== null && level?.value !== undefined) parts.push(`${t("currentLevel")}: ${formatNumber(level.value)} ${level.unit || "cm"}`);
  if (discharge?.value !== null && discharge?.value !== undefined) parts.push(`${t("discharge")}: ${formatNumber(discharge.value)} ${discharge.unit || "m³/s"}`);
  if (temperature?.value !== null && temperature?.value !== undefined) parts.push(`${t("temperature")}: ${formatNumber(temperature.value, 1)} ${temperature.unit || "°C"}`);
  const delay = level?.capture_delay_seconds ?? discharge?.capture_delay_seconds ?? temperature?.capture_delay_seconds;
  if (Number.isFinite(Number(delay))) parts.push(t("captureDelayMinutes", { count: formatNumber(Math.max(0, Number(delay)) / 60, 0) }));
  const quality = level?.canonical_quality_flag || discharge?.canonical_quality_flag || temperature?.canonical_quality_flag;
  if (quality) parts.push(qualityLabel(quality));
  if (stream.source_stream_type === "daily") parts.unshift(t("dailyObservation"));
  return `<p>${parts.map(escapeHtml).join(" · ")}</p>`;
}

function coordinateDetails(properties) {
  if (properties.scope !== "international") return "";
  const method = isApproximate(properties) ? t("approximateCoordinates") : isManualCoordinate(properties) ? t("manuallyVerifiedCoordinates") : t("officialCoordinates");
  const coordinate = Number.isFinite(properties.coordinate_latitude) && Number.isFinite(properties.coordinate_longitude)
    ? `${properties.coordinate_latitude.toFixed(5)}, ${properties.coordinate_longitude.toFixed(5)}` : null;
  const sourceValue = properties.coordinate_source || "";
  const source = sourceValue
    ? /^https?:\/\//i.test(sourceValue)
      ? `<p><strong>${escapeHtml(t("coordinateSource"))}:</strong> <a href="${escapeHtml(sourceValue)}" target="_blank" rel="noopener">${escapeHtml(sourceValue)}</a></p>`
      : valueLine(t("coordinateSource"), coordinateProvenanceLabel(sourceValue))
    : "";
  const warning = isApproximate(properties) ? `<p class="warning-copy coordinate-warning">! ${escapeHtml(t("approximateCoordinateWarning"))}</p>` : "";
  const streamDetails = (properties.streams || []).length ? `<div class="stream-list"><strong>${escapeHtml(t("streamCount"))}: ${formatNumber(properties.stream_count || properties.streams.length)}</strong>${properties.streams.map(stream => properties.country_code === "RS" ? rsStreamLine(stream) : `<p>${escapeHtml(t(`stream_${stream.source_stream_type}`))}${stream.is_primary_stream ? ` · ${escapeHtml(t("primaryStream"))}` : ""}${stream.observation_frequency ? ` · ${escapeHtml(frequencyLabel(stream.observation_frequency))}` : ""}</p>`).join("")}</div>` : "";
  return `${valueLine(t("coordinateValue"), coordinate)}${valueLine(t("coordinateMethod"), method)}${valueLine(t("coordinateProvider"), coordinateProvenanceLabel(properties.coordinate_provider))}${valueLine(t("coordinateConfidence"), coordinateConfidenceLabel(properties.coordinate_confidence))}${source}${warning}${streamDetails}`;
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
    ${timeLines}${captureLine}${qualityLine}${coordinateDetails(properties)}
    ${properties.country_code === "AT" ? `<p class="warning-copy">! ${escapeHtml(t("austriaTestSourceWarning"))}</p>` : ""}
    ${properties.country_code === "BG" ? `<p class="warning-copy">! ${escapeHtml(t("appdForecastInactive"))}</p>` : ""}
    ${properties.country_code === "RS" ? `<p class="warning-copy">! ${escapeHtml(t(properties.source_status === "suspended" ? "rsTlsSuspended" : "rsProvisionalData"))}</p>` : ""}
    ${properties.country_code === "HR" && properties.freshness_status === "stale" ? `<p class="warning-copy">! ${escapeHtml(t("hrStaleDetail", { date: properties.published_snapshot_date || t("unavailable") }))}</p>` : ""}
    ${properties.country_code === "HR" ? `<p class="warning-copy">${escapeHtml(t("hrForecastDisclaimer"))}</p>` : ""}
    ${isInternational ? `${valueLine(t("accessStatus"), statusLabel(properties.access_status || "unavailable"))}${valueLine(t("automationStatus"), statusLabel(properties.automation_status || "unavailable"))}${valueLine(t("freshnessStatus"), statusLabel(properties.freshness_status || "unavailable"))}${valueLine(t("validationStatus"), statusLabel(properties.validation_status || "unavailable"))}` : ""}
    ${isInternational ? `<p><strong>${escapeHtml(t("sourceStatus"))}:</strong> <span class="status-tag ${escapeHtml(properties.source_status)}">${escapeHtml(statusLabel(properties.source_status))}</span></p>` : ""}
    ${sourceLink}
    <button class="button primary compact" type="button" data-open-station="${escapeHtml(properties.station_id)}">${escapeHtml(t("openAnalysis"))}</button>
  </div>`;
}

function groupPopupHtml(propertiesList) {
  if (propertiesList.length === 1) return popupHtml(propertiesList[0]);
  const approximate = propertiesList.some(isApproximate);
  return `<div class="station-popup shared-locality-popup">
    <h3>${escapeHtml(t("sharedLocalityStations", { count: propertiesList.length }))}</h3>
    <p>${escapeHtml(t("sharedLocalityCopy"))}</p>
    ${approximate ? `<p class="warning-copy coordinate-warning">! ${escapeHtml(t("approximateCoordinateWarning"))}</p>` : ""}
    <ul>${propertiesList.map(properties => `<li><button class="button ghost compact" type="button" data-open-station="${escapeHtml(properties.station_id)}">${escapeHtml(properties.display_name)} · ${escapeHtml(stationTypeLabel(properties.station_type))}</button></li>`).join("")}</ul>
  </div>`;
}

function bindPopup(group) {
  group.marker.bindPopup(groupPopupHtml(group.visibleProperties), { maxWidth: 360 });
}

function bindOpenAnalysisButtons(root) {
  root?.querySelectorAll("[data-open-station]").forEach(button => button.addEventListener("click", () => onSelectStation(button.dataset.openStation)));
}

function updateGroup(group) {
  if (!group.visibleProperties.length) return;
  group.marker.properties = group.visibleProperties[0];
  const selected = group.visibleProperties.some(item => item.station_id === selectedStationId);
  const aggregateCount = group.visibleProperties.reduce((count, item) => count + Math.max(1, Number(item.stream_count) || 1), 0);
  group.marker.setIcon(markerIcon(group.marker.properties, selected, aggregateCount));
  group.marker.options.title = group.visibleProperties.length > 1 ? t("sharedLocalityStations", { count: group.visibleProperties.length }) : group.marker.properties.display_name;
  bindPopup(group);
}

export function initMap(elementId, geojson, selectCallback) {
  onSelectStation = selectCallback;
  map = L.map(elementId, { zoomControl: true, attributionControl: true, preferCanvas: true }).setView(MAP_CONFIG.center, MAP_CONFIG.zoom);
  primaryLayer = L.tileLayer(MAP_CONFIG.tiles, { attribution: MAP_CONFIG.attribution, maxZoom: 19 }).addTo(map);
  fallbackLayer = L.tileLayer(MAP_CONFIG.fallbackTiles, { attribution: MAP_CONFIG.fallbackAttribution, maxZoom: 19 });
  primaryLayer.on("tileerror", () => { if (!map.hasLayer(fallbackLayer)) { map.removeLayer(primaryLayer); fallbackLayer.addTo(map); } });
  const grouped = new Map();
  geojson.features.forEach(feature => {
    const key = feature.geometry.coordinates.join(",");
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push({ ...feature.properties, coordinate_longitude: feature.geometry.coordinates[0], coordinate_latitude: feature.geometry.coordinates[1] });
  });
  const bounds = [];
  grouped.forEach((propertiesList, key) => {
    const [lng, lat] = key.split(",").map(Number);
    const group = { allProperties: propertiesList, visibleProperties: [...propertiesList], marker: null };
    const marker = L.marker([lat, lng], { icon: markerIcon(propertiesList[0], false, propertiesList.length), keyboard: true, title: propertiesList[0].display_name });
    group.marker = marker; marker.properties = propertiesList[0];
    marker.on("click", () => { if (group.visibleProperties.length === 1) onSelectStation(group.visibleProperties[0].station_id); });
    bindPopup(group); marker.addTo(map); markerGroups.push(group);
    propertiesList.forEach(properties => markers.set(properties.station_id, marker));
    bounds.push([lat, lng]);
  });
  map.on("popupopen", event => { const popup = event.popup.getElement(); applyTranslations(popup); bindOpenAnalysisButtons(popup); });
  if (bounds.length) map.fitBounds(bounds, { padding: [24, 24] });
  return map;
}

export function filterMap(predicate) {
  markerGroups.forEach(group => {
    group.visibleProperties = group.allProperties.filter(predicate);
    const visible = group.visibleProperties.length > 0;
    if (visible) { updateGroup(group); if (!map.hasLayer(group.marker)) group.marker.addTo(map); }
    if (!visible && map.hasLayer(group.marker)) map.removeLayer(group.marker);
  });
}

export function refreshMapLanguage() {
  markerGroups.forEach(updateGroup);
  const source = map?._popup?._source;
  if (source) {
    const group = markerGroups.find(item => item.marker === source);
    if (group) { map._popup.setContent(groupPopupHtml(group.visibleProperties)); bindOpenAnalysisButtons(map._popup.getElement()); }
  }
}

export function selectMapStation(stationId, { pan = true, openPopup = false } = {}) {
  selectedStationId = stationId;
  markerGroups.forEach(updateGroup);
  const marker = markers.get(stationId); if (!marker || !map.hasLayer(marker)) return;
  marker.setZIndexOffset(1000); if (pan) map.panTo(marker.getLatLng(), { animate: true, duration: .35 }); if (openPopup) marker.openPopup();
}

export function resetMap() {
  const bounds = markerGroups.filter(group => map.hasLayer(group.marker)).map(group => group.marker.getLatLng());
  if (bounds.length) map.fitBounds(bounds, { padding: [24, 24] });
}

export function findStation(query) {
  const normalized = query.trim().toLocaleLowerCase();
  for (const group of markerGroups) {
    if (!map.hasLayer(group.marker)) continue;
    const properties = group.visibleProperties.find(item => `${item.display_name} ${item.station_name_local || ""}`.toLocaleLowerCase().includes(normalized));
    if (properties) return { properties };
  }
  return null;
}

export function refreshMapSize() { setTimeout(() => map?.invalidateSize(), 80); }