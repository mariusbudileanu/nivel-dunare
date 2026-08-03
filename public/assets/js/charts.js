import { COLORS, LEADS, PLOT_CONFIG, formatDate, safeFilename } from "./config.js";

const registry = new Map();
const baseLayout = {
  paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff", font: { family: "Inter, system-ui, sans-serif", color: COLORS.text, size: 12 },
  margin: { l: 62, r: 28, t: 28, b: 58 }, hovermode: "x unified",
  xaxis: { gridcolor: "#edf2f5", linecolor: COLORS.grid, zeroline: false, automargin: true },
  yaxis: { gridcolor: "#e5ebef", linecolor: COLORS.grid, zerolinecolor: COLORS.secondary, automargin: true },
  legend: { orientation: "h", y: 1.08, x: 0, bgcolor: "rgba(255,255,255,.85)" },
  transition: { duration: 180 },
};

function noDataTrace(message = "Nu există încă suficiente date pentru această selecție.") {
  return [{ x: [], y: [], type: "scatter", mode: "lines", name: "Fără date", hoverinfo: "skip" }];
}

function register(id, meta) { registry.set(id, meta); }
function dateOnly(value) { return String(value || "").slice(0, 10); }

export function filterByRange(rows, field, range) {
  if (!range?.from && !range?.to) return rows;
  return rows.filter(row => (!range.from || dateOnly(row[field]) >= range.from) && (!range.to || dateOnly(row[field]) <= range.to));
}

export async function renderLevel(id, station, observations, forecasts, range) {
  const obs = filterByRange(observations, "measurement_datetime", range);
  const issues = [...new Set(forecasts.map(row => row.forecast_issue_datetime))].sort();
  const latestIssue = issues.at(-1);
  const forecast = forecasts.filter(row => row.forecast_issue_datetime === latestIssue && row.forecast_available);
  const observedByDate = new Map(observations.map(row => [row.measurement_date, row]));
  const traces = [];
  if (obs.length) {
    traces.push({
      x: obs.map(row => row.measurement_datetime), y: obs.map(row => row.level_cm),
      customdata: obs.map(row => [row.variation_cm_24h, row.water_temperature_c, row.quality_flag]),
      type: "scatter", mode: "lines+markers", name: "Observat", connectgaps: false,
      line: { color: COLORS.observation, width: 3 }, marker: { color: COLORS.observation, size: 7 },
      hovertemplate: "<b>%{x|%d.%m.%Y}</b><br>Nivel: %{y:.0f} cm<br>Variație: %{customdata[0]:+.0f} cm<br>Temperatură: %{customdata[1]:.1f} °C<br>Stare: %{customdata[2]}<extra>Observat</extra>"
    });
    const latest = obs.at(-1);
    traces.push({ x: [latest.measurement_datetime], y: [latest.level_cm], type: "scatter", mode: "markers", name: "Observația curentă", marker: { color: COLORS.current, size: 14, line: { color: "white", width: 3 } }, hovertemplate: "Observația curentă<br>%{x|%d.%m.%Y}: %{y:.0f} cm<extra></extra>" });
  }
  if (forecast.length) {
    const custom = forecast.map(row => {
      const actual = observedByDate.get(row.target_date)?.level_cm;
      const error = actual == null ? null : Number(row.forecast_level_cm) - Number(actual);
      return [row.lead_hours, row.forecast_issue_datetime, row.quality_flag, actual, error];
    });
    const lastObservedDate = observations.at(-1)?.measurement_date;
    traces.push({
      x: forecast.map(row => row.target_datetime), y: forecast.map(row => row.forecast_level_cm),
      customdata: custom, type: "scatter", mode: "lines+markers", name: "Prognozat",
      connectgaps: false, line: { color: COLORS.forecast, width: 3, dash: "dash" },
      marker: { color: COLORS.forecast, size: 10, symbol: forecast.map(row => row.target_date <= lastObservedDate ? "circle-open" : "circle") },
      hovertemplate: "<b>Țintă %{x|%d.%m.%Y}</b><br>Prognoză: %{y:.0f} cm<br>Orizont: %{customdata[0]} h<br>Emisă: %{customdata[1]|%d.%m.%Y}<br>Validare: %{customdata[2]}<br>Observat: %{customdata[3]:.0f} cm<br>Eroare: %{customdata[4]:+.0f} cm<extra>Prognozat</extra>"
    });
  }
  const latestDate = observations.at(-1)?.measurement_datetime;
  const maxForecast = forecast.at(-1)?.target_datetime;
  const shapes = latestDate && maxForecast ? [
    { type: "rect", xref: "x", yref: "paper", x0: latestDate, x1: maxForecast, y0: 0, y1: 1, fillcolor: "rgba(113,97,217,.07)", line: { width: 0 }, layer: "below" },
    { type: "line", xref: "x", yref: "paper", x0: latestDate, x1: latestDate, y0: 0, y1: 1, line: { color: COLORS.current, width: 1.5, dash: "dot" } }
  ] : [];
  await Plotly.react(id, traces.length ? traces : noDataTrace(), {
    ...baseLayout, shapes, yaxis: { ...baseLayout.yaxis, title: "Nivel (cm)" },
    xaxis: { ...baseLayout.xaxis, rangeslider: { visible: true, thickness: .08 }, range: range?.from && range?.to ? [range.from, range.to] : undefined }
  }, PLOT_CONFIG);
  register(id, { title: `${station.display_name} — Evoluția nivelului și prognoza`, slug: station.slug, kind: "evolutie_prognoza", range });
}

export async function renderVariation(id, station, observations, range) {
  const rows = filterByRange(observations, "measurement_datetime", range);
  const colors = rows.map(row => row.variation_cm_24h > 0 ? COLORS.rising : row.variation_cm_24h < 0 ? COLORS.falling : COLORS.stationary);
  const symbols = rows.map(row => row.variation_cm_24h > 0 ? `+${row.variation_cm_24h}` : row.variation_cm_24h < 0 ? `${row.variation_cm_24h}` : "0");
  const traces = rows.length ? [{
    x: rows.map(row => row.measurement_datetime), y: rows.map(row => row.variation_cm_24h),
    customdata: rows.map(row => [row.level_cm, row.variation_cm_24h > 0 ? "creștere" : row.variation_cm_24h < 0 ? "scădere" : "staționare"]),
    text: symbols, textposition: "outside", cliponaxis: false, type: "bar", name: "Variație 24 h", marker: { color: colors },
    hovertemplate: "<b>%{x|%d.%m.%Y}</b><br>Variație: %{y:+.0f} cm<br>Tendință: %{customdata[1]}<br>Nivel: %{customdata[0]:.0f} cm<extra></extra>"
  }] : noDataTrace();
  await Plotly.react(id, traces, { ...baseLayout, showlegend: false, yaxis: { ...baseLayout.yaxis, title: "Variație (cm)", zeroline: true }, xaxis: { ...baseLayout.xaxis, range: range?.from && range?.to ? [range.from, range.to] : undefined } }, PLOT_CONFIG);
  register(id, { title: `${station.display_name} — Variația zilnică`, slug: station.slug, kind: "variatie", range });
}

export async function renderTemperature(id, station, observations, range) {
  const rows = filterByRange(observations, "measurement_datetime", range);
  const values = rows.map(row => Number(row.water_temperature_c));
  const traces = rows.length ? [{ x: rows.map(row => row.measurement_datetime), y: values, type: "scatter", mode: "lines+markers", name: "Temperatura apei", line: { color: "#e58a3d", width: 3 }, marker: { size: 7 }, hovertemplate: "<b>%{x|%d.%m.%Y}</b><br>Temperatură: %{y:.1f} °C<extra></extra>" }] : noDataTrace();
  const subtitle = values.length ? `Min ${Math.min(...values).toFixed(1)} °C · Max ${Math.max(...values).toFixed(1)} °C` : "Fără date";
  await Plotly.react(id, traces, { ...baseLayout, annotations: [{ text: subtitle, xref: "paper", yref: "paper", x: 1, y: 1.08, showarrow: false, font: { color: COLORS.secondary, size: 11 } }], showlegend: false, yaxis: { ...baseLayout.yaxis, title: "Temperatură (°C)" }, xaxis: { ...baseLayout.xaxis, range: range?.from && range?.to ? [range.from, range.to] : undefined } }, PLOT_CONFIG);
  register(id, { title: `${station.display_name} — Temperatura apei`, slug: station.slug, kind: "temperatura", range });
}

export async function renderHistory(id, station, observations, forecasts, issue) {
  const selected = forecasts.filter(row => row.forecast_issue_datetime === issue);
  const start = new Date(issue); start.setDate(start.getDate() - 7);
  const end = new Date(issue); end.setDate(end.getDate() + 7);
  const observedRows = observations.filter(row => new Date(row.measurement_datetime) >= start && new Date(row.measurement_datetime) <= end);
  const observedByDate = new Map(observations.map(row => [row.measurement_date, row.level_cm]));
  const traces = [];
  if (observedRows.length) traces.push({ x: observedRows.map(row => row.measurement_datetime), y: observedRows.map(row => row.level_cm), type: "scatter", mode: "lines+markers", name: "Observat", connectgaps: false, line: { color: COLORS.observation, width: 3 }, hovertemplate: "%{x|%d.%m.%Y}: %{y:.0f} cm<extra>Observat</extra>" });
  const available = selected.filter(row => row.forecast_available);
  if (available.length) traces.push({ x: available.map(row => row.target_datetime), y: available.map(row => row.forecast_level_cm), customdata: available.map(row => { const actual = observedByDate.get(row.target_date); return [row.lead_hours, actual, actual == null ? null : Number(row.forecast_level_cm) - Number(actual), row.quality_flag]; }), type: "scatter", mode: "lines+markers", name: "Prognoza selectată", line: { color: COLORS.forecast, dash: "dash", width: 3 }, marker: { size: 10 }, hovertemplate: "Țintă %{x|%d.%m.%Y}<br>Prognoză %{y:.0f} cm<br>Orizont %{customdata[0]} h<br>Observat %{customdata[1]:.0f} cm<br>Eroare %{customdata[2]:+.0f} cm<br>%{customdata[3]}<extra></extra>" });
  await Plotly.react(id, traces.length ? traces : noDataTrace("Ediția selectată nu conține prognoze disponibile."), { ...baseLayout, yaxis: { ...baseLayout.yaxis, title: "Nivel (cm)" } }, PLOT_CONFIG);
  register(id, { title: `${station.display_name} — Prognoză emisă ${dateOnly(issue)}`, slug: station.slug, kind: `prognoza_emisa_${dateOnly(issue)}`, range: { from: dateOnly(start.toISOString()), to: dateOnly(end.toISOString()) } });
}

export async function renderScores(id, station, scores) {
  const usable = scores.filter(row => row.mae_cm !== null && row.mae_cm !== "");
  const traces = usable.length ? [{ x: usable.map(row => `${row.lead_hours} h`), y: usable.map(row => row.mae_cm), customdata: usable.map(row => [row.n_pairs, row.rmse_cm, row.bias_cm, row.maturity]), type: "bar", name: "MAE", marker: { color: COLORS.forecast }, hovertemplate: "Orizont %{x}<br>MAE %{y:.1f} cm<br>RMSE %{customdata[1]:.1f} cm<br>Bias %{customdata[2]:+.1f} cm<br>Perechi %{customdata[0]}<br>%{customdata[3]}<extra></extra>" }] : noDataTrace("Date insuficiente pentru scoruri — sunt necesare observații la datele-țintă.");
  await Plotly.react(id, traces, { ...baseLayout, showlegend: false, xaxis: { ...baseLayout.xaxis, title: "Orizont" }, yaxis: { ...baseLayout.yaxis, title: "MAE (cm)" } }, PLOT_CONFIG);
  register(id, { title: `${station.display_name} — Evaluarea prognozelor`, slug: station.slug, kind: "evaluare_prognoze", range: {} });
}

export async function renderComparison(id, series, mode, range) {
  const traces = series.map(({ station, observations }, index) => {
    const rows = filterByRange(observations, "measurement_datetime", range);
    const first = rows[0]?.level_cm;
    const y = mode === "variation" ? rows.map(row => row.variation_cm_24h) : rows.map(row => Number(row.level_cm) - Number(first));
    return { x: rows.map(row => row.measurement_datetime), y, type: "scatter", mode: "lines+markers", connectgaps: false, name: station.display_name, line: { width: 2.5 }, marker: { size: 6 }, hovertemplate: `%{x|%d.%m.%Y}<br>%{y:+.0f} cm<extra>${station.display_name}</extra>` };
  });
  await Plotly.react(id, traces.length ? traces : noDataTrace("Alege cel puțin o stație."), { ...baseLayout, yaxis: { ...baseLayout.yaxis, title: mode === "variation" ? "Variație 24 h (cm)" : "Schimbare față de prima zi (cm)", zeroline: true } }, PLOT_CONFIG);
  const slugs = series.map(item => item.station.slug).join("_") || "statii";
  register(id, { title: mode === "variation" ? "Comparație — variație zilnică" : "Comparație — schimbare față de prima zi", slug: slugs, kind: "comparatie", range });
}

function currentVisibleRows(graph) {
  const rows = [];
  graph.data.forEach(trace => {
    if (trace.visible === "legendonly" || !Array.isArray(trace.x) || !Array.isArray(trace.y)) return;
    trace.x.forEach((x, index) => rows.push({ serie: trace.name || "serie", datetime: x, valoare: trace.y[index] ?? "" }));
  });
  return rows;
}

function csvEscape(value) { const text = value == null ? "" : String(value); return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text; }
function downloadBlob(content, name, type) { const url = URL.createObjectURL(new Blob([content], { type })); const link = document.createElement("a"); link.href = url; link.download = name; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }

export function downloadChartCsv(id) {
  const graph = document.getElementById(id); const meta = registry.get(id);
  const rows = currentVisibleRows(graph); const unit = meta.kind.includes("temperatura") ? "°C" : "cm";
  const csv = ["serie,datetime,valoare,unitate", ...rows.map(row => [row.serie, row.datetime, row.valoare, unit].map(csvEscape).join(","))].join("\r\n");
  downloadBlob("\ufeff" + csv, `nivel_dunare_${safeFilename(meta.slug)}_${safeFilename(meta.kind)}.csv`, "text/csv;charset=utf-8");
}

export async function downloadChartPng(id) {
  const graph = document.getElementById(id); const meta = registry.get(id);
  const oldTitle = graph.layout.title; const oldMargin = { ...graph.layout.margin }; const oldAnnotations = graph.layout.annotations || [];
  const interval = meta.range?.from || meta.range?.to ? `${meta.range?.from || "început"}–${meta.range?.to || "prezent"}` : "tot intervalul disponibil";
  const generated = new Intl.DateTimeFormat("ro-RO", { timeZone: "Europe/Bucharest", dateStyle: "medium", timeStyle: "short" }).format(new Date());
  await Plotly.relayout(graph, {
    title: { text: `${meta.title}<br><span style="font-size:13px">Interval: ${interval}</span>`, x: .04, xanchor: "left" },
    margin: { l: 85, r: 55, t: 115, b: 95 }, paper_bgcolor: "white", plot_bgcolor: "white",
    annotations: [...oldAnnotations, { text: `Sursa datelor: AFDJ · Generat: ${generated} Europe/Bucharest`, xref: "paper", yref: "paper", x: 0, y: -.18, showarrow: false, xanchor: "left", font: { size: 12, color: COLORS.secondary } }]
  });
  try {
    await Plotly.downloadImage(graph, { format: "png", width: 1800, height: 1000, scale: 2, filename: `nivel_dunare_${safeFilename(meta.slug)}_${safeFilename(meta.kind)}_${meta.range?.from || "start"}_${meta.range?.to || "prezent"}` });
  } finally {
    await Plotly.relayout(graph, { title: oldTitle || null, margin: oldMargin, annotations: oldAnnotations });
  }
}

export function resizeChart(id) { const element = document.getElementById(id); if (element?.data) Plotly.Plots.resize(element); }
