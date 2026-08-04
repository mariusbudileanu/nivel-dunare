import { formatDate, formatNumber } from "./config.js";
import { applyTranslations, countryName, issueLabel, onLanguageChange, qualityLabel, stationTypeLabel, statusLabel, t } from "./i18n.js";

const filters = { country: "all", source: "all", status: "all", type: "all" };
let data;
let notify = () => {};
let qualityByStation = new Map();

function displayStatus(station) {
  return station.source_status === "suspended" && station.country_code === "HR" ? "stale" : station.source_status;
}

function buildQualityIndex() {
  qualityByStation = new Map(data.stations.map(station => [station.station_id, new Set()]));
  for (const row of data.latest) qualityByStation.get(row.station_id)?.add(row.canonical_quality_flag || "unavailable");
  for (const issue of data.qualityIssues) {
    if (issue.code !== "outside_plausible_water_temperature_range") continue;
    const stationId = issue.station_id || issue.record_id;
    if (!qualityByStation.has(stationId)) qualityByStation.set(stationId, new Set());
    qualityByStation.get(stationId).add("suspect");
  }
  for (const qualities of qualityByStation.values()) if (!qualities.size) qualities.add("unavailable");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

function statusIcon(status) { return { complete: "✓", partial: "◐", provisional: "◇", suspect: "!", stale: "◷", suspended: "⏸", unavailable: "—" }[status] || "—"; }

function option(value, label, selected) { return `<option value="${escapeHtml(value)}"${selected === value ? " selected" : ""}>${escapeHtml(label)}</option>`; }

function renderFilters() {
  const country = document.querySelector("#country-filter");
  const source = document.querySelector("#source-filter");
  const status = document.querySelector("#status-filter");
  const type = document.querySelector("#type-filter");
  country.innerHTML = option("all", t("allCountries"), filters.country) + ["RO", "DE", "AT", "SK", "HU", "HR", "BG", "RS"].map(code => option(code, countryName(code), filters.country)).join("");
  source.innerHTML = option("all", t("allSources"), filters.source) + [{ source_id: "afdj_ro", label: "AFDJ" }, ...data.sources].map(item => option(item.source_id, item.label, filters.source)).join("");
  status.innerHTML = option("all", t("allStatuses"), filters.status) + ["complete", "partial", "provisional", "suspect", "stale", "suspended", "unavailable"].map(value => option(value, `${statusIcon(value)} ${statusLabel(value)}`, filters.status)).join("");
  const types = [...new Set(data.stations.map(station => station.station_type))].sort();
  type.innerHTML = option("all", t("allTypes"), filters.type) + types.map(value => option(value, stationTypeLabel(value), filters.type)).join("");
}

function renderMetrics() {
  const values = [
    ["totalRegistry", data.status.station_count], ["mappedStations", data.status.mapped_station_count],
    ["unmappedStations", data.status.unmapped_station_count], ["currentStations", data.status.current_station_count],
    ["completeSources", data.status.complete_source_count], ["partialSources", data.status.partial_source_count],
    ["staleStations", data.status.stale_station_count], ["suspendedStations", data.status.suspended_station_count],
    ["suspectValues", data.status.suspect_current_observation_count],
  ];
  document.querySelector("#international-metrics").innerHTML = values.map(([key, value]) => `<div><span>${escapeHtml(t(key))}</span><strong>${formatNumber(value)}</strong></div>`).join("");
}

function latestByStation() {
  const grouped = new Map();
  for (const row of data.latest) {
    if (!grouped.has(row.station_id)) grouped.set(row.station_id, {});
    grouped.get(row.station_id)[row.parameter] = row;
  }
  return grouped;
}

function valueLine(label, row) {
  if (!row) return "";
  return `<span><b>${escapeHtml(label)}:</b> ${formatNumber(row.value, row.parameter === "water_temperature" ? 1 : 0)} ${escapeHtml(row.unit)}</span>`;
}

function renderUnmapped() {
  const latest = latestByStation();
  const rows = data.unmapped.filter(matchesFilters);
  document.querySelector("#unmapped-count").textContent = formatNumber(rows.length);
  const container = document.querySelector("#unmapped-list");
  if (!rows.length) { container.innerHTML = `<p class="empty-state">${escapeHtml(t("noFilteredStations"))}</p>`; return; }
  container.innerHTML = rows.map(station => {
    const values = latest.get(station.station_id) || {};
    const local = station.station_name_local && station.station_name_local !== station.station_name ? `<p class="local-name">${escapeHtml(station.station_name_local)}</p>` : "";
    const dateRow = values.water_level || values.discharge || values.water_temperature;
    const dateValue = dateRow?.measurement_datetime_local || dateRow?.measurement_datetime_utc || dateRow?.measurement_date;
    let timeDetails = "";
    if (dateRow?.measurement_date && !dateRow?.measurement_datetime_local && !dateRow?.measurement_datetime_utc) {
      timeDetails = `<p><b>${escapeHtml(t("date"))}:</b> ${escapeHtml(formatDate(dateRow.measurement_date))}</p>`;
    } else if (dateValue) {
      const zone = dateRow?.measurement_timezone || "";
      const localValue = dateRow?.measurement_datetime_local || dateRow?.measurement_time_original;
      if (localValue) timeDetails += `<p><b>${escapeHtml(t("sourceTime"))}:</b> ${escapeHtml(formatDate(localValue, true, zone))}${zone ? ` (${escapeHtml(zone)})` : ""}</p>`;
      if (dateRow?.measurement_datetime_utc) timeDetails += `<p><b>${escapeHtml(t("utcTime"))}:</b> ${escapeHtml(formatDate(dateRow.measurement_datetime_utc, true, "UTC"))} UTC</p>`;
    }
    const sourceStatus = displayStatus(station);
    const stationIssues = data.qualityIssues.filter(issue => (issue.station_id || issue.record_id) === station.station_id);
    const issueCodes = [...new Set(stationIssues.map(issue => issue.code))];
    const quality = dateRow?.canonical_quality_flag;
    const forecastCount = (data.forecastsByStation.get(station.station_id) || []).length;
    return `<article class="unmapped-card" data-country="${station.country_code}" data-status="${sourceStatus}" data-quality="${qualityByStation.get(station.station_id)?.has("suspect") ? "suspect" : escapeHtml(quality || "unavailable")}">
      <div class="unmapped-card-head"><div><h3>${escapeHtml(station.station_name)}</h3>${local}<p>${escapeHtml(countryName(station.country_code))} · ${escapeHtml(station.source_label)}</p><p>${escapeHtml(stationTypeLabel(station.station_type))}</p></div><span class="status-tag ${escapeHtml(sourceStatus)}">${statusIcon(sourceStatus)} ${escapeHtml(statusLabel(sourceStatus))}</span></div>
      <div class="unmapped-values">${valueLine(t("waterLevel"), values.water_level)}${valueLine(t("discharge"), values.discharge)}${valueLine(t("waterTemperature"), values.water_temperature)}</div>
      ${forecastCount ? `<p><b>${escapeHtml(t("availableForecasts"))}:</b> ${formatNumber(forecastCount)}</p>` : ""}
      ${quality ? `<p><b>${escapeHtml(t("observationQuality"))}:</b> <span class="status-tag ${escapeHtml(quality)}">${escapeHtml(qualityLabel(quality))}</span></p>` : ""}
      ${timeDetails}
      ${station.capture_datetime_utc ? `<p><b>${escapeHtml(t("captureTime"))}:</b> ${escapeHtml(formatDate(station.capture_datetime_utc, true, "UTC"))} UTC</p>` : ""}
      ${issueCodes.map(code => `<p class="warning-copy">! ${escapeHtml(issueLabel(code))}</p>`).join("")}
      ${station.country_code === "HR" ? `<p class="warning-copy">◷ ${escapeHtml(t("stale"))}</p>` : ""}
      ${station.country_code === "RS" ? `<p class="warning-copy">⏸ TLS: ${escapeHtml(statusLabel("suspended"))}</p>` : ""}
      ${station.source_url ? `<a href="${escapeHtml(station.source_url)}" target="_blank" rel="noopener">${escapeHtml(t("officialSource"))}</a>` : ""}
    </article>`;
  }).join("");
}

export function matchesFilters(properties) {
  const sourceStatus = displayStatus(properties);
  const qualities = qualityByStation.get(properties.station_id) || new Set();
  const statusMatches = filters.status === "all"
    || (["provisional", "suspect", "unavailable"].includes(filters.status) ? qualities.has(filters.status) : sourceStatus === filters.status);
  return (filters.country === "all" || properties.country_code === filters.country)
    && (filters.source === "all" || properties.source_id === filters.source)
    && statusMatches
    && (filters.type === "all" || properties.station_type === filters.type);
}

export function initBetaUi(international, onFilter) {
  data = international; notify = onFilter; buildQualityIndex();
  for (const [key, selector] of [["country", "#country-filter"], ["source", "#source-filter"], ["status", "#status-filter"], ["type", "#type-filter"]]) {
    document.querySelector(selector).addEventListener("change", event => { filters[key] = event.target.value; renderUnmapped(); notify(matchesFilters); });
  }
  renderFilters(); renderMetrics(); renderUnmapped(); applyTranslations();
  onLanguageChange(() => { renderFilters(); renderMetrics(); renderUnmapped(); });
}

export function refreshBetaUi() { if (data) { renderFilters(); renderMetrics(); renderUnmapped(); } }
