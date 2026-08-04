import { getLocale } from "./i18n.js";

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
  return new Intl.NumberFormat(getLocale(), { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(Number(value));
}

export function formatDate(value, withTime = false, requestedTimeZone = null) {
  if (!value) return "—";
  const text = String(value);
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(text);
  let date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  let timeZone = dateOnly ? "UTC" : requestedTimeZone || "Europe/Bucharest";
  const options = () => ({
    timeZone, day: "2-digit", month: "2-digit", year: "numeric",
    ...(!dateOnly && withTime ? { hour: "2-digit", minute: "2-digit" } : {})
  });
  try {
    return new Intl.DateTimeFormat(getLocale(), options()).format(date);
  } catch (error) {
    if (!(error instanceof RangeError)) throw error;
    const local = text.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (requestedTimeZone && local) {
      date = new Date(Date.UTC(Number(local[1]), Number(local[2]) - 1, Number(local[3]), Number(local[4]), Number(local[5])));
      timeZone = "UTC";
      return new Intl.DateTimeFormat(getLocale(), options()).format(date);
    }
    timeZone = dateOnly ? "UTC" : "Europe/Bucharest";
    return new Intl.DateTimeFormat(getLocale(), options()).format(date);
  }
}

export function safeFilename(value) {
  return String(value || "date").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}
