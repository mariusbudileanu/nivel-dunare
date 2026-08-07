const BASE = new URL("../../data/international/", import.meta.url);

async function getJson(name) {
  const response = await fetch(new URL(name, BASE), { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`International beta data unavailable (${response.status})`);
  return response.json();
}

function measurementKey(row) {
  return row.measurement_datetime_utc || row.measurement_datetime_local || row.measurement_date || row.measurement_time_original;
}

export async function loadInternationalData() {
  const [status, stations, streams, observations, latest, forecasts, sources, geojson, unmapped, qualityIssues] = await Promise.all([
    "status.json", "stations.json", "streams.json", "observations.json", "latest.json", "forecasts.json", "sources.json",
    "stations.geojson", "unmapped_stations.json", "quality_issues.json",
  ].map(getJson));
  const stationsById = new Map(stations.map(station => [station.station_id, station]));
  const observationsByStation = new Map();
  const forecastsByStation = new Map();
  for (const row of observations) {
    if (!observationsByStation.has(row.station_id)) observationsByStation.set(row.station_id, []);
    observationsByStation.get(row.station_id).push(row);
  }
  for (const row of forecasts) {
    if (!forecastsByStation.has(row.station_id)) forecastsByStation.set(row.station_id, []);
    forecastsByStation.get(row.station_id).push(row);
  }
  const sourcesById = new Map(sources.map(source => [source.source_id, source]));
  for (const station of stations) Object.assign(station, sourcesById.get(station.source_id) || {});
  return { status, stations, streams, stationsById, observations, observationsByStation, latest, forecasts, forecastsByStation, sources, sourcesById, geojson, unmapped, qualityIssues };
}

export function internationalMapFeatures(data) {
  return data.geojson.features.map(feature => {
    const p = feature.properties;
    const level = p.water_level;
    const temperature = p.water_temperature;
    const discharge = p.discharge;
    const primary = level || discharge || temperature;
    return {
      ...feature,
      properties: {
        ...p, ...(data.sourcesById.get(p.source_id) || {}), scope: "international", display_name: p.station_name, slug: p.station_slug,
        level_cm: level?.value ?? null, variation_cm_24h: level?.variation_value ?? null,
        water_temperature_c: temperature?.value ?? null, discharge_m3_s: discharge?.value ?? null,
        forecast_count: (p.station_ids || [p.station_id]).reduce((count, stationId) => count + (data.forecastsByStation.get(stationId) || []).length, 0),
        measurement_datetime: primary?.measurement_datetime_local || primary?.measurement_datetime_utc || primary?.measurement_date || null,
        quality_flag: primary?.canonical_quality_flag === "observed" ? "valid" : primary?.canonical_quality_flag || "unavailable",
      },
    };
  });
}

export function enrichRomanianFeatures(geojson) {
  return {
    ...geojson,
    features: geojson.features.map(feature => ({
      ...feature,
      properties: {
        ...feature.properties, scope: "afdj", country_code: "RO", source_id: "afdj_ro", source_label: "AFDJ",
        source_status: "complete", station_type: "gauge", station_name: feature.properties.display_name,
        station_name_local: feature.properties.display_name, source_url: "https://www.afdj.ro/ro/cotele-dunarii",
      },
    })),
  };
}

function cleanForecastIssueDatetime(row) {
  if (row.forecast_issue_datetime_utc) return row.forecast_issue_datetime_utc;
  const raw = row.forecast_issue_time_original || "";
  const match = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})/);
  return match ? `${match[3]}-${match[2]}-${match[1]}` : raw || null;
}

export function legacyStationData(data, stationId) {
  const sourceRows = data.observationsByStation.get(stationId) || [];
  const grouped = new Map();
  for (const row of sourceRows) {
    const key = measurementKey(row);
    if (!grouped.has(key)) grouped.set(key, {
      measurement_datetime: row.measurement_datetime_local || row.measurement_datetime_utc || row.measurement_date,
      measurement_date: (row.measurement_datetime_utc || row.measurement_datetime_local || row.measurement_date || "").slice(0, 10),
      level_cm: null, variation_cm_24h: null, water_temperature_c: null, quality_flag: "valid",
    });
    const item = grouped.get(key);
    if (row.parameter === "water_level") {
      item.level_cm = row.value;
      item.variation_cm_24h = row.variation_value;
      item.quality_flag = row.canonical_quality_flag === "observed" ? "valid" : row.canonical_quality_flag || "valid";
    }
    if (row.parameter === "water_temperature") item.water_temperature_c = row.value;
  }
  const observations = [...grouped.values()].filter(row => row.level_cm !== null).sort((a, b) => String(a.measurement_datetime).localeCompare(String(b.measurement_datetime)));
  const forecasts = (data.forecastsByStation.get(stationId) || []).map(row => ({
    forecast_issue_datetime: cleanForecastIssueDatetime(row),
    target_datetime: row.target_datetime_utc || row.target_date,
    target_date: (row.target_datetime_utc || row.target_date || "").slice(0, 10),
    forecast_level_cm: row.forecast_value, lead_hours: row.lead_hours,
    quality_flag: "valid", forecast_available: true,
  })).sort((a, b) => String(a.target_datetime).localeCompare(String(b.target_datetime)));
  return { observations, forecasts, scores: [] };
}
