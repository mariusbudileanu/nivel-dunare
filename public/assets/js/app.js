import { RANGE_DAYS, formatDate, formatNumber } from "./config.js";
import { dataUrl, loadStartupData, loadStation } from "./data.js";
import { filterMap, findStation, initMap, refreshMapLanguage, refreshMapSize, resetMap, selectMapStation } from "./map-beta.js";
import { initBetaUi } from "./beta-ui.js";
import { applyTranslations, countryName, getLocale, initLanguage, issueLabel, onLanguageChange, statusLabel, t, toggleLanguage } from "./i18n.js";
import {
  downloadChartCsv, downloadChartPng, renderComparison, renderHistory,
  renderLevel, renderScores, renderTemperature, renderVariation, resizeChart
} from "./charts.js";

const state = {
  status: null, features: [], stations: new Map(), stationData: new Map(),
  selectedId: null, activeTab: "level", rangePreset: "30d", range: {}, selectedDate: null,
  compareIds: [], compareMode: "delta",
  filterPredicate: () => true, international: null
};

let downloadEntries = [];
const chartIds = {
  level: "chart-level", variation: "chart-variation", temperature: "chart-temperature",
  history: "chart-history", scores: "chart-scores"
};

function $(selector, root = document) { return root.querySelector(selector); }
function $$(selector, root = document) { return [...root.querySelectorAll(selector)]; }

function toast(message, timeout = 3200) {
  const element = $("#toast"); element.textContent = message; element.hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => { element.hidden = true; }, timeout);
}

function trend(value) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return { key: "none", symbol: "•", label: t("noTrendAvailable") };
  const number = Number(value);
  if (number > 0) return { key: "up", symbol: "+", label: t("trendUp") };
  if (number < 0) return { key: "down", symbol: "−", label: t("trendDown") };
  return { key: "still", symbol: "0", label: t("trendStill") };
}

function stationFreshness(properties) {
  if (properties.freshness_status === "stale") return { key: "stale", label: t("stale") };
  if (properties.freshness_status === "unavailable" || properties.access_status === "unavailable" || properties.access_status === "tls_failed") return { key: "unavailable", label: t("freshnessUnavailable") };
  if (properties.quality_flag === "provisional" || properties.validation_status === "source_provisional") return { key: "provisional", label: t("provisional") };
  return { key: "current", label: t("current") };
}

const STREAM_BADGE_KEYS = { manual: "stream_manual", automatic: "stream_automatic", nrt: "stream_automatic", daily: "stream_daily", daily_manual: "stream_daily", forecast: "stream_forecast" };
function streamBadges(properties) {
  return [...new Set((properties.streams || []).map(stream => STREAM_BADGE_KEYS[stream.source_stream_type]).filter(Boolean))];
}

const COUNTRY_ORDER = ["RO", "BG", "RS", "HR", "HU", "SK", "AT", "DE"];
// RS/HU/SK currently publish no river_km at all (data/reference/ris_station_registry.csv
// only has waterway_km for HR and BG). For these three, within-country order is computed
// from station coordinates (principal-axis projection) rather than a sourced chainage
// value - it is an approximation, not an official kilometre, and is labelled as such in
// the station list. The projection naturally comes out upstream-first for all three and
// needs reversing; verified against a real neighbouring river_km, not assumed:
//  RS: rs-bezdan (45.844,18.858) sits on Croatia's Batina gauge (45.846,18.855; real
//      waterway_km 1424.6, HR's highest/most-upstream station) -> Bezdan is RS's
//      upstream end.
//  HU: hu-mohacs (45.993,18.682) is ~25 km from that same Batina gauge -> Mohács is
//      HU's downstream end, not its upstream one.
//  SK: sk-devin/-devin-lom sit at the Austrian border (the Morava confluence); Austria's
//      own lowest real river_km station (Thebnerstraßl, km 1879) is the closest AT gauge
//      to Devín, confirming Devín is SK's upstream end.
const GEOGRAPHIC_ORDER_REVERSED = new Set(["RS", "HU", "SK"]);

function computeAxisOrder(rows) {
  const n = rows.length;
  const meanLat = rows.reduce((sum, row) => sum + row.latitude, 0) / n;
  const meanLon = rows.reduce((sum, row) => sum + row.longitude, 0) / n;
  let sxx = 0, syy = 0, sxy = 0;
  rows.forEach(row => { const dx = row.longitude - meanLon, dy = row.latitude - meanLat; sxx += dx * dx; syy += dy * dy; sxy += dx * dy; });
  const theta = 0.5 * Math.atan2(2 * sxy, sxx - syy);
  const vx = Math.cos(theta), vy = Math.sin(theta);
  return [...rows].sort((a, b) => ((a.longitude - meanLon) * vx + (a.latitude - meanLat) * vy) - ((b.longitude - meanLon) * vx + (b.latitude - meanLat) * vy));
}

function orderWithinCountry(countryCode, rows) {
  if (rows.every(row => row.river_km != null)) return [...rows].sort((a, b) => a.river_km - b.river_km);
  if (!rows.every(row => Number.isFinite(row.latitude) && Number.isFinite(row.longitude))) return [...rows].sort((a, b) => a.display_name.localeCompare(b.display_name, getLocale()));
  const axisOrder = computeAxisOrder(rows);
  return GEOGRAPHIC_ORDER_REVERSED.has(countryCode) ? axisOrder.reverse() : axisOrder;
}

function selectedStation() { return state.stations.get(state.selectedId); }
function valueWithUnit(value, unit, digits = 0) {
  return value === null || value === undefined || value === "" ? t("unavailable") : `${formatNumber(value, digits)} ${unit}`;
}

function afdjSourceEntry(status) {
  return {
    source_id: "afdj_ro", country_code: "RO", label: "AFDJ", source_url: "https://www.afdj.ro/ro/cotele-dunarii",
    physical_station_count: status.station_count, station_count: status.station_count,
    update_frequency: "5x daily Europe/Bucharest", source_observation_frequency: [],
    last_attempt_at: status.last_capture_datetime_local, last_success_at: status.last_capture_datetime_local,
    last_source_observation_at: status.latest_measurement_datetime,
    access_status: "available", automation_status: "scheduled",
    freshness_status: status.system_status === "operational" ? "current" : "unavailable",
    source_status: "complete", validation_status: "not_applicable",
    validation_message_ro: "Date actualizate automat de pe Hetzner, de 5 ori pe zi (07:00, 10:00, 12:00, 18:00, 21:00 Europe/Bucharest).",
    validation_message_en: "Data updated automatically from Hetzner, five times a day (07:00, 10:00, 12:00, 18:00, 21:00 Europe/Bucharest).",
  };
}

function applyStatus(status) {
  state.status = status;
  $("#technical-status").textContent = JSON.stringify(status, null, 2);
  const archiveDays = Math.max(0, (new Date(status.latest_measurement_date) - new Date(status.archive_start_date)) / 86400000);
  if (archiveDays < 30 && !new URLSearchParams(location.search).has("range")) state.rangePreset = "all";
}

function latestGlobalObservation() {
  const candidates = [state.status?.latest_measurement_datetime, ...(state.international?.sources || []).map(source => source.last_source_observation_at)].filter(Boolean);
  return candidates.reduce((latest, value) => (!latest || new Date(value) > new Date(latest)) ? value : latest, null);
}

function latestGlobalCapture() {
  const candidates = [state.status?.last_capture_datetime_local, state.international?.status?.generated_from_capture_utc].filter(Boolean);
  return candidates.reduce((latest, value) => (!latest || new Date(value) > new Date(latest)) ? value : latest, null);
}

function renderUpdateBar() {
  const status = state.status; const international = state.international;
  const sources = international.sources;
  const current = sources.filter(source => source.freshness_status === "current" && source.access_status === "available").length;
  const stale = sources.filter(source => source.freshness_status === "stale").length;
  const manual = sources.filter(source => source.automation_status === "manual").length;
  const unavailable = sources.filter(source => source.freshness_status === "unavailable" || source.access_status !== "available").length;
  const mixed = sources.some(source => source.automation_status !== "scheduled" || source.freshness_status !== "current" || source.source_status !== "complete");
  const afdjWarning = status.system_status !== "operational" || status.xml_html_mismatch_count > 0;
  const warning = afdjWarning || mixed;
  const pill = $("#system-status");
  pill.classList.toggle("warning", warning);
  pill.innerHTML = `<span class="status-dot"></span>${mixed ? t("mixedUpdateStatus") : warning ? t("attention") : t("updated")}`;
  $("#stat-latest-observation").textContent = formatDate(latestGlobalObservation(), true);
  $("#stat-last-capture").textContent = formatDate(latestGlobalCapture(), true);
  $("#stat-last-run").textContent = international.status.generated_from_capture_utc ? formatDate(international.status.generated_from_capture_utc, true) : t("unavailable");
  $("#stat-sources-updated").textContent = `${formatNumber(current)} / ${formatNumber(sources.length)}`;
  $("#stat-stale-sources").textContent = formatNumber(stale);
  $("#stat-manual-sources").textContent = formatNumber(manual);
  $("#stat-unavailable-sources").textContent = formatNumber(unavailable);
  const footerVersion = $("#footer-contract-version"); if (footerVersion) footerVersion.textContent = international.status.contract_version || t("unavailable");
}

function overviewTrendBucket(properties) {
  const variation = properties.variation_cm_24h;
  if (variation === null || variation === undefined || variation === "") return "none";
  const number = Number(variation);
  if (Number.isNaN(number)) return "none";
  if (number > 0) return "up";
  if (number < 0) return "down";
  return "still";
}

function renderOverview() {
  const international = state.international;
  const counts = { up: 0, down: 0, still: 0, none: 0 };
  state.features.forEach(feature => { counts[overviewTrendBucket(feature.properties)]++; });
  const monitoredLocations = state.features.length;
  const dataStreams = Number(state.status.station_count) + Number(international.status.station_count);
  const countries = new Set(["RO", ...international.stations.map(station => station.country_code)]).size;
  const currentObservationStations = Number(state.status.station_count) + Number(international.status.current_station_count);
  const values = [
    ["monitoredLocations", monitoredLocations, ""], ["dataStreams", dataStreams, ""], ["countries", countries, ""], ["currentObservationStations", currentObservationStations, ""],
    ["rising", counts.up, "rising"], ["falling", counts.down, "falling"], ["stationary", counts.still, "stationary"], ["noTrendAvailable", counts.none, "warning"],
  ];
  $("#overview-metrics").innerHTML = values.map(([key, value, modifier]) => `<article class="metric-card${modifier ? ` ${modifier}` : ""}"><span>${t(key)}</span><strong>${formatNumber(value)}</strong></article>`).join("");
}
function renderStationOptions() {
  const select = $("#station-select");
  const selected = state.selectedId || select.value;
  select.innerHTML = "";
  [...state.stations.values()].sort((a, b) => (a.river_km ?? Number.POSITIVE_INFINITY) - (b.river_km ?? Number.POSITIVE_INFINITY) || a.display_name.localeCompare(b.display_name, getLocale())).forEach(station => {
    const option = document.createElement("option"); option.value = station.station_id;
    option.textContent = `${station.display_name} · ${countryName(station.country_code)}${station.river_km == null ? "" : ` · km ${formatNumber(station.river_km)}`}`;
    select.append(option);
  });
  if (selected && state.stations.has(selected)) select.value = selected;
}

function setupStations(geojson) {
  state.features = geojson.features;
  state.stations.clear();
  geojson.features.forEach(feature => {
    const station = { ...feature.properties, latitude: feature.geometry.coordinates[1], longitude: feature.geometry.coordinates[0] };
    state.stations.set(station.station_id, station);
  });
  renderStationOptions(); renderTable(); renderComparePicker();
}

async function getStationData(station) {
  if (!state.stationData.has(station.station_id)) {
    state.stationData.set(station.station_id, loadStation(station.slug).catch(error => { state.stationData.delete(station.station_id); throw error; }));
  }
  return state.stationData.get(station.station_id);
}

function deriveRange(observations) {
  if (!observations.length || state.rangePreset === "all") return { from: "", to: "" };
  const to = observations.at(-1).measurement_date;
  const days = RANGE_DAYS[state.rangePreset];
  if (!days) return state.range;
  const fromDate = new Date(`${to}T12:00:00`); fromDate.setDate(fromDate.getDate() - (days - 1));
  return { from: fromDate.toISOString().slice(0, 10), to };
}

function updateRangeUi() {
  $$("[data-range]").forEach(button => button.classList.toggle("active", button.dataset.range === state.rangePreset));
  $("#date-from").value = state.range.from || ""; $("#date-to").value = state.range.to || "";
}

function updateQuery() {
  const station = selectedStation(); if (!station) return;
  const params = new URLSearchParams(location.search);
  params.set("station", station.slug); params.set("range", state.rangePreset || "custom"); params.set("chart", state.activeTab);
  if (state.selectedDate) params.set("date", state.selectedDate); else params.delete("date");
  history.replaceState(null, "", `${location.pathname}?${params.toString()}${location.hash}`);
}

async function selectStation(stationId, options = {}) {
  const station = state.stations.get(stationId); if (!station) return;
  const isStationChange = state.selectedId !== stationId;
  if ("date" in options) state.selectedDate = options.date || null;
  else if (isStationChange) state.selectedDate = null;
  if (isStationChange && state.rangePreset === "custom") state.rangePreset = "30d";
  state.selectedId = stationId; $("#station-select").value = stationId;
  selectMapStation(stationId, { pan: options.pan !== false, openPopup: options.openPopup === true });
  $("#station-title").textContent = station.display_name;
  const context = [countryName(station.country_code), station.source_label || station.source_name, station.river_km == null ? null : `km ${formatNumber(station.river_km)}`].filter(Boolean);
  $("#station-context").textContent = context.join(" · ");
  $("#station-level").textContent = valueWithUnit(station.level_cm, "cm");
  const variation = station.variation_cm_24h == null ? null : Number(station.variation_cm_24h);
  $("#station-variation").textContent = variation == null ? t("unavailable") : `${variation > 0 ? "+" : ""}${formatNumber(variation)} cm`;
  $("#station-temperature").textContent = valueWithUnit(station.water_temperature_c, "°C", 1);
  $("#station-forecast-date").textContent = t("loadingEllipsis");
  try {
    const data = await getStationData(station);
    const issues = [...new Set(data.forecasts.map(row => row.forecast_issue_datetime).filter(Boolean))].sort();
    $("#station-forecast-date").textContent = issues.length ? formatDate(issues.at(-1), true) : t("unavailable");
    state.range = deriveRange(data.observations); updateRangeUi();
    const stationWarnings = data.forecasts.filter(row => !["valid"].includes(row.quality_flag));
    const qualityIssues = state.international?.qualityIssues.filter(issue => (issue.station_id || issue.record_id) === station.station_id) || [];
    const banner = $("#quality-banner");
    if (qualityIssues.length) {
      banner.hidden = false;
      banner.textContent = [...new Set(qualityIssues.map(issue => issueLabel(issue.code)))].join(" · ");
    } else if (station.scope === "international" && station.source_status !== "complete") {
      banner.hidden = false; banner.textContent = `${t("sourceStatus")}: ${statusLabel(station.source_status)}.`;
    } else if (stationWarnings.length) {
      const ambiguous = stationWarnings.filter(row => row.quality_flag.includes("zero") || row.quality_flag.includes("missing_forecast")).length;
      const mismatch = stationWarnings.filter(row => row.quality_flag.includes("mismatch")).length;
      banner.hidden = false; banner.textContent = `${t("warnings")}: ${ambiguous + mismatch}`;
    } else banner.hidden = true;
    populateIssueSelector(issues); await renderActiveChart();
    if (state.compareIds.includes(stationId)) await renderCompare();
    renderTable(); updateQuery();
  } catch (error) {
    $("#station-forecast-date").textContent = t("unavailable");
    $("#quality-banner").hidden = false; $("#quality-banner").textContent = t("stationDataUnavailable");
    console.error(error); toast(t("stationLoadError"));
  }
}

function populateIssueSelector(issues) {
  const select = $("#forecast-issue-select"); const old = select.value;
  select.innerHTML = "";
  [...issues].reverse().forEach(issue => { const option = document.createElement("option"); option.value = issue; option.textContent = formatDate(issue, true); select.append(option); });
  select.value = issues.includes(old) ? old : issues.at(-1) || "";
}

async function renderActiveChart() {
  const station = selectedStation(); if (!station) return;
  const data = await getStationData(station);
  if (state.activeTab === "level") await renderLevel("chart-level", station, data.observations, data.forecasts, state.range, state.selectedDate);
  if (state.activeTab === "variation") await renderVariation("chart-variation", station, data.observations, state.range);
  if (state.activeTab === "temperature") await renderTemperature("chart-temperature", station, data.observations, state.range);
  if (state.activeTab === "history") await renderHistory("chart-history", station, data.observations, data.forecasts, $("#forecast-issue-select").value);
  if (state.activeTab === "scores") { renderScoreSummary(data.scores); await renderScores("chart-scores", station, data.scores); }
}

function renderScoreSummary(scores) {
  const paired = scores.filter(row => Number(row.n_pairs) > 0);
  const total = paired.reduce((sum, row) => sum + Number(row.n_pairs), 0);
  const average = field => paired.length ? paired.reduce((sum, row) => sum + Number(row[field] || 0), 0) / paired.length : null;
  const maturity = total < 10 ? t("maturityInsufficient") : total < 30 ? t("maturityPreliminary") : t("maturityConsolidated");
  $("#score-summary").innerHTML = [
    [t("pairs"), total], [t("averageMae"), average("mae_cm") == null ? "—" : `${formatNumber(average("mae_cm"), 1)} cm`],
    [t("averageRmse"), average("rmse_cm") == null ? "—" : `${formatNumber(average("rmse_cm"), 1)} cm`], [t("maturity"), maturity]
  ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join("");
}

async function changeTab(tab) {
  state.activeTab = tab;
  $$("[role=tab]").forEach(button => button.setAttribute("aria-selected", String(button.dataset.tab === tab)));
  $$(".chart-tab").forEach(panel => { panel.hidden = panel.id !== `panel-${tab}`; });
  await renderActiveChart(); updateQuery(); setTimeout(() => resizeChart(chartIds[tab]), 20);
}

function filteredTableFeatures() {
  const query = $("#table-search").value.trim().toLocaleLowerCase(getLocale()); const filter = $("#table-filter").value;
  return state.features.filter(feature => {
    const p = feature.properties; const rowTrend = trend(p.variation_cm_24h);
    return state.filterPredicate(p) && (!query || `${p.display_name} ${p.station_name_local || ""}`.toLocaleLowerCase(getLocale()).includes(query)) && (filter === "all" || rowTrend.key === filter);
  });
}

function groupedTableFeatures() {
  const byCountry = new Map();
  filteredTableFeatures().forEach(feature => {
    const cc = feature.properties.country_code;
    if (!byCountry.has(cc)) byCountry.set(cc, []);
    byCountry.get(cc).push({ ...feature.properties, latitude: feature.geometry.coordinates[1], longitude: feature.geometry.coordinates[0] });
  });
  const knownFirst = COUNTRY_ORDER.filter(cc => byCountry.has(cc));
  const rest = [...byCountry.keys()].filter(cc => !COUNTRY_ORDER.includes(cc)).sort();
  return [...knownFirst, ...rest].map(countryCode => ({
    countryCode, stations: orderWithinCountry(countryCode, byCountry.get(countryCode)),
    approximateOrder: !byCountry.get(countryCode).every(row => row.river_km != null),
  }));
}

function renderTable() {
  const container = $("#stations-accordion"); container.innerHTML = "";
  const query = $("#table-search").value.trim();
  const selectedCountry = selectedStation()?.country_code;
  const cell = (value, unit = "", digits = 0) => value === null || value === undefined || value === "" ? `<span aria-label="${t("unavailable")}">—</span>` : `${formatNumber(value, digits)}${unit ? ` ${unit}` : ""}`;
  const groups = groupedTableFeatures();
  if (!groups.length) { container.innerHTML = `<p class="empty-state">${t("noFilteredStations")}</p>`; return; }
  groups.forEach(({ countryCode, stations, approximateOrder }) => {
    const details = document.createElement("details"); details.className = "country-group"; details.open = Boolean(query) || countryCode === selectedCountry;
    const streamTotal = stations.reduce((sum, p) => sum + Math.max(1, Number(p.stream_count) || 1), 0);
    const summaryText = countryCode === "RO" ? t("countryStationsCount", { count: formatNumber(stations.length) })
      : t("countryLocationsStreamsCount", { locations: formatNumber(stations.length), streams: formatNumber(streamTotal) });
    const summary = document.createElement("summary"); summary.innerHTML = `<strong>${countryName(countryCode)}</strong> · ${summaryText}`;
    details.append(summary);
    if (approximateOrder) { const note = document.createElement("p"); note.className = "approximate-order-note"; note.textContent = t("approximateOrderNote"); details.append(note); }
    const table = document.createElement("table"); table.className = "country-station-table";
    table.innerHTML = `<thead><tr><th data-i18n="station">${t("station")}</th><th data-i18n="kilometre">${t("kilometre")}</th><th data-i18n="level">${t("level")}</th><th data-i18n="variation">${t("variation")}</th><th data-i18n="observationDate">${t("observationDate")}</th><th data-i18n="trend">${t("trend")}</th><th data-i18n="freshnessStatus">${t("freshnessStatus")}</th></tr></thead>`;
    const tbody = document.createElement("tbody");
    stations.forEach(p => {
      const rowTrend = trend(p.variation_cm_24h);
      const freshness = countryCode === "RO" ? { key: "current", label: t("current") } : stationFreshness(p);
      const variation = p.variation_cm_24h == null ? null : Number(p.variation_cm_24h);
      const localName = p.station_name_local && p.station_name_local !== p.display_name ? `<small>${p.station_name_local}</small>` : "";
      const badges = streamBadges(p).map(key => `<span class="stream-chip">${t(key)}</span>`).join("");
      const row = document.createElement("tr"); row.tabIndex = 0; row.dataset.stationId = p.station_id;
      row.innerHTML = `<td><strong>${p.display_name}</strong>${localName}${badges ? `<span class="stream-chips">${badges}</span>` : ""}</td><td>${p.river_km == null ? "—" : cell(p.river_km)}</td><td>${cell(p.level_cm, "cm")}</td><td>${variation == null ? "—" : `${variation > 0 ? "+" : ""}${formatNumber(variation)} cm`}</td><td>${formatDate(p.measurement_datetime)}</td><td><span class="trend-badge ${rowTrend.key}">${rowTrend.symbol}</span> ${rowTrend.label}</td><td><span class="quality-chip ${freshness.key}">${freshness.label}</span></td>`;
      row.addEventListener("click", () => { selectStation(p.station_id); scrollToAnalysis(); });
      row.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); row.click(); } });
      if (p.station_id === state.selectedId) row.setAttribute("aria-current", "true");
      tbody.append(row);
    });
    table.append(tbody);
    const scroll = document.createElement("div"); scroll.className = "country-table-scroll"; scroll.append(table);
    details.append(scroll); container.append(details);
  });
}

function scrollToAnalysis() {
  const panel = $(".analysis-panel"); if (!panel) return;
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  panel.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  const heading = $("#station-title");
  if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus({ preventScroll: true }); }
}

function renderComparePicker() {
  const picker = $("#compare-picker"); picker.innerHTML = "";
  [...state.stations.values()].sort((a, b) => (a.river_km ?? Number.POSITIVE_INFINITY) - (b.river_km ?? Number.POSITIVE_INFINITY)).forEach(station => {
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" value="${station.station_id}" ${state.compareIds.includes(station.station_id) ? "checked" : ""}> ${station.display_name}`;
    label.querySelector("input").addEventListener("change", async event => {
      if (event.target.checked && state.compareIds.length >= 4) { event.target.checked = false; toast(t("compareMaximumFour")); return; }
      state.compareIds = event.target.checked ? [...state.compareIds, station.station_id] : state.compareIds.filter(id => id !== station.station_id);
      await renderCompare();
    }); picker.append(label);
  });
}

async function renderCompare() {
  const series = [];
  for (const id of state.compareIds) { const station = state.stations.get(id); const data = await getStationData(station); series.push({ station, observations: data.observations }); }
  $("#compare-selection").textContent = series.length ? series.map(item => item.station.display_name).join(" · ") : t("noStationSelected");
  await renderComparison("chart-compare", series, state.compareMode, state.range);
}

function downloadTableCsv(scope = "filtered") {
  const rows = (scope === "all" ? state.features : filteredTableFeatures()).map(feature => feature.properties);
  const fields = ["display_name", "country_code", "river_km", "level_cm", "variation_cm_24h", "measurement_datetime"];
  const escape = value => /[",\n]/.test(String(value)) ? `"${String(value).replaceAll('"', '""')}"` : value;
  const content = "\ufeff" + [fields.join(","), ...rows.map(row => fields.map(field => escape(row[field] ?? "")).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a"); link.href = url;
  const dateStamp = new Date().toISOString().slice(0, 10);
  link.download = `nivel_dunare_statii_${scope === "all" ? "toate" : "filtrate"}_${dateStamp}.csv`;
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const ADVANCED_FILTER_IDS = ["source-filter", "trend-filter", "access-filter", "status-filter", "automation-filter", "quality-filter", "type-filter", "stream-filter", "coordinate-filter"];
function updateActiveFilterCount() {
  const active = ADVANCED_FILTER_IDS.filter(id => document.getElementById(id)?.value && document.getElementById(id).value !== "all").length;
  const badge = $("#active-filters-count");
  if (badge) badge.textContent = active > 0 ? t("activeFiltersCount", { count: formatNumber(active) }) : "";
}

function toggleFullscreen(element, chartId) {
  const active = element.classList.toggle("is-fullscreen"); document.body.style.overflow = active ? "hidden" : "";
  const button = element.querySelector("[data-action=expand], [data-compare-action=expand]"); if (button) button.textContent = active ? t("closeAction") : t("expand");
  setTimeout(() => resizeChart(chartId), 100);
}

function localizedDownloadLabel(item) {
  const fixed = {
    "latest.csv": "downloadCurrentSituation",
    "observations.csv": "downloadAllObservations",
    "forecasts.csv": "downloadAllForecasts",
    "stations.csv": "downloadStationRegistry",
    "latest.geojson": "downloadGeospatialSituation",
  }[item.path];
  if (fixed) return t(fixed);
  if (item.path.startsWith("station/")) return `${item.label.split(" — ")[0]} — ${t("combinedHistory")}`;
  if (item.path.startsWith("international/")) return `${t("internationalBetaDownload")} · ${item.path.split("/").at(-1)}`;
  return item.label;
}

function renderDownloads() {
  $("#download-list").innerHTML = downloadEntries.map(item => `<a href="${dataUrl(item.path)}" download><span>${localizedDownloadLabel(item)}</span><small>${item.format}</small></a>`).join("");
}
function bindEvents(downloads) {
  $("#station-select").addEventListener("change", event => { selectStation(event.target.value); scrollToAnalysis(); });
  $("#map-reset").addEventListener("click", resetMap);
  $("#map-fullscreen").addEventListener("click", () => { const panel = $(".map-panel"); panel.classList.toggle("is-fullscreen"); document.body.style.overflow = panel.classList.contains("is-fullscreen") ? "hidden" : ""; refreshMapSize(); });
  $("#station-search").addEventListener("keydown", event => { if (event.key === "Enter") { const marker = findStation(event.target.value); if (marker) { selectStation(marker.properties.station_id, { openPopup: true }); scrollToAnalysis(); } else toast(t("stationNotFound")); } });
  $$("[data-range]").forEach(button => button.addEventListener("click", async () => { state.rangePreset = button.dataset.range; const data = await getStationData(selectedStation()); state.range = deriveRange(data.observations); updateRangeUi(); await renderActiveChart(); await renderCompare(); updateQuery(); }));
  [$("#date-from"), $("#date-to")].forEach(input => input.addEventListener("change", async () => { state.rangePreset = "custom"; state.range = { from: $("#date-from").value, to: $("#date-to").value }; updateRangeUi(); await renderActiveChart(); await renderCompare(); updateQuery(); }));
  $("#range-reset").addEventListener("click", async () => { state.rangePreset = "all"; state.range = {}; updateRangeUi(); await renderActiveChart(); await renderCompare(); updateQuery(); });
  $$("[role=tab]").forEach(button => button.addEventListener("click", () => changeTab(button.dataset.tab)));
  $(".tabs").addEventListener("keydown", event => { if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return; const tabs = $$("[role=tab]"); const index = tabs.indexOf(document.activeElement); const next = tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length]; next.focus(); next.click(); });
  $("#forecast-issue-select").addEventListener("change", () => renderActiveChart());
  $$(".chart-tab").forEach(panel => panel.addEventListener("click", async event => { const action = event.target.dataset.action; const id = panel.querySelector(".chart")?.id; if (!action || !id) return; if (action === "csv") downloadChartCsv(id); if (action === "png") downloadChartPng(id); if (action === "expand") toggleFullscreen(panel, id); if (action === "goto-latest") { state.selectedDate = null; await renderActiveChart(); updateQuery(); } }));
  $("#compare-add").addEventListener("click", () => { $("#compare-picker").hidden = !$("#compare-picker").hidden; });
  $("#compare-mode").addEventListener("change", async event => { state.compareMode = event.target.value; await renderCompare(); });
  $(".comparison-section").addEventListener("click", event => { const action = event.target.dataset.compareAction; if (action === "csv") downloadChartCsv("chart-compare"); if (action === "png") downloadChartPng("chart-compare"); if (action === "expand") toggleFullscreen($(".comparison-section"), "chart-compare"); });
  $("#table-search").addEventListener("input", renderTable); $("#table-filter").addEventListener("change", renderTable);
  $("#table-csv").addEventListener("click", () => downloadTableCsv("filtered")); $("#table-csv-all").addEventListener("click", () => downloadTableCsv("all"));
  $("#advanced-filters-toggle").addEventListener("click", () => { const panel = $("#advanced-filters"); panel.hidden = !panel.hidden; $("#advanced-filters-toggle").setAttribute("aria-expanded", String(!panel.hidden)); });
  $("#filters-reset").addEventListener("click", () => { $$(".international-filters select").forEach(select => { select.value = "all"; select.dispatchEvent(new Event("change")); }); });
  $$(".international-filters select").forEach(select => select.addEventListener("change", updateActiveFilterCount));
  $("#info-button").addEventListener("click", () => $("#info-dialog").showModal());
  $("#footer-methodology-link")?.addEventListener("click", () => $("#info-dialog").showModal());
  $("#language-button").addEventListener("click", toggleLanguage);
  $("#downloads-button").addEventListener("click", () => $("#downloads-dialog").showModal());
  $$('[data-close-dialog]').forEach(button => button.addEventListener("click", () => document.getElementById(button.dataset.closeDialog).close()));
  const internationalDownloads = ["stations.json", "streams.json", "observations.json", "latest.json", "forecasts.json", "sources.json", "status.json", "stations.geojson", "unmapped_stations.json", "quality_issues.json"].map(name => ({ path: `international/${name}`, label: name, format: name.endsWith("geojson") ? "GeoJSON" : "JSON" }));
  downloadEntries = [...downloads, ...internationalDownloads]; renderDownloads();
  document.addEventListener("keydown", event => { if (event.key !== "Escape") return; const expanded = $(".is-fullscreen"); if (expanded) { const chart = expanded.querySelector(".chart")?.id; expanded.classList.remove("is-fullscreen"); document.body.style.overflow = ""; if (chart) resizeChart(chart); refreshMapSize(); } });
  window.addEventListener("resize", debounce(() => { refreshMapSize(); Object.values(chartIds).forEach(resizeChart); resizeChart("chart-compare"); }, 120));
}

function debounce(fn, wait) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); }; }

function refreshPopoverLabels() {
  $$(".info-trigger").forEach(trigger => {
    const label = trigger.closest(".update-item")?.querySelector(".update-item-label")?.textContent || (trigger.closest(".update-item-status") ? t("updateStatusTitle") : "");
    trigger.setAttribute("aria-label", label ? `${label} — ${t("moreInfo")}` : t("moreInfo"));
  });
}

function initPopovers() {
  let openPopover = null; let openTrigger = null;
  function hide() {
    if (!openPopover) return;
    openPopover.hidden = true; openTrigger.setAttribute("aria-expanded", "false");
    openPopover = null; openTrigger = null;
  }
  function show(trigger, popover) {
    if (openPopover && openPopover !== popover) hide();
    popover.hidden = false; trigger.setAttribute("aria-expanded", "true");
    openPopover = popover; openTrigger = trigger;
  }
  $$(".info-trigger").forEach(trigger => {
    const popover = document.getElementById(trigger.dataset.popoverTarget); if (!popover) return;
    trigger.setAttribute("aria-describedby", popover.id);
    trigger.addEventListener("mouseenter", () => show(trigger, popover));
    trigger.addEventListener("mouseleave", () => { if (document.activeElement !== trigger) hide(); });
    trigger.addEventListener("focus", () => show(trigger, popover));
    trigger.addEventListener("blur", () => hide());
    trigger.addEventListener("click", event => { event.stopPropagation(); if (openPopover === popover) hide(); else show(trigger, popover); });
  });
  document.addEventListener("click", event => { if (openPopover && !event.target.closest(".info-trigger") && !event.target.closest(".popover")) hide(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && openPopover) { const trigger = openTrigger; hide(); trigger?.focus(); } });
  refreshPopoverLabels();
}

async function start() {
  initLanguage();
  document.body.classList.add("loading");
  try {
    const { status, geojson, downloads, international } = await loadStartupData();
    state.international = international;
    applyStatus(status); setupStations(geojson); renderUpdateBar(); renderOverview(); initMap("map", geojson, id => { selectStation(id); scrollToAnalysis(); }); bindEvents(downloads);
    initBetaUi(international, predicate => { state.filterPredicate = predicate; filterMap(predicate); renderTable(); updateActiveFilterCount(); }, afdjSourceEntry(status));
    initPopovers(); updateActiveFilterCount();
    onLanguageChange(async () => {
      applyTranslations(); applyStatus(state.status); renderUpdateBar(); renderOverview(); refreshPopoverLabels(); refreshMapLanguage(); renderStationOptions(); renderTable(); renderComparePicker(); renderDownloads(); updateActiveFilterCount();
      if (state.selectedId) await selectStation(state.selectedId, { pan: false });
      await renderCompare();
    });
    const params = new URLSearchParams(location.search); const requestedSlug = params.get("station");
    const requested = [...state.stations.values()].find(station => station.slug === requestedSlug) || [...state.stations.values()].find(station => station.slug === "giurgiu") || [...state.stations.values()][0];
    const range = params.get("range"); if (["7d", "30d", "90d", "365d", "all"].includes(range)) state.rangePreset = range;
    const tab = params.get("chart"); if (chartIds[tab]) state.activeTab = tab;
    const requestedDateParam = params.get("date");
    const requestedDate = requestedDateParam && /^\d{4}-\d{2}-\d{2}$/.test(requestedDateParam) ? requestedDateParam : null;
    applyTranslations();
    await selectStation(requested.station_id, { pan: false, date: requestedDate });
    if (state.activeTab !== "level") await changeTab(state.activeTab);
  } catch (error) {
    console.error(error); $("#system-status").classList.add("warning"); $("#system-status").innerHTML = `<span class="status-dot"></span>${t("unavailable")}`;
    toast(t("unavailable"), 8000);
  } finally { document.body.classList.remove("loading"); }
}

start();
