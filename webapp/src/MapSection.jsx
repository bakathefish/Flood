import React, {useState, useEffect} from 'react';
import {MapContainer, TileLayer, GeoJSON, useMap} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {Section} from '@astryxdesign/core/Section';
import {VStack} from '@astryxdesign/core/VStack';
import {HStack} from '@astryxdesign/core/HStack';
import {Grid} from '@astryxdesign/core/Grid';
import {Text} from '@astryxdesign/core/Text';
import {Heading} from '@astryxdesign/core/Heading';
import {Divider} from '@astryxdesign/core/Divider';
import {Slider} from '@astryxdesign/core/Slider';
import {SegmentedControl} from '@astryxdesign/core/SegmentedControl';
import {SegmentedControlItem} from '@astryxdesign/core/SegmentedControl';
import Papa from 'papaparse';
import {dataColors} from './theme';

const MAP_T = {
  en: {
    no: '03', title: 'Explore the record',
    intro: 'Pull up any monsoon from 2015 to now and watch the water move, even the years the model was never trained on. Or switch to the decade of recurrence and the rupee impact. Hover to compare, click any district for the full breakdown.',
    year: 'Flood by year', freq: 'Decade recurrence', impact: 'Impact (₹)', now: 'Live now (2026)',
    hint: 'Click a district for its numbers.',
    lgYear: 'Hectares flooded that monsoon', lgFreq: 'Seasons flooded ≥1%, 2015–25 (of 11)',
    lgImp: 'Crop value at risk, ₹ crore (2025)', lgNow: 'Water observed this window, km² (live)',
    yr: 'flooded', crop: 'Cropland flooded 2025', val: 'Crop value at risk 2025', rec: 'Seasons flooded, 2015–25', obs: 'Water this window (live)',
  },
  hi: {
    no: '03', title: 'रिकॉर्ड देखें',
    intro: '2015 से अब तक का कोई भी मानसून चुनें और पानी को चलते देखें — वे साल भी जिन पर मॉडल कभी प्रशिक्षित नहीं हुआ। या दशक की पुनरावृत्ति और रुपये में प्रभाव पर जाएँ। तुलना के लिए होवर करें, पूरा विवरण देखने के लिए किसी ज़िले पर क्लिक करें।',
    year: 'साल दर साल बाढ़', freq: 'दशक पुनरावृत्ति', impact: 'प्रभाव (₹)', now: 'अभी लाइव (2026)',
    hint: 'ज़िले के आँकड़ों के लिए उस पर क्लिक करें।',
    lgYear: 'उस मानसून में जलमग्न हेक्टेयर', lgFreq: '≥1% जलमग्न मौसम, 2015–25 (11 में से)',
    lgImp: 'फ़सल मूल्य जोखिम में, ₹ करोड़ (2025)', lgNow: 'इस विंडो में देखा गया जल, km² (लाइव)',
    yr: 'जलमग्न', crop: '2025 जलमग्न फ़सली भूमि', val: '2025 फ़सल मूल्य जोखिम में', rec: 'जलमग्न मौसम, 2015–25', obs: 'इस विंडो में जल (लाइव)',
  },
  pa: {
    no: '03', title: 'ਰਿਕਾਰਡ ਵੇਖੋ',
    intro: '2015 ਤੋਂ ਹੁਣ ਤੱਕ ਕੋਈ ਵੀ ਮਾਨਸੂਨ ਚੁਣੋ ਅਤੇ ਪਾਣੀ ਨੂੰ ਚੱਲਦਾ ਵੇਖੋ — ਉਹ ਸਾਲ ਵੀ ਜਿਨ੍ਹਾਂ ਉੱਤੇ ਮਾਡਲ ਕਦੇ ਸਿਖਲਾਈ ਨਹੀਂ ਹੋਇਆ। ਜਾਂ ਦਹਾਕੇ ਦੀ ਮੁੜ-ਆਵਰਤੀ ਤੇ ਰੁਪਏ ਵਿੱਚ ਪ੍ਰਭਾਵ ਉੱਤੇ ਜਾਓ। ਤੁਲਨਾ ਲਈ ਹੋਵਰ ਕਰੋ, ਪੂਰਾ ਵੇਰਵਾ ਵੇਖਣ ਲਈ ਕਿਸੇ ਜ਼ਿਲ੍ਹੇ ਉੱਤੇ ਕਲਿੱਕ ਕਰੋ।',
    year: 'ਸਾਲ-ਦਰ-ਸਾਲ ਹੜ੍ਹ', freq: 'ਦਹਾਕਾ ਮੁੜ-ਆਵਰਤੀ', impact: 'ਪ੍ਰਭਾਵ (₹)', now: 'ਹੁਣ ਲਾਈਵ (2026)',
    hint: 'ਜ਼ਿਲ੍ਹੇ ਦੇ ਅੰਕੜਿਆਂ ਲਈ ਉਸ ਉੱਤੇ ਕਲਿੱਕ ਕਰੋ।',
    lgYear: 'ਉਸ ਮਾਨਸੂਨ ਵਿੱਚ ਡੁੱਬੇ ਹੈਕਟੇਅਰ', lgFreq: '≥1% ਡੁੱਬੇ ਮੌਸਮ, 2015–25 (11 ਵਿੱਚੋਂ)',
    lgImp: 'ਫ਼ਸਲ ਮੁੱਲ ਜੋਖਮ ਵਿੱਚ, ₹ ਕਰੋੜ (2025)', lgNow: 'ਇਸ ਵਿੰਡੋ ਵਿੱਚ ਵੇਖਿਆ ਪਾਣੀ, km² (ਲਾਈਵ)',
    yr: 'ਡੁੱਬਿਆ', crop: '2025 ਡੁੱਬੀ ਫ਼ਸਲੀ ਜ਼ਮੀਨ', val: '2025 ਫ਼ਸਲ ਮੁੱਲ ਜੋਖਮ ਵਿੱਚ', rec: 'ਡੁੱਬੇ ਮੌਸਮ, 2015–25', obs: 'ਇਸ ਵਿੰਡੋ ਵਿੱਚ ਪਾਣੀ (ਲਾਈਵ)',
  },
};

// Ramps run light to dark on paper, the reverse of the old dark-mode set.
// Each was checked against the page surface with the dataviz validator: the
// old pale ends sat at 1.12:1 here and would have vanished into the sheet.
const RAMPS = {
  year: {cols: dataColors.water, stops: [0, 500, 1500, 4000, 8000]},
  freq: {cols: dataColors.recurrence, stops: [0, 1, 2, 3, 4]},
  impact: {cols: dataColors.impact, stops: [0, 50, 150, 400, 900]},
  now: {cols: dataColors.water, stops: [0, 1, 3, 7, 15]},
};

// A district with no observation is drawn as a hatch on bare paper, not as a
// tint. The ramp's lowest colour would mean "we looked and there was almost
// nothing", which is the opposite of what a null means — and a neutral grey
// cannot be told apart from the ochre ramp by colour alone (dE 7.4, well
// under the 15 floor), so the distinction has to be carried by texture.
const NO_DATA_PATTERN_ID = 'sailaab-nodata';
const NO_DATA_FILL = `url(#${NO_DATA_PATTERN_ID})`;

const colorFor = (v, layer) => {
  if (v === null || v === undefined) return NO_DATA_FILL;
  const {cols, stops} = RAMPS[layer];
  let c = cols[0];
  stops.forEach((s, i) => { if (v >= s && (v > 0 || i === 0)) c = cols[i]; });
  return c;
};

// Leaflet draws vectors into a single <svg> in the overlay pane. Dropping a
// <defs> in there once gives every no-data district a real hatch fill, which
// no amount of tinting could achieve legibly.
function NoDataHatch() {
  const map = useMap();
  useEffect(() => {
    const pane = map.getPane('overlayPane');
    if (!pane) return;
    let stop = false;
    const install = () => {
      if (stop) return;
      const svg = pane.querySelector('svg');
      if (!svg) { requestAnimationFrame(install); return; }
      if (svg.querySelector(`#${NO_DATA_PATTERN_ID}`)) return;
      const NS = 'http://www.w3.org/2000/svg';
      const defs = document.createElementNS(NS, 'defs');
      const pat = document.createElementNS(NS, 'pattern');
      pat.setAttribute('id', NO_DATA_PATTERN_ID);
      pat.setAttribute('patternUnits', 'userSpaceOnUse');
      pat.setAttribute('width', '6');
      pat.setAttribute('height', '6');
      pat.setAttribute('patternTransform', 'rotate(45)');
      const bg = document.createElementNS(NS, 'rect');
      bg.setAttribute('width', '6');
      bg.setAttribute('height', '6');
      bg.setAttribute('fill', '#FBF9F4');
      const line = document.createElementNS(NS, 'line');
      line.setAttribute('x1', '0');
      line.setAttribute('y1', '0');
      line.setAttribute('x2', '0');
      line.setAttribute('y2', '6');
      line.setAttribute('stroke', dataColors.noDataHatch);
      line.setAttribute('stroke-width', '1.5');
      pat.appendChild(bg);
      pat.appendChild(line);
      defs.appendChild(pat);
      svg.insertBefore(defs, svg.firstChild);
    };
    install();
    return () => { stop = true; };
  }, [map]);
  return null;
}

// With the map on the full measure a fixed zoom left Punjab small and adrift
// in the middle of the frame. Fitting the state's own bounds makes the
// subject fill the plate at any container width.
function FitToState({geo}) {
  const map = useMap();
  useEffect(() => {
    if (!geo) return;
    const layer = L.geoJSON(geo);
    const bounds = layer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, {padding: [18, 18]});
  }, [map, geo]);
  return null;
}

// the map geometry names one district differently from every data feed
const ALIAS = {'Shahid Bhagat Singh Nagar': 'Nawanshahr'};
const dn = (g) => ALIAS[g] || g;

async function loadCsv(url) {
  const text = await (await fetch(url)).text();
  return Papa.parse(text, {header: true, skipEmptyLines: true}).data;
}

function Stat({label, value}) {
  return (
    <HStack justify="between" vAlign="baseline" gap={4}>
      <Text type="label" color="secondary">{label}</Text>
      <Text type="code" color="primary" hasTabularNumbers>{value}</Text>
    </HStack>
  );
}

export default function MapSection({lang}) {
  const t = MAP_T[lang] || MAP_T.en;
  const [geo, setGeo] = useState(null);
  const [stats, setStats] = useState({});
  const [freq, setFreq] = useState({});
  const [byYear, setByYear] = useState({});
  const [now, setNow] = useState({});
  const [layer, setLayer] = useState('year');
  const [year, setYear] = useState(2025);
  const [sel, setSel] = useState(null);

  useEffect(() => {
    let on = true;
    fetch('assets/punjab_districts.json').then((r) => r.json()).then((g) => on && setGeo(g)).catch(() => {});
    loadCsv('assets/district_flood_stats_2025.csv').then((rows) => {
      if (!on) return;
      const m = {}; rows.forEach((d) => (m[d.district] = d)); setStats(m);
    }).catch(() => {});
    loadCsv('assets/flood_frequency_districts_late_season.csv').then((rows) => {
      if (!on) return;
      const m = {}; rows.forEach((d) => (m[d.district] = d)); setFreq(m);
    }).catch(() => {});
    loadCsv('assets/gfm_district_window_fractions_2015_2025.csv').then((rows) => {
      if (!on) return;
      const by = {};
      rows.forEach((d) => {
        const y = d.year, dist = d.district, ha = +d.flooded_ha || 0;
        by[y] = by[y] || {};
        if (!(dist in by[y]) || ha > by[y][dist]) by[y][dist] = ha; // peak window that year
      });
      setByYear(by);
    }).catch(() => {});
    fetch('https://raw.githubusercontent.com/bakathefish/Flood/master/monitor/nowcast.json')
      .then((r) => r.json())
      .then((j) => {
        if (!on) return;
        const m = {}; (j.districts || []).forEach((d) => (m[d.district] = d)); setNow(m);
      }).catch(() => {});
    return () => { on = false; };
  }, []);

  const ready = geo && Object.keys(stats).length > 0;
  const valueOf = (raw) => {
    const name = dn(raw);
    if (layer === 'year') return +((byYear[year] && byYear[year][name]) || 0);
    if (layer === 'freq') return +((freq[name] && freq[name].seasons_with_fraction_gt1pct) || 0);
    if (layer === 'impact') return +((stats[name] && (stats[name].crop_var_inr_v2 || stats[name].crop_var_inr)) || 0) / 1e7;
    // The live layer is the one place a null must survive. A district the
    // satellite never imaged has no water figure, and `|| 0` was painting it
    // the same colour as a district that was imaged and found dry. null here
    // means unknown, and every caller below has to handle it.
    const row = now[name];
    if (!row) return null;
    if (row.covered === false) return null;
    const km2 = row.observed_km2;
    return typeof km2 === 'number' && Number.isFinite(km2) ? km2 : null;
  };
  const fmt = (v) => {
    if (v === null) return 'not imaged';
    if (layer === 'year') return `${Math.round(v).toLocaleString()} ha`;
    if (layer === 'freq') return `${v} / 11`;
    if (layer === 'impact') return `₹ ${Math.round(v).toLocaleString()} cr`;
    return `${v.toFixed(1)} km²`;
  };
  const legend = {year: t.lgYear, freq: t.lgFreq, impact: t.lgImp, now: t.lgNow}[layer];

  const styleFn = (f) => {
    const unobserved = valueOf(f.properties.district) === null;
    return {
      fillColor: colorFor(valueOf(f.properties.district), layer),
      // dashed outline so an unobserved district reads as unknown at a
      // glance, not merely as a slightly different shade of calm. Paired
      // with the hatch fill, it is unmistakable at any zoom.
      dashArray: unobserved ? '4 3' : undefined,
      fillOpacity: unobserved ? 1 : 0.9,
      color: dataColors.mapOutline,
      weight: unobserved ? 1.25 : 0.75,
    };
  };
  const onEach = (f, lyr) => {
    const name = f.properties.district;
    const unobserved = valueOf(name) === null;
    lyr.bindTooltip(`${name} · ${fmt(valueOf(name))}`, {sticky: true, direction: 'top'});
    lyr.on({
      mouseover: (e) => { e.target.setStyle({weight: 2.5, color: dataColors.mapHover}); e.target.bringToFront(); },
      mouseout: (e) => { e.target.setStyle({weight: unobserved ? 1.25 : 0.75, color: dataColors.mapOutline}); },
      click: () => setSel(name),
    });
  };

  const LAYERS = [
    {k: 'year', label: t.year},
    {k: 'freq', label: t.freq},
    {k: 'impact', label: t.impact},
    {k: 'now', label: t.now},
  ];
  const s = sel ? stats[dn(sel)] : null;
  const n = sel ? now[dn(sel)] : null;
  const fq = sel ? freq[dn(sel)] : null;
  const selYearHa = sel && byYear[year] ? byYear[year][dn(sel)] : null;
  const crore = s ? (+((s.crop_var_inr_v2 || s.crop_var_inr)) / 1e7).toFixed(0) : null;
  const activeLabel = (LAYERS.find((L) => L.k === layer) || {}).label || '';
  const headDesc = layer === 'year' ? `${year} ${t.yr}` : activeLabel;

  return (
    <Section variant="transparent" padding={0} dividers={['bottom']}>
      <HStack justify="center" width="100%">
        <VStack width="100%" maxWidth={1120} paddingInline={4} paddingBlock={8} gap={6} hAlign="start" id="explore">
          <VStack width="100%" gap={3}>
            <Divider />
            <HStack gap={4} vAlign="baseline" wrap="wrap" paddingBlock={1}>
              <Text type="code" color="accent">{t.no}</Text>
              <Heading level={2}>{t.title}</Heading>
            </HStack>
          </VStack>
          <VStack maxWidth={660}>
            <Text type="large" color="secondary">{t.intro}</Text>
          </VStack>
          {/* One row of controls above the map, which is where a reader
              looks for them and where they stop competing with the data. */}
          <HStack gap={4} vAlign="center" wrap="wrap" width="100%">
            <SegmentedControl label={t.title} size="sm" value={layer} onChange={setLayer}>
              {LAYERS.map((L) => (
                <SegmentedControlItem key={L.k} value={L.k} label={L.label} />
              ))}
            </SegmentedControl>
            {layer === 'year' && (
              <HStack gap={3} vAlign="center" wrap="wrap">
                <Text type="code" color="primary" size="lg" hasTabularNumbers>{year}</Text>
                <VStack width={260} maxWidth="100%">
                  <Slider label="Year" isLabelHidden value={year} min={2015} max={2025} step={1} valueDisplay="none" onChange={(v) => setYear(Array.isArray(v) ? v[0] : v)} />
                </VStack>
                <Text type="supporting" color="secondary">2015 – 2025</Text>
              </HStack>
            )}
          </HStack>
          {/* Punjab is a tall, narrow state, so the plate is portrait: given
              the full measure the geometry fitted to height and left two
              thirds of the frame empty. The read-out sits in the column
              beside it, which is also where a reader's eye already is after
              clicking a district. */}
          <Grid columns={{minWidth: 360, max: 2}} gap={6} align="start" width="100%">
            <div style={{height: 600, border: '1px solid var(--color-border-emphasized)', borderRadius: 'var(--radius-inner, 2px)', overflow: 'hidden', background: 'var(--color-background-surface)'}}>
              {/* zoomSnap 0 lets fitBounds land on a fractional zoom.
                  Leaflet's default integer snap was throwing away up to half
                  the plate, which is why the state sat small in the middle of
                  its own frame. */}
              {ready && (
                <MapContainer center={[31.05, 75.4]} zoom={7} zoomSnap={0} zoomDelta={0.5} scrollWheelZoom={false} style={{height: '100%', width: '100%', background: 'transparent'}}>
                  {/* A pale basemap so the choropleth carries the colour and
                      the terrain stays reference, which is the way every
                      newsroom draws a district map. */}
                  <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" subdomains="abcd" attribution='&copy; OpenStreetMap &copy; CARTO' />
                  <NoDataHatch />
                  <FitToState geo={geo} />
                  <GeoJSON key={layer + year + Object.keys(byYear).length + Object.keys(now).length} data={geo} style={styleFn} onEachFeature={onEach} />
                </MapContainer>
              )}
            </div>
            <VStack gap={3} width="100%">
              {sel ? (
                <VStack width="100%" gap={0}>
                  <Divider />
                  <HStack justify="between" vAlign="baseline" gap={5} wrap="wrap" paddingBlock={4}>
                    <VStack gap={1}>
                      <Heading level={3}>{sel}</Heading>
                      <Text type="label" color="secondary">{headDesc}</Text>
                    </VStack>
                    <Text type="figure" color="primary">{fmt(valueOf(sel))}</Text>
                  </HStack>
                  <Divider />
                  <VStack paddingBlock={3}><Stat label={`${year} ${t.yr}`} value={selYearHa != null ? `${Math.round(selYearHa).toLocaleString()} ha` : '—'} /></VStack>
                  <Divider />
                  <VStack paddingBlock={3}><Stat label={t.rec} value={fq ? `${fq.seasons_with_fraction_gt1pct} / 11` : '—'} /></VStack>
                  {year === 2025 && (
                    <>
                      <Divider />
                      <VStack paddingBlock={3}><Stat label={t.crop} value={s ? `${Math.round(+s.crop_flooded_ha).toLocaleString()} ha` : '—'} /></VStack>
                      <Divider />
                      <VStack paddingBlock={3}><Stat label={t.val} value={crore ? `₹ ${(+crore).toLocaleString()} crore` : '—'} /></VStack>
                    </>
                  )}
                  <Divider />
                </VStack>
              ) : (
                <VStack gap={2} width="100%">
                  <Text color="secondary">{t.hint}</Text>
                  <Text type="supporting" color="secondary">{legend}</Text>
                </VStack>
              )}
            </VStack>
          </Grid>
        </VStack>
      </HStack>
    </Section>
  );
}
