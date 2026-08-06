// Schema validation for the published nowcast feed.
//
// Extracted from the component so it can be exercised directly. The rules here
// decide whether a live flood board is shown at all, and the failure mode of
// getting them wrong is a page that looks calm, so they are worth testing
// against real payloads rather than eyeballing inside JSX.
//
// Two principles:
//   * fail closed, never filter. Dropping a malformed row and rendering the
//     rest hides the fact that the feed is broken; if any row is wrong we do
//     not trust the board it belongs to.
//   * validate what is published, not what we wish were published. p_event is
//     serialised rounded to four places, so two genuinely different scores can
//     arrive equal and a strict monotonicity check would reject a correct
//     ranking. The rank field is the producer's authoritative order.

export const TIERS = ['watch', 'elevated', 'low'];

/** Strictly a JSON number. `+x` turns null, "" and false into 0 and true into
 *  1, so coercing before a finite check lets a malformed field arrive as a
 *  confident zero. */
export function num(x) {
  return typeof x === 'number' && Number.isFinite(x) ? x : null;
}

export function inRange(x, lo, hi) {
  const v = num(x);
  return v !== null && v >= lo && v <= hi ? v : null;
}

function isPositiveInt(x) {
  const v = num(x);
  return v !== null && Number.isInteger(v) && v >= 1;
}

/** Fields every row must satisfy whether or not it carries a score. */
function rowShapeOk(d) {
  if (!d || typeof d !== 'object' || Array.isArray(d)) return false;
  if (typeof d.district !== 'string' || d.district === '') return false;
  // coverage must be a real boolean: missing, null, "" or 0 previously slipped
  // through as "not literally false", i.e. treated as covered.
  if (typeof d.covered !== 'boolean') return false;
  for (const [field, hi] of [['observed_fraction_window', 1], ['observed_km2', 1e6]]) {
    if (d[field] !== null && d[field] !== undefined && inRange(d[field], 0, hi) === null) {
      return false;
    }
  }
  if (!('transparent_score' in d)) return false;
  if (d.transparent_score !== null && num(d.transparent_score) === null) return false;
  return true;
}

/** An uncovered district must carry no operational output at all, and must say
 *  so explicitly. A missing key is not the same as a null: it means the
 *  producer never spoke to the question, and a consumer that treats silence as
 *  "nothing to report" is the failure this whole file exists to prevent. */
function uncoveredRowOk(d) {
  for (const field of ['p_event', 'rank', 'tier', 'observed_km2', 'transparent_score']) {
    if (!(field in d)) return false;
    if (d[field] !== null) return false;
  }
  return true;
}

/** A covered, scored district must carry a complete, legal operational set. */
function scoredRowOk(d) {
  return inRange(d.p_event, 0, 1) !== null
    && TIERS.includes(d.tier)
    && isPositiveInt(d.rank);
}

export function hasScore(d) {
  return !!d && typeof d === 'object' && inRange(d.p_event, 0, 1) !== null;
}

/**
 * Validate the whole district list. Returns true only if EVERY row is legal —
 * including rows with no score, which used to be skipped and could therefore
 * smuggle an illegal tier or rank into a feed we then trusted.
 */
export function districtsAreValid(districts) {
  if (!Array.isArray(districts) || districts.length === 0) return false;
  const names = new Set();
  for (const d of districts) {
    if (!rowShapeOk(d)) return false;
    if (names.has(d.district)) return false; // duplicate district
    names.add(d.district);
    // every row must state its score, even to say it has none
    if (!('p_event' in d)) return false;
    if (!d.covered) {
      if (!uncoveredRowOk(d)) return false;
    } else if (d.p_event === null) {
      // covered but unscored: allowed, but it must claim no operational output
      for (const field of ['rank', 'tier', 'transparent_score']) {
        if (!(field in d) || d[field] !== null) return false;
      }
    } else if (!scoredRowOk(d)) {
      return false;
    }
  }
  return true;
}

/**
 * The scored rows as a ranking. Ranks must be exactly 1..N with no gaps or
 * repeats, and scores must not rise as rank worsens — compared with the
 * publication rounding as tolerance, because ties in the feed are expected.
 */
export function rankingIsCoherent(scored) {
  const n = scored.length;
  if (n === 0) return false;
  const ranks = scored.map((d) => num(d.rank));
  if (ranks.some((r) => r === null)) return false;
  const sorted = [...ranks].sort((a, b) => a - b);
  for (let i = 0; i < n; i += 1) if (sorted[i] !== i + 1) return false;

  // Rounding is monotonic: if the true score of rank i-1 is at least that of
  // rank i, the published values cannot invert. Ties therefore need no
  // tolerance, and allowing one was fail-open — it accepted a published score
  // of 0.0004 at rank 2 behind 0.0003 at rank 1, a real inversion.
  const byRank = [...scored].sort((a, b) => num(a.rank) - num(b.rank));
  for (let i = 1; i < n; i += 1) {
    if (num(byRank[i].p_event) > num(byRank[i - 1].p_event)) return false;
  }
  return true;
}

/**
 * Resolve what the forecast section should render. One place, so the states
 * stay mutually exclusive and the benign ones can never be reached by
 * accident.
 *
 * Returns {state, scored, unimaged, threshold} where state is one of
 * 'loading' | 'inactive' | 'unavailable' | 'board'.
 */
export function resolveForecastState(nc, {fetchFailed = false} = {}) {
  const out = {state: 'unavailable', scored: [], unimaged: [], threshold: null};
  if (fetchFailed) return out;
  if (!nc || typeof nc !== 'object') {
    out.state = 'loading';
    return out;
  }

  const fc = nc.forecast;
  const saysUnavailable = !!fc && typeof fc === 'object' && fc.status === 'unavailable';
  const feedFailed = typeof nc.notes === 'string' && nc.notes.startsWith('DEGRADED');

  // Out of season is benign, so it is never inferred from a feed reporting its
  // own failure, and never from an unknown (null) season flag.
  if (nc.core_season === false && !saysUnavailable && !feedFailed) {
    out.state = 'inactive';
    return out;
  }
  if (nc.core_season !== true || saysUnavailable || feedFailed) return out;

  if (!districtsAreValid(nc.districts)) return out;

  const scored = nc.districts.filter(hasScore)
    .sort((a, b) => num(a.rank) - num(b.rank));
  const unimaged = nc.districts.filter((d) => d.covered === false);
  if (scored.length === 0 || !rankingIsCoherent(scored)) {
    out.unimaged = unimaged;
    return out;
  }

  const threshold = fc && typeof fc === 'object' ? inRange(fc.alert_threshold, 0, 1) : null;
  if (threshold === null) {
    out.unimaged = unimaged;
    return out;
  }

  out.state = 'board';
  out.scored = scored;
  out.unimaged = unimaged;
  out.threshold = threshold;
  return out;
}
