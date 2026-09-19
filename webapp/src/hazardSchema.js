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

// ---- names and dates, one form per language --------------------------------
// The feed carries Latin-script names; the page shows each in the reader's
// script, falling back to the feed's own name when a translation is missing
// (a new station must never vanish). The Water Resources Department's
// Low / Medium / High classes keep their English word as a gloss because
// that is the word on the department's own tables.
export const NAMES = {
  hi: {
    'Bhakra': 'भाखड़ा', 'Pong': 'पौंग', 'Ranjit Sagar': 'रणजीत सागर',
    'Beas local': 'ब्यास स्थानीय', 'Ghaggar Bhankarpur': 'घग्गर भानकरपुर',
    'Ghaggar Khanauri': 'घग्गर खनौरी', 'Harike local': 'हरीके स्थानीय',
    'Sutlej local': 'सतलुज स्थानीय',
    'Dhilwan': 'धिलवान', 'Ferozepur Head Works': 'फ़िरोज़पुर हेडवर्क्स',
    'Harike Head Works': 'हरीके हेडवर्क्स', 'Naushera Mirthal': 'नौशेरा मिर्थल',
    'Railway Bridge Phillaur': 'रेलवे पुल फिल्लौर', 'Ropar Head Works': 'रोपड़ हेडवर्क्स',
    'Beas': 'ब्यास', 'Sutlej': 'सतलुज', 'Sutlej+Beas': 'सतलुज+ब्यास',
  },
  pa: {
    'Bhakra': 'ਭਾਖੜਾ', 'Pong': 'ਪੌਂਗ', 'Ranjit Sagar': 'ਰਣਜੀਤ ਸਾਗਰ',
    'Beas local': 'ਬਿਆਸ ਸਥਾਨਕ', 'Ghaggar Bhankarpur': 'ਘੱਗਰ ਭਾਨਕਰਪੁਰ',
    'Ghaggar Khanauri': 'ਘੱਗਰ ਖਨੌਰੀ', 'Harike local': 'ਹਰੀਕੇ ਸਥਾਨਕ',
    'Sutlej local': 'ਸਤਲੁਜ ਸਥਾਨਕ',
    'Dhilwan': 'ਧਿਲਵਾਂ', 'Ferozepur Head Works': 'ਫ਼ਿਰੋਜ਼ਪੁਰ ਹੈੱਡਵਰਕਸ',
    'Harike Head Works': 'ਹਰੀਕੇ ਹੈੱਡਵਰਕਸ', 'Naushera Mirthal': 'ਨੌਸ਼ਹਿਰਾ ਮਿਰਥਲ',
    'Railway Bridge Phillaur': 'ਰੇਲਵੇ ਪੁਲ ਫਿਲੌਰ', 'Ropar Head Works': 'ਰੋਪੜ ਹੈੱਡਵਰਕਸ',
    'Beas': 'ਬਿਆਸ', 'Sutlej': 'ਸਤਲੁਜ', 'Sutlej+Beas': 'ਸਤਲੁਜ+ਬਿਆਸ',
  },
};

export const CLASS_LABELS = {
  en: {Low: 'Low', Medium: 'Medium', High: 'High'},
  hi: {Low: 'निम्न (Low)', Medium: 'मध्यम (Medium)', High: 'उच्च (High)'},
  pa: {Low: 'ਘੱਟ (Low)', Medium: 'ਦਰਮਿਆਨਾ (Medium)', High: 'ਉੱਚ (High)'},
};

export function localName(name, lang) {
  const m = NAMES[lang];
  return m && typeof name === 'string' && m[name] ? m[name] : name;
}

export function classLabel(cls, lang) {
  const m = CLASS_LABELS[lang] || CLASS_LABELS.en;
  return m[cls] || cls;
}

const MONTHS = {
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  hi: ['जनवरी', 'फ़रवरी', 'मार्च', 'अप्रैल', 'मई', 'जून', 'जुलाई', 'अगस्त', 'सितंबर', 'अक्टूबर', 'नवंबर', 'दिसंबर'],
  pa: ['ਜਨਵਰੀ', 'ਫ਼ਰਵਰੀ', 'ਮਾਰਚ', 'ਅਪ੍ਰੈਲ', 'ਮਈ', 'ਜੂਨ', 'ਜੁਲਾਈ', 'ਅਗਸਤ', 'ਸਤੰਬਰ', 'ਅਕਤੂਬਰ', 'ਨਵੰਬਰ', 'ਦਸੰਬਰ'],
};
const MONTHS_SHORT = {
  en: MONTHS.en,
  hi: ['जन', 'फ़र', 'मार्च', 'अप्रै', 'मई', 'जून', 'जुल', 'अग', 'सित', 'अक्टू', 'नव', 'दिस'],
  pa: ['ਜਨ', 'ਫ਼ਰ', 'ਮਾਰਚ', 'ਅਪ੍ਰੈ', 'ਮਈ', 'ਜੂਨ', 'ਜੁਲ', 'ਅਗ', 'ਸਤੰ', 'ਅਕਤੂ', 'ਨਵੰ', 'ਦਸੰ'],
};

// "19 Sep 2026" / "19 सितंबर 2026" / "19 ਸਤੰਬਰ 2026" from an ISO date; null otherwise.
export function formatDate(iso, lang, {year = true, short = false} = {}) {
  const d = isoDate(iso);
  if (d === null) return null;
  const [y, m, day] = d.split('-').map((x) => parseInt(x, 10));
  if (m < 1 || m > 12 || day < 1 || day > 31) return null;
  const names = (short ? MONTHS_SHORT : MONTHS)[lang] || (short ? MONTHS_SHORT : MONTHS).en;
  return `${day} ${names[m - 1]}${year ? ` ${y}` : ''}`;
}

// The bulletin's own DD-MM-YYYY (BBMB's form) and HH:MM, shown in the same
// form as every other date on the page. Anything else is shown as received
// rather than guessed at.
export function formatBulletinAsOn(as_on_date, as_on_time, lang) {
  if (typeof as_on_date !== 'string') return null;
  const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(as_on_date);
  const iso = m ? `${m[3]}-${m[2]}-${m[1]}` : null;
  const date = iso ? formatDate(iso, lang) : as_on_date;
  const time = typeof as_on_time === 'string' && /^\d{2}:\d{2}$/.test(as_on_time) ? ` ${as_on_time}` : '';
  return `${date}${time}`;
}

// The five horizon days as short calendar labels ("20 Sep"), so a wrapped
// row of percentages still says which day each one is.
export function horizonLabels(issueIso, lang) {
  const d = isoDate(issueIso);
  if (d === null) return HORIZONS.map((h) => `+${h}`);
  const t0 = Date.parse(`${d}T00:00:00Z`);
  return HORIZONS.map((h) => {
    const iso = new Date(t0 + h * 86400000).toISOString().slice(0, 10);
    return formatDate(iso, lang, {year: false, short: true});
  });
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
export function resolveHazardState(feed, {fetchFailed = false, nowMs = null, lang = 'en'} = {}) {
  const out = {
    state: 'unavailable', reason: null, stale: false, ageDays: null, issue_date: null,
    issue_label: null, horizon_labels: HORIZONS.map((h) => `+${h}`),
    generated_utc: null, bulletin_as_on: null, bulletin_label: null, record: null, disclaimer: null,
    dams: [], weather: [], reaches: [], snowmelt: null,
  };
  if (fetchFailed) { out.reason = 'fetch'; return out; }
  if (!feed || typeof feed !== 'object') {
    out.state = 'loading';
    return out;
  }
  // From here on the file arrived but is not a watch: a publishing fault,
  // which the page names as such rather than as a connection problem.
  out.reason = 'malformed';
  const issue = isoDate(feed.issue_date);
  if (issue === null) return out;
  if (!feed.dams || typeof feed.dams !== 'object') return out;

  const dams = DAMS.map((n) => damRow(n, feed.dams[n])).filter(Boolean);
  if (dams.length === 0) return out;
  out.reason = null;

  out.state = 'watch';
  out.issue_date = issue;
  out.issue_label = formatDate(issue, lang);
  out.horizon_labels = horizonLabels(issue, lang);
  out.generated_utc = typeof feed.generated_utc === 'string' ? feed.generated_utc : null;
  out.record = typeof feed.record === 'string' ? feed.record : null;
  out.disclaimer = typeof feed.disclaimer === 'string' ? feed.disclaimer : null;
  const b = feed.bulletin && typeof feed.bulletin === 'object' ? feed.bulletin : {};
  out.bulletin_as_on = typeof b.as_on_date === 'string'
    ? (typeof b.as_on_time === 'string' ? `${b.as_on_date} ${b.as_on_time}` : b.as_on_date)
    : null;
  out.bulletin_label = formatBulletinAsOn(b.as_on_date, b.as_on_time, lang);
  out.ageDays = issueAgeDays(issue, nowMs);
  out.stale = out.ageDays !== null && out.ageDays > MAX_ISSUE_AGE_DAYS;
  out.dams = dams.map((d) => ({...d, label: localName(d.name, lang)}));
  const wx = feed.weather && typeof feed.weather === 'object' ? feed.weather : {};
  out.weather = Object.keys(wx).sort().map((n) => weatherRow(n, wx[n])).filter(Boolean)
    .map((w) => ({...w, label: localName(w.name, lang)}));
  out.reaches = (Array.isArray(feed.reaches) ? feed.reaches.map(reachRow).filter(Boolean) : [])
    .map((r) => ({
      ...r,
      label: localName(r.station, lang),
      river_label: r.river ? localName(r.river, lang) : null,
      peak_label: r.peak_date ? formatDate(r.peak_date, lang) : null,
      cls_label: WRD_CLASSES.includes(r.cls) ? classLabel(r.cls, lang) : null,
    }));
  out.snowmelt = snowmeltSummary(feed.dams.Bhakra);
  return out;
}
