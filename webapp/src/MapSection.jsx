import React, {useState, useEffect} from 'react';
import {MapContainer, TileLayer, GeoJSON} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import {Section} from '@astryxdesign/core/Section';
import {VStack} from '@astryxdesign/core/VStack';
import {HStack} from '@astryxdesign/core/HStack';
import {Grid} from '@astryxdesign/core/Grid';
import {Text} from '@astryxdesign/core/Text';
import {Heading} from '@astryxdesign/core/Heading';
import {Divider} from '@astryxdesign/core/Divider';
import {Button} from '@astryxdesign/core/Button';
import {Slider} from '@astryxdesign/core/Slider';
import Papa from 'papaparse';

const MAP_T = {
  en: {
    no: '03', title: 'Explore the record',
    intro: 'Pull up any monsoon from 2015 to now and watch the water move — even the years the model was never trained on. Or switch to the decade of recurrence and the rupee impact. Hover to compare, click any district for the full breakdown.',
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

const TEAL = ['#17211f', '#1b4340', '#20706a', '#289c90', '#3ad0c0'];
const AMBER = ['#26200f', '#4d3b16', '#7d5f1f', '#ab8730', '#e2b955'];
const ORANGE = ['#261612', '#4d2717', '#7d3a1c', '#b0542c', '#e07a45'];
const RAMPS = {
  year: {cols: TEAL, stops: [0, 500, 1500, 4000, 8000]},
  freq: {cols: AMBER, stops: [0, 1, 2, 3, 4]},
  impact: {cols: ORANGE, stops: [0, 50, 150, 400, 900]},
  now: {cols: TEAL, stops: [0, 1, 3, 7, 15]},
};
const colorFor = (v, layer) => {
  const {cols, stops} = RAMPS[layer];
  let c = cols[0];
  stops.forEach((s, i) => { if (v >= s && (v > 0 || i === 0)) c = cols[i]; });
  return c;
};

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
      <Text type="supporting" color="secondary">{label}</Text>
      <Text hasTabularNumbers>{value}</Text>
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
    if (layer === 'impact') return +((stats[name] && stats[name].crop_var_inr) || 0) / 1e7;
    return +((now[name] && now[name].observed_km2) || 0);
  };
  const fmt = (v) => {
    if (layer === 'year') return `${Math.round(v).toLocaleString()} ha`;
    if (layer === 'freq') return `${v} / 11`;
    if (layer === 'impact') return `₹ ${Math.round(v).toLocaleString()} cr`;
    return `${v.toFixed(1)} km²`;
  };
  const legend = {year: t.lgYear, freq: t.lgFreq, impact: t.lgImp, now: t.lgNow}[layer];

  const styleFn = (f) => ({
    fillColor: colorFor(valueOf(f.properties.district), layer),
    fillOpacity: 0.88, color: '#39424e', weight: 1,
  });
  const onEach = (f, lyr) => {
    const name = f.properties.district;
    lyr.bindTooltip(`${name} · ${fmt(valueOf(name))}`, {sticky: true, direction: 'top'});
    lyr.on({
      mouseover: (e) => { e.target.setStyle({weight: 2, color: '#3ad0c0'}); e.target.bringToFront(); },
      mouseout: (e) => { e.target.setStyle({weight: 1, color: '#39424e'}); },
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
  const crore = s ? (+s.crop_var_inr / 1e7).toFixed(0) : null;
  const activeLabel = (LAYERS.find((L) => L.k === layer) || {}).label || '';
  const headDesc = layer === 'year' ? `${year} ${t.yr}` : activeLabel;

  return (
    <Section variant="transparent" padding={0} dividers={['bottom']}>
      <HStack justify="center" width="100%">
        <VStack width="100%" maxWidth={1080} paddingInline={4} paddingBlock={8} gap={5} hAlign="center" id="explore">
          <HStack gap={3} vAlign="center">
            <Text type="label" color="accent">{t.no}</Text>
            <Heading level={2}>{t.title}</Heading>
          </HStack>
          <VStack maxWidth={700}>
            <Text type="large" color="secondary">{t.intro}</Text>
          </VStack>
          <HStack gap={2} vAlign="center" wrap="wrap">
            {LAYERS.map((L) => (
              <Button key={L.k} variant={layer === L.k ? 'primary' : 'ghost'} onClick={() => setLayer(L.k)}>{L.label}</Button>
            ))}
          </HStack>
          {layer === 'year' && (
            <HStack gap={4} vAlign="center" wrap="wrap">
              <Text type="label" color="accent" hasTabularNumbers>{year}</Text>
              <VStack width={320} maxWidth="100%">
                <Slider label="Year" isLabelHidden value={year} min={2015} max={2025} step={1} valueDisplay="none" onChange={(v) => setYear(Array.isArray(v) ? v[0] : v)} />
              </VStack>
              <Text type="supporting" color="secondary">2015 – 2025</Text>
            </HStack>
          )}
          <Grid columns={{minWidth: 320, max: 2}} gap={5} align="stretch" width="100%">
            <div style={{height: 520, border: '1px solid var(--color-border-emphasized)', borderRadius: 'var(--radius-inner, 2px)', overflow: 'hidden', background: 'var(--color-background-surface)'}}>
              {ready && (
                <MapContainer center={[31.05, 75.4]} zoom={7} scrollWheelZoom={false} style={{height: '100%', width: '100%', background: 'transparent'}}>
                  <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" subdomains="abcd" attribution='&copy; OpenStreetMap &copy; CARTO' />
                  <GeoJSON key={layer + year + Object.keys(byYear).length + Object.keys(now).length} data={geo} style={styleFn} onEachFeature={onEach} />
                </MapContainer>
              )}
            </div>
            <VStack gap={3}>
              {sel ? (
                <>
                  <VStack gap={1}>
                    <Heading level={3}>{sel}</Heading>
                    <Text type="supporting" color="secondary">{headDesc}</Text>
                    <Text size="2xl" color="accent" hasTabularNumbers>{fmt(valueOf(sel))}</Text>
                  </VStack>
                  <VStack gap={0}>
                    <Divider />
                    <VStack paddingBlock={2}><Stat label={`${year} ${t.yr}`} value={selYearHa != null ? `${Math.round(selYearHa).toLocaleString()} ha` : '—'} /></VStack>
                    <Divider />
                    <VStack paddingBlock={2}><Stat label={t.rec} value={fq ? `${fq.seasons_with_fraction_gt1pct} / 11` : '—'} /></VStack>
                    {year === 2025 && (
                      <>
                        <Divider />
                        <VStack paddingBlock={2}><Stat label={t.crop} value={s ? `${Math.round(+s.crop_flooded_ha).toLocaleString()} ha` : '—'} /></VStack>
                        <Divider />
                        <VStack paddingBlock={2}><Stat label={t.val} value={crore ? `₹ ${(+crore).toLocaleString()} crore` : '—'} /></VStack>
                      </>
                    )}
                    <Divider />
                  </VStack>
                </>
              ) : (
                <VStack gap={2} justify="center" height="100%">
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
