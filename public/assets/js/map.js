import { COLORS, MAP_CONFIG, formatDate, formatNumber } from "./config.js";

let map;
let primaryLayer;
let fallbackLayer;
const markers = new Map();
let onSelectStation = () => {};

function trendClass(properties) {
  if (properties.quality_flag !== "valid") return "alert";
  const value = Number(properties.variation_cm_24h);
  return value > 0 ? "up" : value < 0 ? "down" : "still";
}

function markerIcon(properties, selected = false) {
  return L.divIcon({
    className: "station-marker-wrap",
    html: `<div class="station-marker ${trendClass(properties)}${selected ? " selected" : ""}" aria-hidden="true"></div>`,
    iconSize: [18, 18], iconAnchor: [9, 9], popupAnchor: [0, -10]
  });
}

function popupHtml(properties) {
  const variation = Number(properties.variation_cm_24h);
  const sign = variation > 0 ? "+" : "";
  return `<div class="station-popup">
    <h3>${properties.display_name}</h3><p>Km ${formatNumber(properties.river_km)}</p>
    <p><strong>Nivel actual:</strong> ${formatNumber(properties.level_cm)} cm</p>
    <p><strong>Variație 24 h:</strong> ${sign}${formatNumber(variation)} cm</p>
    <p><strong>Temperatură:</strong> ${formatNumber(properties.water_temperature_c, 1)} °C</p>
    <p><strong>Data:</strong> ${formatDate(properties.measurement_datetime)}</p>
    <p><strong>Stare:</strong> ${properties.quality_flag === "valid" ? "validată" : "atenționare"}</p>
    <button class="button primary compact" type="button" data-open-station="${properties.station_id}">Deschide analiza</button>
  </div>`;
}

export function initMap(elementId, geojson, selectCallback) {
  onSelectStation = selectCallback;
  map = L.map(elementId, { zoomControl: true, attributionControl: true, preferCanvas: true })
    .setView(MAP_CONFIG.center, MAP_CONFIG.zoom);
  primaryLayer = L.tileLayer(MAP_CONFIG.tiles, { attribution: MAP_CONFIG.attribution, maxZoom: 19 }).addTo(map);
  fallbackLayer = L.tileLayer(MAP_CONFIG.fallbackTiles, { attribution: MAP_CONFIG.fallbackAttribution, maxZoom: 19 });
  primaryLayer.on("tileerror", () => {
    if (!map.hasLayer(fallbackLayer)) { map.removeLayer(primaryLayer); fallbackLayer.addTo(map); }
  });
  const bounds = [];
  geojson.features.forEach(feature => {
    const [lng, lat] = feature.geometry.coordinates;
    const properties = feature.properties;
    const marker = L.marker([lat, lng], { icon: markerIcon(properties), keyboard: true, title: properties.display_name })
      .bindPopup(popupHtml(properties), { maxWidth: 270 })
      .on("click", () => onSelectStation(properties.station_id));
    marker.properties = properties;
    marker.addTo(map);
    markers.set(properties.station_id, marker);
    bounds.push([lat, lng]);
  });
  map.on("popupopen", event => {
    const button = event.popup.getElement()?.querySelector("[data-open-station]");
    button?.addEventListener("click", () => onSelectStation(button.dataset.openStation));
  });
  if (bounds.length) map.fitBounds(bounds, { padding: [24, 24] });
  return map;
}

export function selectMapStation(stationId, { pan = true, openPopup = false } = {}) {
  markers.forEach(marker => marker.setIcon(markerIcon(marker.properties, marker.properties.station_id === stationId)));
  const marker = markers.get(stationId);
  if (!marker) return;
  marker.setZIndexOffset(1000);
  if (pan) map.panTo(marker.getLatLng(), { animate: true, duration: .35 });
  if (openPopup) marker.openPopup();
}

export function resetMap() {
  const bounds = [...markers.values()].map(marker => marker.getLatLng());
  if (bounds.length) map.fitBounds(bounds, { padding: [24, 24] });
}

export function findStation(query) {
  const normalized = query.trim().toLocaleLowerCase("ro-RO");
  return [...markers.values()].find(marker => marker.properties.display_name.toLocaleLowerCase("ro-RO").includes(normalized));
}

export function refreshMapSize() { setTimeout(() => map?.invalidateSize(), 80); }
