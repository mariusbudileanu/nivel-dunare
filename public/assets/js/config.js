export const COLORS = {
  text: "#183042", secondary: "#647484", grid: "#dce5ec",
  observation: "#147da6", current: "#00a6a6", forecast: "#7161d9",
  rising: "#169b7a", falling: "#e36b5d", stationary: "#7b8794", warning: "#e5a93d"
};

export const MAP_CONFIG = {
  center: [44.6, 25.5], zoom: 6,
  tiles: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
  attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
  fallbackTiles: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  fallbackAttribution: "&copy; OpenStreetMap contributors"
};

export const PLOT_CONFIG = {
  responsive: true, displaylogo: false, scrollZoom: true,
  modeBarButtonsToRemove: ["sendDataToCloud", "lasso2d", "select2d", "toImage"]
};

export const RANGE_DAYS = { "7d": 7, "30d": 30, "90d": 90, "365d": 365 };
export const LEADS = [24, 48, 72, 96, 120];

export function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "—";
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(Number(value));
}

export function formatDate(value, withTime = false) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ro-RO", {
    timeZone: "Europe/Bucharest", day: "2-digit", month: "2-digit", year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {})
  }).format(date);
}

export function safeFilename(value) {
  return String(value || "date").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}
