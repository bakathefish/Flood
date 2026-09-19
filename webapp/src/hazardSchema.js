// Validator for the river hazard watch feed
// (punjabflood/outputs/forecast/latest.json, written by the daily Action).
//
// Same discipline as forecastSchema.js: one place decides what the section
// renders, a malformed field is shown as unknown and never as a calm number,
// and the states are mutually exclusive. The feed is the product JSON with a
// `record` field naming the dated file it copies.

export const DAMS = ['Bhakra', 'Pong', 'Ranjit Sagar'];
export const HORIZONS = [1, 2, 3, 4, 5];
export const WATCH_LEVELS = ['quiet', 'watch', 'alert'];
export const WRD_CLASSES = ['Low', 'Medium', 'High'];

// A watch issued more than this many days ago is shown with a stale notice.
// The Action runs once a day; two missed cycles is worth telling the reader.
export const MAX_ISSUE_AGE_DAYS = 2;

export function num(x) {
  return typeof x === 'number' && Number.isFinite(x) ? x : null;
}

export function inRange(x, lo, hi) {
  const v = num(x);
  return v === null || v < lo || v > hi ? null : v;
}

function isoDate(s) {
  return typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : null;
}

// Days between the issue date (UTC midnight) and now; null when unknown.
export function issueAgeDays(issueDate, nowMs) {
  const d = isoDate(issueDate);
  if (d === null || typeof nowMs !== 'number') return null;
  const t = Date.parse(d + 'T00:00:00Z');
  if (!Number.isFinite(t)) return null;
  return Math.floor((nowMs - t) / 86400000);
}

// The probability the spillway is forced, per horizon day, under the widest
// error budget the product prints (rain-ensemble spread, the inflow model's
// ordinary-day error and its flood-scale volume error). A missing or
// out-of-range value is null: "—" on the page, never 0.
export function spillwayProbabilities(dam) {
  const ens = dam && typeof dam.ensemble === 'object' && dam.ensemble !== null ? dam.ensemble : {};
  return HORIZONS.map((h) => {
    const e = ens[String(h)];
    if (!e || typeof e !== 'object') return null;
    return inRange(e.p_exhaustion_flood_scale, 0, 1);
  });
}

export function damRow(name, dam) {
  if (!dam || typeof dam !== 'object') return null;
  const st = dam.state && typeof dam.state === 'object' ? dam.state : {};
  const level = num(st.level_ft);
  const storage = inRange(dam.storage_fraction, 0, 1.5);
  const inflow = num(st.inflow_cusecs);
  const outflow = num(st.outflow_cusecs);
  const p = spillwayProbabilities(dam);
  // A row with no level, no storage and no probability is not a reading.
  if (level === null && storage === null && p.every((x) => x === null)) return null;
  return {
    name,
    level_ft: level,
    storage_fraction: storage,
    inflow_cusecs: inflow,
    outflow_cusecs: outflow,
    p,
    basis: typeof st.basis === 'string' ? st.basis : null,
  };
}

export function weatherRow(name, w) {
  if (!w || typeof w !== 'object') return null;
  const level = WATCH_LEVELS.includes(w.level) ? w.level : 'unknown';
  const obs = w.observed && typeof w.observed === 'object' ? w.observed : {};
  const fc = w.forecast && typeof w.forecast === 'object' ? w.forecast : {};
  const primary = typeof w.primary_model === 'string' ? w.primary_model : null;
  const three = fc.three_day_mm && typeof fc.three_day_mm === 'object' ? fc.three_day_mm : {};
  const pct = fc.three_day_percentile && typeof fc.three_day_percentile === 'object'
    ? fc.three_day_percentile : {};
  return {
    name,
    level,
    observed_total_mm: num(obs.total_mm),
    observed_days: Array.isArray(obs.days) ? obs.days.length : null,
    next3_mm: primary ? num(three[primary]) : null,
    next3_percentile: primary ? inRange(pct[primary], 0, 100) : null,
  };
}

export function reachRow(r) {
  if (!r || typeof r !== 'object' || typeof r.station !== 'string') return null;
  const peak = num(r.peak_cusecs);
  return {
    station: r.station,
    river: typeof r.river === 'string' ? r.river : null,
    peak_cusecs: peak,
    peak_date: isoDate(r.peak_date),
    // null from the producer means "below the department's Low threshold";
    // anything else unrecognised is unknown.
    cls: r.peak_class === null ? 'below' : (WRD_CLASSES.includes(r.peak_class) ? r.peak_class : 'unknown'),
  };
}

export function snowmeltSummary(dam) {
  const s = dam && dam.snowmelt && typeof dam.snowmelt === 'object' ? dam.snowmelt : null;
  if (!s) return null;
  const sum = (a) => (Array.isArray(a) && a.every((x) => num(x) !== null) ? a.reduce((p, q) => p + q, 0) : null);
  return {
    applied: s.applied === true,
    recent_mm: sum(s.melt_mm_recent),
    recent_days: Array.isArray(s.melt_mm_recent) ? s.melt_mm_recent.length : null,
    forecast_mm: sum(s.melt_mm_forecast),
    pack_mm: num(s.pack_mm_issue),
    note: typeof s.note === 'string' ? s.note : null,
  };
}

/**
 * Resolve what the hazard section renders.
 * state: 'loading' | 'unavailable' | 'watch'.
 * `stale` is set on a watch older than MAX_ISSUE_AGE_DAYS; the watch still
 * shows, with the issue date beside it, because an old reading with its date
 * is information and a blank is not.
 */
export function resolveHazardState(feed, {fetchFailed = false, nowMs = null} = {}) {
  const out = {
    state: 'unavailable', stale: false, ageDays: null, issue_date: null,
    generated_utc: null, bulletin_as_on: null, record: null, disclaimer: null,
    dams: [], weather: [], reaches: [], snowmelt: null,
  };
  if (fetchFailed) return out;
  if (!feed || typeof feed !== 'object') {
    out.state = 'loading';
    return out;
  }
  const issue = isoDate(feed.issue_date);
  if (issue === null) return out;
  if (!feed.dams || typeof feed.dams !== 'object') return out;

  const dams = DAMS.map((n) => damRow(n, feed.dams[n])).filter(Boolean);
  if (dams.length === 0) return out;

  out.state = 'watch';
  out.issue_date = issue;
  out.generated_utc = typeof feed.generated_utc === 'string' ? feed.generated_utc : null;
  out.record = typeof feed.record === 'string' ? feed.record : null;
  out.disclaimer = typeof feed.disclaimer === 'string' ? feed.disclaimer : null;
  const b = feed.bulletin && typeof feed.bulletin === 'object' ? feed.bulletin : {};
  out.bulletin_as_on = typeof b.as_on_date === 'string'
    ? (typeof b.as_on_time === 'string' ? `${b.as_on_date} ${b.as_on_time}` : b.as_on_date)
    : null;
  out.ageDays = issueAgeDays(issue, nowMs);
  out.stale = out.ageDays !== null && out.ageDays > MAX_ISSUE_AGE_DAYS;
  out.dams = dams;
  const wx = feed.weather && typeof feed.weather === 'object' ? feed.weather : {};
  out.weather = Object.keys(wx).sort().map((n) => weatherRow(n, wx[n])).filter(Boolean);
  out.reaches = Array.isArray(feed.reaches) ? feed.reaches.map(reachRow).filter(Boolean) : [];
  out.snowmelt = snowmeltSummary(feed.dams.Bhakra);
  return out;
}
