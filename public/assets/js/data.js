import { enrichRomanianFeatures, internationalMapFeatures, legacyStationData, loadInternationalData } from "./international.js";

const DATA_BASE = new URL("../../data/", import.meta.url);
const cache = new Map();
let internationalData;

async function getJson(path) {
  if (cache.has(path)) return cache.get(path);
  const promise = fetch(new URL(path, DATA_BASE), { headers: { Accept: "application/json" } })
    .then(response => {
      if (!response.ok) throw new Error(`Data unavailable (${response.status})`);
      return response.json();
    });
  cache.set(path, promise);
  try { return await promise; } catch (error) { cache.delete(path); throw error; }
}

export async function loadStartupData() {
  const [status, romanianGeojson, downloads, international] = await Promise.all([
    getJson("status.json"), getJson("latest.geojson"), getJson("downloads.json"), loadInternationalData(),
  ]);
  internationalData = international;
  const ro = enrichRomanianFeatures(romanianGeojson);
  const geojson = { ...ro, features: [...ro.features, ...internationalMapFeatures(international)] };
  return { status, geojson, downloads, international };
}

export async function loadStation(slug) {
  if (internationalData) {
    const station = internationalData.stations.find(item => item.station_slug === slug);
    if (station) return legacyStationData(internationalData, station.station_id);
  }
  const [observations, forecasts, scores] = await Promise.all([
    getJson(`station/${slug}-observations.json`), getJson(`station/${slug}-forecasts.json`), getJson(`station/${slug}-forecast-scores.json`),
  ]);
  return { observations, forecasts, scores };
}

export function dataUrl(path) { return new URL(path, DATA_BASE).href; }