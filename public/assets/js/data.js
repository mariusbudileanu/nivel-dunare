const DATA_BASE = new URL("../../data/", import.meta.url);
const cache = new Map();

async function getJson(path) {
  if (cache.has(path)) return cache.get(path);
  const promise = fetch(new URL(path, DATA_BASE), { headers: { Accept: "application/json" } })
    .then(response => {
      if (!response.ok) throw new Error(`Date indisponibile (${response.status})`);
      return response.json();
    });
  cache.set(path, promise);
  try { return await promise; } catch (error) { cache.delete(path); throw error; }
}

export async function loadStartupData() {
  const [status, geojson, downloads] = await Promise.all([
    getJson("status.json"), getJson("latest.geojson"), getJson("downloads.json")
  ]);
  return { status, geojson, downloads };
}

export async function loadStation(slug) {
  const [observations, forecasts, scores] = await Promise.all([
    getJson(`station/${slug}-observations.json`),
    getJson(`station/${slug}-forecasts.json`),
    getJson(`station/${slug}-forecast-scores.json`)
  ]);
  return { observations, forecasts, scores };
}

export function dataUrl(path) { return new URL(path, DATA_BASE).href; }
