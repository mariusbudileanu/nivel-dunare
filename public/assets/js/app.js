import { RANGE_DAYS, formatDate, formatNumber } from "./config.js";
import { dataUrl, loadStartupData, loadStation } from "./data.js";
import { findStation, initMap, refreshMapSize, resetMap, selectMapStation } from "./map.js";
import {
  downloadChartCsv, downloadChartPng, renderComparison, renderHistory,
  renderLevel, renderScores, renderTemperature, renderVariation, resizeChart
} from "./charts.js";

const state = {
  status: null, features: [], stations: new Map(), stationData: new Map(),
  selectedId: null, activeTab: "level", rangePreset: "30d", range: {},
  compareIds: [], compareMode: "delta", tableSort: { field: "river_km", direction: 1 }
};

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

function trend(value, quality = "valid") {
  if (quality !== "valid") return { key: "alert", symbol: "!", label: "atenționare" };
  const number = Number(value);
  if (number > 0) return { key: "up", symbol: "+", label: "creștere" };
  if (number < 0) return { key: "down", symbol: "−", label: "scădere" };
  return { key: "still", symbol: "0", label: "staționare" };
}

function selectedStation() { return state.stations.get(state.selectedId); }

function applyStatus(status) {
  state.status = status;
  $("#official-date").textContent = formatDate(status.latest_measurement_datetime, true);
  $("#capture-date").textContent = formatDate(status.last_capture_datetime_local, true);
  $("#metric-stations").textContent = status.station_count;
  $("#metric-rising").textContent = status.rising_count;
  $("#metric-falling").textContent = status.falling_count;
  $("#metric-stationary").textContent = status.stationary_count;
  $("#metric-warning").textContent = status.ambiguous_zero_count + status.xml_html_mismatch_count;
  const pill = $("#system-status");
  const warning = status.system_status !== "operational" || status.xml_html_mismatch_count > 0;
  pill.classList.toggle("warning", warning);
  pill.innerHTML = `<span class="status-dot"></span>${warning ? "Necesită atenție" : "Date actualizate"}`;
  $("#archive-start").textContent = formatDate(status.archive_start_date);
  $("#technical-status").textContent = JSON.stringify(status, null, 2);
  const archiveDays = Math.max(0, (new Date(status.latest_measurement_date) - new Date(status.archive_start_date)) / 86400000);
  if (archiveDays < 30 && !new URLSearchParams(location.search).has("range")) state.rangePreset = "all";
}

function setupStations(geojson) {
  state.features = geojson.features;
  const select = $("#station-select");
  select.innerHTML = "";
  [...geojson.features].sort((a, b) => a.properties.river_km - b.properties.river_km).forEach(feature => {
    const station = { ...feature.properties, latitude: feature.geometry.coordinates[1], longitude: feature.geometry.coordinates[0] };
    state.stations.set(station.station_id, station);
    const option = document.createElement("option"); option.value = station.station_id;
    option.textContent = `${station.display_name} · km ${formatNumber(station.river_km)}`;
    select.append(option);
  });
  renderTable(); renderComparePicker();
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
  history.replaceState(null, "", `${location.pathname}?${params.toString()}${location.hash}`);
}

async function selectStation(stationId, options = {}) {
  const station = state.stations.get(stationId); if (!station) return;
  state.selectedId = stationId; $("#station-select").value = stationId;
  selectMapStation(stationId, { pan: options.pan !== false, openPopup: options.openPopup === true });
  $("#station-title").textContent = station.display_name;
  $("#station-context").textContent = `Km ${formatNumber(station.river_km)} · ${station.source_name}`;
  $("#station-level").textContent = `${formatNumber(station.level_cm)} cm`;
  const variation = Number(station.variation_cm_24h); $("#station-variation").textContent = `${variation > 0 ? "+" : ""}${formatNumber(variation)} cm`;
  $("#station-temperature").textContent = `${formatNumber(station.water_temperature_c, 1)} °C`;
  $("#station-forecast-date").textContent = "Se încarcă…";
  try {
    const data = await getStationData(station);
    const issues = [...new Set(data.forecasts.map(row => row.forecast_issue_datetime))].sort();
    $("#station-forecast-date").textContent = formatDate(issues.at(-1), true);
    state.range = deriveRange(data.observations); updateRangeUi();
    const stationWarnings = data.forecasts.filter(row => !["valid"].includes(row.quality_flag));
    const banner = $("#quality-banner");
    if (stationWarnings.length) {
      const ambiguous = stationWarnings.filter(row => row.quality_flag.includes("zero") || row.quality_flag.includes("missing_forecast")).length;
      const mismatch = stationWarnings.filter(row => row.quality_flag.includes("mismatch")).length;
      banner.hidden = false; banner.textContent = `Validare prognoze: ${ambiguous} valori indisponibile/zero ambiguu și ${mismatch} nepotriviri XML–HTML. Valorile sunt marcate în arhivă.`;
    } else banner.hidden = true;
    populateIssueSelector(issues); await renderActiveChart();
    if (state.compareIds.includes(stationId)) await renderCompare();
    renderTable(); updateQuery();
  } catch (error) {
    $("#station-forecast-date").textContent = "Indisponibil";
    $("#quality-banner").hidden = false; $("#quality-banner").textContent = "Datele stației nu au putut fi încărcate. Reîncearcă sau consultă situația globală.";
    toast(error.message || "Eroare la încărcarea stației");
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
  if (state.activeTab === "level") await renderLevel("chart-level", station, data.observations, data.forecasts, state.range);
  if (state.activeTab === "variation") await renderVariation("chart-variation", station, data.observations, state.range);
  if (state.activeTab === "temperature") await renderTemperature("chart-temperature", station, data.observations, state.range);
  if (state.activeTab === "history") await renderHistory("chart-history", station, data.observations, data.forecasts, $("#forecast-issue-select").value);
  if (state.activeTab === "scores") { renderScoreSummary(data.scores); await renderScores("chart-scores", station, data.scores); }
}

function renderScoreSummary(scores) {
  const paired = scores.filter(row => Number(row.n_pairs) > 0);
  const total = paired.reduce((sum, row) => sum + Number(row.n_pairs), 0);
  const average = field => paired.length ? paired.reduce((sum, row) => sum + Number(row[field] || 0), 0) / paired.length : null;
  const maturity = total < 10 ? "Date insuficiente" : total < 30 ? "Rezultate preliminare" : "Rezultate consolidate";
  $("#score-summary").innerHTML = [
    ["Perechi", total], ["MAE mediu", average("mae_cm") == null ? "—" : `${formatNumber(average("mae_cm"), 1)} cm`],
    ["RMSE mediu", average("rmse_cm") == null ? "—" : `${formatNumber(average("rmse_cm"), 1)} cm`], ["Maturitate", maturity]
  ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join("");
}

async function changeTab(tab) {
  state.activeTab = tab;
  $$("[role=tab]").forEach(button => button.setAttribute("aria-selected", String(button.dataset.tab === tab)));
  $$(".chart-tab").forEach(panel => { panel.hidden = panel.id !== `panel-${tab}`; });
  await renderActiveChart(); updateQuery(); setTimeout(() => resizeChart(chartIds[tab]), 20);
}

function filteredTableFeatures() {
  const query = $("#table-search").value.trim().toLocaleLowerCase("ro-RO"); const filter = $("#table-filter").value;
  const rows = state.features.filter(feature => {
    const p = feature.properties; const t = trend(p.variation_cm_24h, p.quality_flag);
    return (!query || p.display_name.toLocaleLowerCase("ro-RO").includes(query)) && (filter === "all" || t.key === filter);
  });
  const { field, direction } = state.tableSort;
  return rows.sort((a, b) => {
    const av = a.properties[field], bv = b.properties[field];
    const numeric = ["river_km", "level_cm", "variation_cm_24h", "water_temperature_c"].includes(field);
    return direction * (numeric ? Number(av) - Number(bv) : String(av).localeCompare(String(bv), "ro"));
  });
}

function renderTable() {
  const tbody = $("#stations-table tbody"); tbody.innerHTML = "";
  filteredTableFeatures().forEach(feature => {
    const p = feature.properties; const t = trend(p.variation_cm_24h, p.quality_flag); const variation = Number(p.variation_cm_24h);
    const row = document.createElement("tr"); row.tabIndex = 0; row.dataset.stationId = p.station_id;
    row.innerHTML = `<td><strong>${p.display_name}</strong></td><td>${formatNumber(p.river_km)}</td><td>${formatNumber(p.level_cm)} cm</td><td><span class="trend-badge ${t.key}">${t.symbol}</span> ${variation > 0 ? "+" : ""}${formatNumber(variation)} cm</td><td>${formatNumber(p.water_temperature_c, 1)} °C</td><td>${formatDate(p.measurement_datetime)}</td><td><span class="quality-chip ${p.quality_flag === "valid" ? "" : "warning"}">${p.quality_flag === "valid" ? t.label : "atenționare"}</span></td>`;
    row.addEventListener("click", () => { selectStation(p.station_id); scrollToAnalysis(); });
    row.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); row.click(); } });
    if (p.station_id === state.selectedId) row.setAttribute("aria-current", "true");
    tbody.append(row);
  });
}

function scrollToAnalysis() { if (matchMedia("(max-width: 1180px)").matches) $(".analysis-panel").scrollIntoView({ behavior: "smooth", block: "start" }); }

function renderComparePicker() {
  const picker = $("#compare-picker"); picker.innerHTML = "";
  [...state.stations.values()].sort((a, b) => a.river_km - b.river_km).forEach(station => {
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" value="${station.station_id}" ${state.compareIds.includes(station.station_id) ? "checked" : ""}> ${station.display_name}`;
    label.querySelector("input").addEventListener("change", async event => {
      if (event.target.checked && state.compareIds.length >= 4) { event.target.checked = false; toast("Poți compara maximum 4 stații."); return; }
      state.compareIds = event.target.checked ? [...state.compareIds, station.station_id] : state.compareIds.filter(id => id !== station.station_id);
      await renderCompare();
    }); picker.append(label);
  });
}

async function renderCompare() {
  const series = [];
  for (const id of state.compareIds) { const station = state.stations.get(id); const data = await getStationData(station); series.push({ station, observations: data.observations }); }
  $("#compare-selection").textContent = series.length ? series.map(item => item.station.display_name).join(" · ") : "Nicio stație selectată";
  await renderComparison("chart-compare", series, state.compareMode, state.range);
}

function downloadTableCsv() {
  const rows = filteredTableFeatures().map(feature => feature.properties);
  const fields = ["display_name", "river_km", "level_cm", "variation_cm_24h", "water_temperature_c", "measurement_datetime", "quality_flag"];
  const escape = value => /[",\n]/.test(String(value)) ? `"${String(value).replaceAll('"', '""')}"` : value;
  const content = "\ufeff" + [fields.join(","), ...rows.map(row => fields.map(field => escape(row[field] ?? "")).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" })); const link = document.createElement("a"); link.href = url; link.download = "nivel_dunare_situatia_curenta_selectata.csv"; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function toggleFullscreen(element, chartId) {
  const active = element.classList.toggle("is-fullscreen"); document.body.style.overflow = active ? "hidden" : "";
  const button = element.querySelector("[data-action=expand], [data-compare-action=expand]"); if (button) button.textContent = active ? "Închide" : "Extinde";
  setTimeout(() => resizeChart(chartId), 100);
}

function bindEvents(downloads) {
  $("#station-select").addEventListener("change", event => selectStation(event.target.value));
  $("#map-reset").addEventListener("click", resetMap);
  $("#map-fullscreen").addEventListener("click", () => { const panel = $(".map-panel"); panel.classList.toggle("is-fullscreen"); document.body.style.overflow = panel.classList.contains("is-fullscreen") ? "hidden" : ""; refreshMapSize(); });
  $("#station-search").addEventListener("keydown", event => { if (event.key === "Enter") { const marker = findStation(event.target.value); if (marker) selectStation(marker.properties.station_id, { openPopup: true }); else toast("Stația nu a fost găsită."); } });
  $$("[data-range]").forEach(button => button.addEventListener("click", async () => { state.rangePreset = button.dataset.range; const data = await getStationData(selectedStation()); state.range = deriveRange(data.observations); updateRangeUi(); await renderActiveChart(); await renderCompare(); updateQuery(); }));
  [$("#date-from"), $("#date-to")].forEach(input => input.addEventListener("change", async () => { state.rangePreset = "custom"; state.range = { from: $("#date-from").value, to: $("#date-to").value }; updateRangeUi(); await renderActiveChart(); await renderCompare(); updateQuery(); }));
  $("#range-reset").addEventListener("click", async () => { state.rangePreset = "all"; state.range = {}; updateRangeUi(); await renderActiveChart(); await renderCompare(); updateQuery(); });
  $$("[role=tab]").forEach(button => button.addEventListener("click", () => changeTab(button.dataset.tab)));
  $(".tabs").addEventListener("keydown", event => { if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return; const tabs = $$("[role=tab]"); const index = tabs.indexOf(document.activeElement); const next = tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length]; next.focus(); next.click(); });
  $("#forecast-issue-select").addEventListener("change", () => renderActiveChart());
  $$(".chart-tab").forEach(panel => panel.addEventListener("click", event => { const action = event.target.dataset.action; const id = panel.querySelector(".chart")?.id; if (!action || !id) return; if (action === "csv") downloadChartCsv(id); if (action === "png") downloadChartPng(id); if (action === "expand") toggleFullscreen(panel, id); }));
  $("#compare-add").addEventListener("click", () => { $("#compare-picker").hidden = !$("#compare-picker").hidden; });
  $("#compare-mode").addEventListener("change", async event => { state.compareMode = event.target.value; await renderCompare(); });
  $(".comparison-section").addEventListener("click", event => { const action = event.target.dataset.compareAction; if (action === "csv") downloadChartCsv("chart-compare"); if (action === "png") downloadChartPng("chart-compare"); if (action === "expand") toggleFullscreen($(".comparison-section"), "chart-compare"); });
  $("#table-search").addEventListener("input", renderTable); $("#table-filter").addEventListener("change", renderTable); $("#table-csv").addEventListener("click", downloadTableCsv);
  $$("#stations-table th[data-sort]").forEach(header => header.addEventListener("click", () => { const field = header.dataset.sort; state.tableSort.direction = state.tableSort.field === field ? -state.tableSort.direction : 1; state.tableSort.field = field; renderTable(); }));
  $("#info-button").addEventListener("click", () => $("#info-dialog").showModal());
  $("#downloads-button").addEventListener("click", () => $("#downloads-dialog").showModal());
  $$('[data-close-dialog]').forEach(button => button.addEventListener("click", () => document.getElementById(button.dataset.closeDialog).close()));
  $("#download-list").innerHTML = downloads.map(item => `<a href="${dataUrl(item.path)}" download><span>${item.label}</span><small>${item.format}</small></a>`).join("");
  document.addEventListener("keydown", event => { if (event.key !== "Escape") return; const expanded = $(".is-fullscreen"); if (expanded) { const chart = expanded.querySelector(".chart")?.id; expanded.classList.remove("is-fullscreen"); document.body.style.overflow = ""; if (chart) resizeChart(chart); refreshMapSize(); } });
  window.addEventListener("resize", debounce(() => { refreshMapSize(); Object.values(chartIds).forEach(resizeChart); resizeChart("chart-compare"); }, 120));
}

function debounce(fn, wait) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); }; }

async function start() {
  document.body.classList.add("loading");
  try {
    const { status, geojson, downloads } = await loadStartupData();
    applyStatus(status); setupStations(geojson); initMap("map", geojson, id => selectStation(id)); bindEvents(downloads);
    const params = new URLSearchParams(location.search); const requestedSlug = params.get("station");
    const requested = [...state.stations.values()].find(station => station.slug === requestedSlug) || [...state.stations.values()].find(station => station.slug === "giurgiu") || [...state.stations.values()][0];
    const range = params.get("range"); if (["7d", "30d", "90d", "365d", "all"].includes(range)) state.rangePreset = range;
    const tab = params.get("chart"); if (chartIds[tab]) state.activeTab = tab;
    await selectStation(requested.station_id, { pan: false });
    if (state.activeTab !== "level") await changeTab(state.activeTab);
  } catch (error) {
    console.error(error); $("#system-status").classList.add("warning"); $("#system-status").innerHTML = '<span class="status-dot"></span>Date indisponibile';
    toast("Aplicația nu a putut încărca datele publice. Încearcă din nou mai târziu.", 8000);
  } finally { document.body.classList.remove("loading"); }
}

start();
