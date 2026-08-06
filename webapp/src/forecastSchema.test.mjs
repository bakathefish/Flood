// node --test webapp/src/forecastSchema.test.mjs
//
// Behavioural tests for the feed validator. These decide whether a live flood
// board renders, so both directions matter: a broken feed must not produce a
// board, and a correct feed must not be rejected. The second direction is not
// hypothetical — an over-strict rank check once rejected the real committed
// payload, which would have shown "forecast unavailable" on a working day.

import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, join} from 'node:path';

import {
  districtsAreValid,
  rankingIsCoherent,
  resolveForecastState,
} from './forecastSchema.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const ARTIFACT = join(HERE, '..', '..', 'monitor', 'nowcast.json');

function row(over = {}) {
  return {
    district: 'Firozpur',
    p_event: 0.0405,
    covered: true,
    acquisition_state: 'observed',
    acquisition_fraction: 1.0,
    observed_fraction_window: 0.0,
    observed_km2: 0.0,
    rank: 1,
    tier: 'elevated',
    transparent_score: 1.5,
    ...over,
  };
}

/** An uncovered row as the producer actually emits it: every operational field
 *  present and null, with the acquisition state that explains why. */
function uncoveredRow(over = {}) {
  return row({
    covered: false,
    acquisition_state: 'not_observed',
    acquisition_fraction: 0.0,
    p_event: null,
    rank: null,
    tier: null,
    observed_km2: null,
    observed_fraction_window: null,
    transparent_score: null,
    ...over,
  });
}

function feed(districts, over = {}) {
  return {
    core_season: true,
    notes: 'quiet',
    forecast: {alert_threshold: 0.7917, status: undefined},
    districts,
    ...over,
  };
}

// --------------------------------------------------------------------------
// the real committed payload must render
// --------------------------------------------------------------------------
test('the committed live feed produces a board', () => {
  const nc = JSON.parse(readFileSync(ARTIFACT, 'utf8'));
  const {state} = resolveForecastState(nc);
  // This used to return early whenever the artifact was not board-shaped, which
  // meant a feed that failed the schema passed the test that exists to catch
  // exactly that. Assert the state we resolved to instead of skipping: an
  // out-of-season artifact is legitimately 'inactive', but a validation failure
  // is 'unavailable' and must never pass silently.
  if (nc.core_season !== true) {
    assert.equal(state, 'inactive', 'out-of-season feed should resolve to inactive');
    return;
  }
  assert.equal(state, 'board', 'the committed in-season feed must not fail closed');
});

// --------------------------------------------------------------------------
// acquisition fields: they arrived after this validator was written and went
// unchecked, so a feed could contradict itself and still render
// --------------------------------------------------------------------------
test('an uncovered row cannot publish an observed flood fraction', () => {
  // The defect: observed_km2 was on the null-required list, its sibling
  // observed_fraction_window was not, so "nobody imaged this" and "87% of it
  // is under water" could ship on the same row and the map drew the second.
  assert.equal(
    districtsAreValid([uncoveredRow({observed_fraction_window: 0.87})]), false,
  );
});

test('covered must agree with the acquisition state', () => {
  assert.equal(
    districtsAreValid([row({covered: true, acquisition_state: 'not_observed'})]), false,
    'covered:true beside not_observed is a row lying about its own coverage',
  );
  assert.equal(
    districtsAreValid([uncoveredRow({acquisition_state: 'observed'})]), false,
    'covered:false beside observed is the same contradiction the other way',
  );
});

test('a row must state its acquisition at all', () => {
  const bare = row();
  delete bare.acquisition_state;
  assert.equal(districtsAreValid([bare]), false, 'missing acquisition_state must fail');

  const noFrac = row();
  delete noFrac.acquisition_fraction;
  assert.equal(districtsAreValid([noFrac]), false, 'missing acquisition_fraction must fail');

  assert.equal(
    districtsAreValid([row({acquisition_state: 'sort-of'})]), false,
    'an unknown acquisition state must fail rather than be trusted',
  );
  assert.equal(
    districtsAreValid([row({acquisition_fraction: 1.4})]), false,
    'a fraction outside [0,1] must fail',
  );
});

test('an uncovered row omitting a key is not the same as nulling it', () => {
  for (const field of [
    'p_event', 'rank', 'tier',
    'observed_km2', 'observed_fraction_window', 'transparent_score',
  ]) {
    const d = uncoveredRow();
    delete d[field];
    assert.equal(districtsAreValid([d]), false, `omitting ${field} must fail`);
  }
});

test('the producer-shaped uncovered row is accepted', () => {
  // The strictness above is worthless if it also rejects the real feed. This is
  // the shape sailaab/nowcast.py actually emits for a district nobody imaged.
  assert.equal(districtsAreValid([uncoveredRow()]), true);
});

test('tied rounded scores with valid ranks stay coherent', () => {
  // p_event is published rounded to 4dp, so genuinely different scores tie.
  const rows = [
    row({district: 'A', p_event: 0.0004, rank: 1}),
    row({district: 'B', p_event: 0.0003, rank: 2}),
    row({district: 'C', p_event: 0.0003, rank: 3}),
    row({district: 'D', p_event: 0.0003, rank: 4}),
  ];
  assert.equal(rankingIsCoherent(rows), true);
});

// --------------------------------------------------------------------------
// broken feeds must fail closed
// --------------------------------------------------------------------------
test('a genuinely rising score along rank order is rejected', () => {
  const rows = [
    row({district: 'A', p_event: 0.10, rank: 1}),
    row({district: 'B', p_event: 0.50, rank: 2}),
  ];
  assert.equal(rankingIsCoherent(rows), false);
});

test('ranks must be contiguous 1..N', () => {
  assert.equal(rankingIsCoherent([
    row({district: 'A', rank: 1}), row({district: 'B', rank: 3}),
  ]), false);
  assert.equal(rankingIsCoherent([
    row({district: 'A', rank: 2}), row({district: 'B', rank: 2}),
  ]), false);
});

test('a malformed row poisons the whole feed instead of being filtered out', () => {
  for (const bad of [
    {district: ''},
    {district: 'B', covered: null},
    {district: 'B', covered: 'yes'},
    {district: 'B', observed_km2: 'lots'},
    {district: 'B', observed_fraction_window: 4},
    {district: 'B', transparent_score: 'high'},
    null,
    'not a row',
  ]) {
    const rows = [row({district: 'A', rank: 1}),
                  bad && typeof bad === 'object' ? row({rank: 2, ...bad}) : bad];
    assert.equal(districtsAreValid(rows), false, JSON.stringify(bad));
  }
});

test('duplicate district names are rejected', () => {
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}), row({district: 'A', rank: 2}),
  ]), false);
});

test('an unscored row carrying a rank or tier is rejected', () => {
  // this row renders nowhere, but it means the feed disagrees with itself
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}),
    uncoveredRow({district: 'B', rank: 2, tier: 'low'}),
  ]), false);
});

test('an uncovered row keeps no operational output', () => {
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}),
    uncoveredRow({district: 'B'}),
  ]), true);
});

test('a scored row marked uncovered is rejected', () => {
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}),
    uncoveredRow({district: 'B', rank: 2, p_event: 0.02, tier: 'low'}),
  ]), false);
});

test('an unrecognised tier fails the board closed, it is not rendered', () => {
  const nc = feed([row({district: 'A', rank: 1, tier: 'catastrophic'})]);
  assert.equal(resolveForecastState(nc).state, 'unavailable');
});

test('out of season renders inactive, and never from a failed feed', () => {
  assert.equal(resolveForecastState(feed([row()], {core_season: false})).state, 'inactive');
  assert.equal(
    resolveForecastState(feed([row()], {core_season: false, notes: 'DEGRADED: boom'})).state,
    'unavailable', 'a crashed run must not read as off-season');
});

test('unknown season fails closed rather than rendering a board', () => {
  assert.equal(resolveForecastState(feed([row()], {core_season: null})).state, 'unavailable');
  const noKey = feed([row()]);
  delete noKey.core_season;
  assert.equal(resolveForecastState(noKey).state, 'unavailable');
});

test('a missing or invalid threshold fails closed', () => {
  assert.equal(resolveForecastState(feed([row()], {forecast: {}})).state, 'unavailable');
  assert.equal(
    resolveForecastState(feed([row()], {forecast: {alert_threshold: '0.79'}})).state,
    'unavailable');
  assert.equal(
    resolveForecastState(feed([row()], {forecast: {alert_threshold: 4}})).state,
    'unavailable');
});

test('an explicit unavailable status beats everything', () => {
  const nc = feed([row()], {forecast: {status: 'unavailable', alert_threshold: 0.79}});
  assert.equal(resolveForecastState(nc).state, 'unavailable');
});

test('a fetch failure is unavailable, not blank', () => {
  assert.equal(resolveForecastState(null, {fetchFailed: true}).state, 'unavailable');
});

test('no data yet is loading, which renders nothing', () => {
  assert.equal(resolveForecastState(null).state, 'loading');
});

test('uncovered districts are surfaced alongside a valid board', () => {
  const nc = feed([
    row({district: 'A', rank: 1}),
    row({district: 'B', rank: 2, p_event: 0.001}),
    uncoveredRow({district: 'C'}),
  ]);
  const {state, scored, unimaged} = resolveForecastState(nc);
  assert.equal(state, 'board');
  assert.equal(scored.length, 2);
  assert.deepEqual(unimaged.map((d) => d.district), ['C']);
});

// --------------------------------------------------------------------------
// rules added after round 16
// --------------------------------------------------------------------------
test('a one-quantum ranking inversion is rejected, ties are not', () => {
  // rounding is monotonic, so a published inversion is a real inversion
  assert.equal(rankingIsCoherent([
    row({district: 'A', p_event: 0.0003, rank: 1}),
    row({district: 'B', p_event: 0.0004, rank: 2}),
  ]), false, 'one-quantum inversion must fail');
  assert.equal(rankingIsCoherent([
    row({district: 'A', p_event: 0.0003, rank: 1}),
    row({district: 'B', p_event: 0.0003, rank: 2}),
  ]), true, 'an exact tie is legal');
});

test('a missing operational key is rejected, not read as null', () => {
  for (const drop of ['p_event', 'rank', 'tier', 'transparent_score']) {
    const bad = row({district: 'B', rank: 2});
    delete bad[drop];
    assert.equal(districtsAreValid([row({district: 'A', rank: 1}), bad]), false,
                 `missing ${drop} must fail`);
  }
});

test('an uncovered row holding a transparent_score is rejected', () => {
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}),
    uncoveredRow({district: 'B', transparent_score: 1.4}),
  ]), false);
});

test('a covered but unscored row must claim no operational output', () => {
  const base = row({district: 'B', p_event: null, observed_km2: 0.0,
                    observed_fraction_window: 0.0});
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}),
    {...base, rank: null, tier: null, transparent_score: null},
  ]), true);
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}),
    {...base, rank: 2, tier: null, transparent_score: null},
  ]), false, 'an unscored row must not claim a rank');
});

// --------------------------------------------------------------------------
// rules added after the contract review
// --------------------------------------------------------------------------
test('a tier that disagrees with the threshold fails the board', () => {
  // score clears 0.79 but claims a quiet tier: the feed contradicts itself and
  // the quieter statement is the one a reader believes
  const nc = feed([row({district: 'A', p_event: 0.95, rank: 1, tier: 'elevated'})]);
  assert.equal(resolveForecastState(nc).state, 'unavailable');

  const nc2 = feed([row({district: 'A', p_event: 0.95, rank: 1, tier: 'watch'})]);
  assert.equal(resolveForecastState(nc2).state, 'board');
});

test('a below-threshold row claiming watch also fails', () => {
  const nc = feed([row({district: 'A', p_event: 0.01, rank: 1, tier: 'watch'})]);
  assert.equal(resolveForecastState(nc).state, 'unavailable');
});

test('a covered but unscored district is surfaced, never dropped', () => {
  const nc = feed([
    row({district: 'A', rank: 1}),
    row({district: 'B', p_event: null, rank: null, tier: null,
         transparent_score: null, observed_km2: 3.2, observed_fraction_window: 0.01}),
  ]);
  const {state, scored, unimaged, unscored} = resolveForecastState(nc);
  assert.equal(state, 'board');
  assert.deepEqual(scored.map((d) => d.district), ['A']);
  assert.deepEqual(unimaged.map((d) => d.district), []);
  assert.deepEqual(unscored.map((d) => d.district), ['B'],
                   'an imaged district with no score must not vanish');
});

test('every district lands in exactly one group', () => {
  const nc = feed([
    row({district: 'A', rank: 1}),
    row({district: 'B', p_event: null, rank: null, tier: null,
         transparent_score: null, observed_km2: 1.0, observed_fraction_window: 0.0}),
    uncoveredRow({district: 'C'}),
  ]);
  const r = resolveForecastState(nc);
  const seen = [...r.scored, ...r.unimaged, ...r.unscored].map((d) => d.district);
  assert.equal(seen.length, 3, 'no district counted twice or lost');
  assert.deepEqual([...seen].sort(), ['A', 'B', 'C']);
});

test('a stale feed does not sit under a live board', () => {
  const nc = feed([row({district: 'A', rank: 1})],
                  {generated_utc: '2026-08-06T00:00:00Z'});
  const fresh = Date.parse('2026-08-06T03:00:00Z');
  const stale = Date.parse('2026-08-07T12:00:00Z');
  assert.equal(resolveForecastState(nc, {nowMs: fresh}).state, 'board');
  assert.equal(resolveForecastState(nc, {nowMs: stale}).state, 'unavailable');
});

test('staleness is not enforced when no clock is supplied', () => {
  const nc = feed([row({district: 'A', rank: 1})],
                  {generated_utc: '2020-01-01T00:00:00Z'});
  assert.equal(resolveForecastState(nc).state, 'board');
});
