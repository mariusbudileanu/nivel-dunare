import { formatDate, formatNumber } from "./config.js";
import { applyTranslations, coordinateConfidenceLabel, countryName, freshnessLabel, frequencyLabel, getLanguage, issueLabel, onLanguageChange, qualityLabel, stationTypeLabel, statusLabel, t } from "./i18n.js";

const filters = { country: "all", source: "all", trend: "all", access: "all", status: "all", automation: "all", freshness: "all", quality: "all", type: "all", stream: "all", coordinate: "all" };
let data;
let notify = () => {};
let qualityByStation = new Map();
let afdjSource = null;
// Downstream-to-upstream country order; must match app.js's COUNTRY_ORDER (no shared
// constants module exists between these two files today).
const COUNTRY_ORDER = ["RO", "BG", "RS", "HR", "HU", "SK", "AT", "DE"];

function displayStatus(station) {
  return station.freshness_status === "stale" ? "stale" : station.source_status;
}

function buildQualityIndex() {
  qualityByStation = new Map(data.stations.map(station => [station.station_id, new Set()]));
  for (const row of data.latest) qualityByStation.get(row.station_id)?.add(row.canonical_quality_flag || "unavailable");
  for (const issue of data.qualityIssues) {
    if (issue.active === false || issue.code !== "outside_plausible_water_temperature_range") continue;
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
  const trend = document.querySelector("#trend-filter");
  const access = document.querySelector("#access-filter");
  const status = document.querySelector("#status-filter");
  const automation = document.querySelector("#automation-filter");
  const freshness = document.querySelector("#freshness-filter");
  const quality = document.querySelector("#quality-filter");
  const type = document.querySelector("#type-filter");
  const stream = document.querySelector("#stream-filter");
  const coordinate = document.querySelector("#coordinate-filter");
  country.innerHTML = option("all", t("allCountries"), filters.country) + ["RO", "DE", "AT", "SK", "HU", "HR", "BG", "RS"].map(code => option(code, countryName(code), filters.country)).join("");
  source.innerHTML = option("all", t("allSources"), filters.source) + [{ source_id: "afdj_ro", label: "AFDJ" }, ...data.sources].map(item => option(item.source_id, item.label, filters.source)).join("");
  trend.innerHTML = option("all", t("allTrends"), filters.trend) + ["up", "down", "still"].map(value => option(value, t(`trend_${value}`), filters.trend)).join("");
  access.innerHTML = option("all", t("allAccessStates"), filters.access) + [...new Set(data.sources.map(item => item.access_status))].filter(Boolean).map(value => option(value, statusLabel(value), filters.access)).join("");
  status.innerHTML = option("all", t("allStatuses"), filters.status) + ["complete", "partial", "suspended", "unavailable"].map(value => option(value, `${statusIcon(value)} ${statusLabel(value)}`, filters.status)).join("");
  automation.innerHTML = option("all", t("allAutomationStates"), filters.automation) + ["scheduled", "manual", "disabled"].map(value => option(value, statusLabel(value), filters.automation)).join("");
  freshness.innerHTML = option("all", t("allFreshnessStates"), filters.freshness) + ["current", "stale", "unavailable"].map(value => option(value, freshnessLabel(value), filters.freshness)).join("");
  quality.innerHTML = option("all", t("allQualityStates"), filters.quality) + ["observed", "provisional", "unavailable"].map(value => option(value, qualityLabel(value), filters.quality)).join("");
  const types = [...new Set(data.stations.map(station => station.station_type))].sort();
  type.innerHTML = option("all", t("allTypes"), filters.type) + types.map(value => option(value, stationTypeLabel(value), filters.type)).join("");
  const streamTypes = [...new Set(data.streams.map(item => item.source_stream_type))].sort();
  stream.innerHTML = option("all", t("allStreams"), filters.stream) + streamTypes.map(value => option(value, t(`stream_${value}`), filters.stream)).join("");
  coordinate.innerHTML = [["all", "allCoordinateTypes"], ["official", "officialCoordinates"], ["manual", "manuallyVerifiedCoordinates"], ["approximate", "approximateCoordinates"], ["without", "withoutCoordinates"]].map(([value, key]) => option(value, t(key), filters.coordinate)).join("");
}

function renderMetrics() {
  const countSources = (field, value) => data.sources.filter(source => source[field] === value).length;
  const groups = [
    ["coverage", [["totalRegistry", data.status.station_count], ["mappedStations", data.status.mapped_station_count], ["officialCoordinateStations", data.status.official_coordinate_station_count], ["manuallyVerifiedCoordinateStations", data.status.manually_verified_coordinate_station_count], ["approximateCoordinateStations", data.status.approximate_coordinate_station_count], ["unmappedStations", data.status.unmapped_station_count]]],
    ["automation", [["scheduledSources", countSources("automation_status", "scheduled")], ["manualSources", countSources("automation_status", "manual")], ["disabledSources", countSources("automation_status", "disabled")]]],
    ["freshness", [["currentSources", countSources("freshness_status", "current")], ["staleSources", countSources("freshness_status", "stale")], ["unavailableSources", countSources("freshness_status", "unavailable")]]],
    ["integration", [["completeSources", countSources("source_status", "complete")], ["partialSources", countSources("source_status", "partial")], ["suspendedSources", countSources("source_status", "suspended")]]],
    ["sourceQuality", [["validatedSources", countSources("validation_status", "source_validated")], ["provisionalSources", countSources("validation_status", "source_provisional")], ["technicallyValidatedSources", countSources("validation_status", "technical_validation_passed")], ["technicalFailures", countSources("validation_status", "technical_validation_failed")]]],
  ];
  document.querySelector("#international-metrics").innerHTML = groups.map(([title, values]) => `<section class="metric-group"><h3>${escapeHtml(t(title))}</h3><div class="metric-items">${values.map(([key, value]) => `<div><span>${escapeHtml(t(key))}</span><strong>${formatNumber(value)}</strong></div>`).join("")}</div></section>`).join("");
}
function sourceFrequencySummary(source) {
  const sourceFrequency = Array.isArray(source.source_observation_frequency) ? source.source_observation_frequency.map(frequencyLabel).join(", ") : source.source_observation_frequency ? frequencyLabel(source.source_observation_frequency) : "";
  return [source.update_frequency ? frequencyLabel(source.update_frequency) : "", sourceFrequency].filter(Boolean).join(" · ") || t("unavailable");
}

function detailLine(label, value) {
  if (value === null || value === undefined || value === "") return "";
  return `<p><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value)}</p>`;
}

function sourceLastObservationValue(source, sourceStations) {
  const stationIds = new Set(sourceStations.map(station => station.station_id));
  let latestUtc = null;
  for (const row of data.latest) {
    if (!stationIds.has(row.station_id) || !row.measurement_datetime_utc) continue;
    if (!latestUtc || new Date(row.measurement_datetime_utc) > new Date(latestUtc)) latestUtc = row.measurement_datetime_utc;
  }
  return latestUtc || source.last_source_observation_at;
}

function renderSourcesTable() {
  const stationsBySource = new Map();
  for (const station of data.stations) {
    if (!stationsBySource.has(station.source_id)) stationsBySource.set(station.source_id, []);
    stationsBySource.get(station.source_id).push(station);
  }
  const sources = [...(afdjSource ? [afdjSource] : []), ...data.sources]
    .sort((a, b) => COUNTRY_ORDER.indexOf(a.country_code) - COUNTRY_ORDER.indexOf(b.country_code));
  const body = document.querySelector("#source-summary-body");
  body.innerHTML = sources.map((source, index) => {
    const sourceStations = stationsBySource.get(source.source_id) || [];
    const sourceUrl = source.source_url || sourceStations.find(station => station.source_url)?.source_url;
    const messageTemplate = source[getLanguage() === "en" ? "validation_message_en" : "validation_message_ro"] || t("unavailable");
    const observationValue = sourceLastObservationValue(source, sourceStations);
    const observationDate = observationValue ? formatDate(observationValue, true, "Europe/Bucharest") : t("unavailable");
    const message = messageTemplate.replaceAll("{date}", observationDate);
    const detailId = `source-details-${index}`;
    return `<tr class="source-row">
      <td>${escapeHtml(countryName(source.country_code))}</td>
      <td>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener">${escapeHtml(source.label)}</a>` : escapeHtml(source.label)}</td>
      <td>${escapeHtml(statusLabel(source.automation_status))}</td>
      <td>${escapeHtml(observationDate)}</td>
      <td><span class="status-tag ${escapeHtml(source.source_status)}">${escapeHtml(t("sourceIntegrationBadge", { status: statusLabel(source.source_status) }))}</span> <span class="status-tag ${escapeHtml(source.freshness_status)}">${escapeHtml(t("freshnessBadge", { status: freshnessLabel(source.freshness_status) }))}</span></td>
      <td><button type="button" class="button ghost compact source-details-toggle" aria-expanded="false" aria-controls="${detailId}" data-i18n="showDetails">${escapeHtml(t("showDetails"))}</button></td>
    </tr>
    <tr class="source-details-row" id="${detailId}" hidden>
      <td colspan="6">
        ${detailLine(t("lastAttempt"), source.last_attempt_at ? formatDate(source.last_attempt_at, true) : t("unavailable"))}
        ${detailLine(t("lastSuccess"), source.last_success_at ? formatDate(source.last_success_at, true) : t("unavailable"))}
        ${detailLine(t("accessStatus"), statusLabel(source.access_status))}
        ${detailLine(t("validationStatus"), statusLabel(source.validation_status))}
        ${detailLine(t("frequency"), sourceFrequencySummary(source))}
        ${detailLine(t("station"), `${formatNumber(source.physical_station_count)} / ${formatNumber(source.station_count)}`)}
        <p>${escapeHtml(message)}</p>
      </td>
    </tr>`;
  }).join("");
  body.querySelectorAll(".source-details-toggle").forEach(button => button.addEventListener("click", () => {
    const row = document.getElementById(button.getAttribute("aria-controls"));
    const expanded = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", String(!expanded)); row.hidden = expanded;
    button.textContent = expanded ? t("showDetails") : t("hideDetails");
  }));
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
  const section = document.querySelector(".unmapped-section");
  if (section) section.hidden = data.unmapped.length === 0;
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
      <p class="warning-copy">! ${escapeHtml(t("coordinateReviewRequired"))} (${escapeHtml(coordinateConfidenceLabel(station.coordinate_confidence))})</p>
      ${issueCodes.map(code => `<p class="warning-copy">! ${escapeHtml(issueLabel(code))}</p>`).join("")}
      ${station.country_code === "HR" ? `<p class="warning-copy">◷ ${escapeHtml(t("stale"))}</p>` : ""}
      ${station.country_code === "RS" ? `<p class="warning-copy">${escapeHtml(t(station.source_status === "suspended" ? "rsTlsSuspended" : "rsProvisionalData"))}</p>` : ""}
      ${station.source_url ? `<a href="${escapeHtml(station.source_url)}" target="_blank" rel="noopener">${escapeHtml(t("officialSource"))}</a>` : ""}
    </article>`;
  }).join("");
}

export function matchesFilters(properties) {
  const sourceStatus = displayStatus(properties);
  const qualities = qualityByStation.get(properties.station_id) || new Set();
  const variation = properties.variation_cm_24h ?? properties.water_level?.variation_value;
  const trend = properties.trend || (variation > 0 ? "up" : variation < 0 ? "down" : variation === 0 ? "still" : null);
  const statusMatches = filters.status === "all" || sourceStatus === filters.status;
  const coordinateType = properties.mapped === false
    ? "without" : properties.coordinate_method === "manually_verified_station_coordinate" ? "manual"
      : properties.coordinate_method === "geocoded_locality" || properties.is_exact_station_location === false ? "approximate" : "official";
  return (filters.country === "all" || properties.country_code === filters.country)
    && (filters.source === "all" || properties.source_id === filters.source)
    && (filters.trend === "all" || trend === filters.trend)
    && (filters.access === "all" || properties.access_status === filters.access)
    && statusMatches
    && (filters.automation === "all" || properties.automation_status === filters.automation)
    && (filters.freshness === "all" || properties.freshness_status === filters.freshness)
    && (filters.quality === "all" || qualities.has(filters.quality))
    && (filters.type === "all" || properties.station_type === filters.type)
    && (filters.stream === "all" || (properties.streams || [{ source_stream_type: properties.source_stream_type }]).some(item => item.source_stream_type === filters.stream))
    && (filters.coordinate === "all" || coordinateType === filters.coordinate);
}

export function initBetaUi(international, onFilter, afdjPseudoSource = null) {
  data = international; notify = onFilter; afdjSource = afdjPseudoSource; buildQualityIndex();
  for (const [key, selector] of [["country", "#country-filter"], ["source", "#source-filter"], ["trend", "#trend-filter"], ["access", "#access-filter"], ["status", "#status-filter"], ["automation", "#automation-filter"], ["freshness", "#freshness-filter"], ["quality", "#quality-filter"], ["type", "#type-filter"], ["stream", "#stream-filter"], ["coordinate", "#coordinate-filter"]]) {
    document.querySelector(selector).addEventListener("change", event => { filters[key] = event.target.value; renderUnmapped(); notify(matchesFilters); });
  }
  renderFilters(); renderMetrics(); renderSourcesTable(); renderUnmapped(); applyTranslations();
  onLanguageChange(() => { renderFilters(); renderMetrics(); renderSourcesTable(); renderUnmapped(); });
}

export function refreshBetaUi() { if (data) { renderFilters(); renderMetrics(); renderSourcesTable(); renderUnmapped(); } }
