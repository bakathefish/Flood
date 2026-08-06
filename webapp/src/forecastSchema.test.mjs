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
    observed_fraction_window: 0.0,
    observed_km2: 0.0,
    rank: 1,
    tier: 'elevated',
    transparent_score: 1.5,
    ...over,
  };
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
  if (nc.core_season !== true || !nc.forecast || nc.forecast.status === 'unavailable') {
    return; // artifact is legitimately in a non-board state
  }
  const {state} = resolveForecastState(nc);
  assert.equal(state, 'board', 'the committed feed must not fail closed');
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
    row({district: 'B', p_event: null, covered: false, rank: 2, tier: 'low', observed_km2: null}),
  ]), false);
});

test('an uncovered row keeps no operational output', () => {
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}),
    row({district: 'B', p_event: null, covered: false, rank: null, tier: null,
         transparent_score: null, observed_km2: null, observed_fraction_window: null}),
  ]), true);
});

test('a scored row marked uncovered is rejected', () => {
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}),
    row({district: 'B', rank: 2, covered: false}),
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
    row({district: 'C', p_event: null, covered: false, rank: null, tier: null,
         transparent_score: null, observed_km2: null, observed_fraction_window: null}),
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
    row({district: 'B', p_event: null, covered: false, rank: null, tier: null,
         transparent_score: 1.4, observed_km2: null, observed_fraction_window: null}),
  ]), false);
});

test('a covered but unscored row must claim no operational output', () => {
  const base = {district: 'B', p_event: null, covered: true, observed_km2: 0.0,
                observed_fraction_window: 0.0};
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}),
    {...base, rank: null, tier: null, transparent_score: null},
  ]), true);
  assert.equal(districtsAreValid([
    row({district: 'A', rank: 1}),
    {...base, rank: 2, tier: null, transparent_score: null},
  ]), false, 'an unscored row must not claim a rank');
});
