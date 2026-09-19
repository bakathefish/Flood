// node --test webapp/src/hazardSchema.test.mjs
//
// The hazard watch validator decides whether the river watch renders and what
// each cell says. Both directions: a broken feed must not print a calm number,
// and the real committed feed must not be rejected.

import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, join} from 'node:path';

import {
  damRow,
  issueAgeDays,
  reachRow,
  resolveHazardState,
  spillwayProbabilities,
  weatherRow,
  MAX_ISSUE_AGE_DAYS,
  classLabel,
  formatBulletinAsOn,
  formatDate,
  horizonLabels,
  localName,
} from './hazardSchema.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const FEED = join(HERE, '..', '..', 'punjabflood', 'outputs', 'forecast', 'latest.json');

function ens(p) {
  const o = {};
  for (const h of [1, 2, 3, 4, 5]) o[String(h)] = {p_exhaustion_flood_scale: p};
  return o;
}

function feed(over = {}) {
  return {
    issue_date: '2026-09-19',
    generated_utc: '2026-09-19T09:22:31+00:00',
    record: '2026-09-19.json',
    disclaimer: 'Not an official warning.',
    bulletin: {as_on_date: '19-09-2026', as_on_time: '06:00'},
    dams: {
      Bhakra: {
        state: {level_ft: 1644.77, inflow_cusecs: 23825, outflow_cusecs: 26500, basis: 'bbmb'},
        storage_fraction: 0.6687,
        ensemble: ens(0.0),
        snowmelt: {applied: true, melt_mm_recent: [0.3, 0.2], melt_mm_forecast: [0.1], pack_mm_issue: 421},
      },
      Pong: {state: {level_ft: 1371.56}, storage_fraction: 0.748, ensemble: ens(0.12)},
    },
    weather: {
      Bhakra: {level: 'quiet', primary_model: 'm', observed: {days: ['a', 'b'], total_mm: 21.2},
        forecast: {three_day_mm: {m: 1.1}, three_day_percentile: {m: 6}}},
    },
    reaches: [{station: 'Dhilwan', river: 'Beas', peak_cusecs: 6398, peak_date: '2026-09-21', peak_class: null}],
    ...over,
  };
}

test('fetch failure is unavailable, no feed is loading', () => {
  assert.equal(resolveHazardState(null, {fetchFailed: true}).state, 'unavailable');
  assert.equal(resolveHazardState(null).state, 'loading');
  assert.equal(resolveHazardState(undefined).state, 'loading');
});

test('a well-formed feed resolves to a watch with its dams in order', () => {
  const r = resolveHazardState(feed(), {nowMs: Date.parse('2026-09-19T12:00:00Z')});
  assert.equal(r.state, 'watch');
  assert.equal(r.stale, false);
  assert.equal(r.ageDays, 0);
  assert.deepEqual(r.dams.map((d) => d.name), ['Bhakra', 'Pong']);
  assert.equal(r.dams[0].level_ft, 1644.77);
  assert.deepEqual(r.dams[1].p, [0.12, 0.12, 0.12, 0.12, 0.12]);
  assert.equal(r.bulletin_as_on, '19-09-2026 06:00');
  assert.equal(r.record, '2026-09-19.json');
  assert.equal(r.snowmelt.applied, true);
  assert.equal(r.snowmelt.pack_mm, 421);
  assert.ok(Math.abs(r.snowmelt.recent_mm - 0.5) < 1e-9);
  assert.equal(r.weather[0].level, 'quiet');
  assert.equal(r.weather[0].next3_mm, 1.1);
  assert.equal(r.reaches[0].cls, 'below');
});

test('a missing or malformed probability is null, never zero', () => {
  const p = spillwayProbabilities({ensemble: {'1': {p_exhaustion_flood_scale: 'x'}, '3': {p_exhaustion_flood_scale: 1.7}}});
  assert.deepEqual(p, [null, null, null, null, null]);
  assert.deepEqual(spillwayProbabilities({}), [null, null, null, null, null]);
});

test('a dam with no reading at all is dropped, and no dams means unavailable', () => {
  assert.equal(damRow('Bhakra', {state: {}, ensemble: {}}), null);
  assert.equal(resolveHazardState(feed({dams: {Bhakra: {}}})).state, 'unavailable');
  assert.equal(resolveHazardState(feed({dams: null})).state, 'unavailable');
  assert.equal(resolveHazardState(feed({issue_date: '19/09/2026'})).state, 'unavailable');
});

test('storage outside a physical range is unknown', () => {
  assert.equal(damRow('Pong', {state: {level_ft: 1}, storage_fraction: -0.2}).storage_fraction, null);
  assert.equal(damRow('Pong', {state: {level_ft: 1}, storage_fraction: 9}).storage_fraction, null);
});

test('an unknown watch level is shown as unknown, not quiet', () => {
  assert.equal(weatherRow('X', {level: 'calm'}).level, 'unknown');
  assert.equal(weatherRow('X', {level: 'alert'}).level, 'alert');
});

test('reach classes: null is below Low, a bad string is unknown', () => {
  assert.equal(reachRow({station: 's', peak_class: null}).cls, 'below');
  assert.equal(reachRow({station: 's', peak_class: 'High'}).cls, 'High');
  assert.equal(reachRow({station: 's', peak_class: 'severe'}).cls, 'unknown');
  assert.equal(reachRow({peak_class: null}), null);
});

test('an old watch is stale but still a watch', () => {
  const now = Date.parse('2026-09-19T00:00:00Z') + (MAX_ISSUE_AGE_DAYS + 1) * 86400000 + 1000;
  const r = resolveHazardState(feed(), {nowMs: now});
  assert.equal(r.state, 'watch');
  assert.equal(r.stale, true);
  assert.equal(r.ageDays, MAX_ISSUE_AGE_DAYS + 1);
  assert.equal(issueAgeDays('nope', now), null);
});

test('the committed feed resolves to a watch', () => {
  const j = JSON.parse(readFileSync(FEED, 'utf8'));
  const r = resolveHazardState(j, {nowMs: Date.parse(j.generated_utc)});
  assert.equal(r.state, 'watch');
  // the daily bulletin carries Bhakra and Pong; Ranjit Sagar has no public
  // daily bulletin, so the product has no dam row for it
  assert.deepEqual(r.dams.map((d) => d.name), ['Bhakra', 'Pong']);
  assert.equal(r.reaches.length, 6);
  assert.equal(r.weather.length, 8);
  assert.ok(r.record && r.record.endsWith('.json'));
  for (const d of r.dams) {
    assert.ok(d.level_ft !== null && d.storage_fraction !== null);
    assert.ok(d.p.every((x) => typeof x === 'number'));
  }
  assert.equal(r.snowmelt.applied, true);
});

test('dates are formatted once per language, and a non-ISO date is null', () => {
  assert.equal(formatDate('2026-09-19', 'en'), '19 Sep 2026');
  assert.equal(formatDate('2026-09-19', 'hi'), '19 सितंबर 2026');
  assert.equal(formatDate('2026-09-19', 'pa'), '19 ਸਤੰਬਰ 2026');
  assert.equal(formatDate('2026-01-05', 'en', {year: false, short: true}), '5 Jan');
  assert.equal(formatDate('19-09-2026', 'en'), null);
  assert.equal(formatDate('2026-13-01', 'en'), null);
  assert.equal(formatDate(null, 'en'), null);
});

test('the bulletin as-on date takes the same form as the issue date', () => {
  assert.equal(formatBulletinAsOn('19-09-2026', '06:00', 'en'), '19 Sep 2026 06:00');
  assert.equal(formatBulletinAsOn('19-09-2026', '06:00', 'pa'), '19 ਸਤੰਬਰ 2026 06:00');
  assert.equal(formatBulletinAsOn('19-09-2026', null, 'hi'), '19 सितंबर 2026');
  assert.equal(formatBulletinAsOn('Sept 19', '06:00', 'en'), 'Sept 19 06:00');
  assert.equal(formatBulletinAsOn(null, '06:00', 'en'), null);
});

test('horizon labels are the five calendar days after the issue date', () => {
  assert.deepEqual(horizonLabels('2026-09-28', 'en'), ['29 Sep', '30 Sep', '1 Oct', '2 Oct', '3 Oct']);
  assert.deepEqual(horizonLabels(null, 'en'), ['+1', '+2', '+3', '+4', '+5']);
});

test('names are shown in the reader’s script and fall back to the feed’s name', () => {
  assert.equal(localName('Pong', 'hi'), 'पौंग');
  assert.equal(localName('Ropar Head Works', 'pa'), 'ਰੋਪੜ ਹੈੱਡਵਰਕਸ');
  assert.equal(localName('Pong', 'en'), 'Pong');
  assert.equal(localName('New Station', 'hi'), 'New Station');
  assert.equal(classLabel('High', 'hi'), 'उच्च (High)');
  assert.equal(classLabel('Low', 'pa'), 'ਘੱਟ (Low)');
  assert.equal(classLabel('Medium', 'en'), 'Medium');
});

test('the resolver carries the labels for the requested language', () => {
  const r = resolveHazardState(feed({reaches: [{station: 'Dhilwan', river: 'Beas', peak_cusecs: 90000, peak_date: '2026-09-21', peak_class: 'High'}]}),
    {nowMs: Date.parse('2026-09-19T12:00:00Z'), lang: 'pa'});
  assert.equal(r.issue_label, '19 ਸਤੰਬਰ 2026');
  assert.equal(r.bulletin_label, '19 ਸਤੰਬਰ 2026 06:00');
  assert.deepEqual(r.horizon_labels, ['20 ਸਤੰ', '21 ਸਤੰ', '22 ਸਤੰ', '23 ਸਤੰ', '24 ਸਤੰ']);
  assert.equal(r.dams[1].label, 'ਪੌਂਗ');
  assert.equal(r.weather[0].label, 'ਭਾਖੜਾ');
  assert.equal(r.reaches[0].label, 'ਧਿਲਵਾਂ');
  assert.equal(r.reaches[0].river_label, 'ਬਿਆਸ');
  assert.equal(r.reaches[0].peak_label, '21 ਸਤੰਬਰ 2026');
  assert.equal(r.reaches[0].cls_label, 'ਉੱਚ (High)');
  const en = resolveHazardState(feed(), {nowMs: Date.parse('2026-09-19T12:00:00Z')});
  assert.equal(en.issue_label, '19 Sep 2026');
  assert.equal(en.dams[0].label, 'Bhakra');
  assert.equal(en.reaches[0].cls_label, null);
});

test('a malformed feed is unavailable for a named reason, a fetch failure for another', () => {
  assert.equal(resolveHazardState(null, {fetchFailed: true}).reason, 'fetch');
  assert.equal(resolveHazardState({issue_date: 'nope'}).reason, 'malformed');
  assert.equal(resolveHazardState(feed({dams: {}})).reason, 'malformed');
  assert.equal(resolveHazardState(feed()).reason, null);
});
