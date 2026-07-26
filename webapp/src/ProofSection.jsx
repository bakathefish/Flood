import React, {useState, useEffect} from 'react';
import Papa from 'papaparse';
import {ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, LabelList} from 'recharts';
import {Section} from '@astryxdesign/core/Section';
import {VStack} from '@astryxdesign/core/VStack';
import {HStack} from '@astryxdesign/core/HStack';
import {Grid} from '@astryxdesign/core/Grid';
import {Text} from '@astryxdesign/core/Text';
import {Heading} from '@astryxdesign/core/Heading';
import {Card} from '@astryxdesign/core/Card';
import {Link} from '@astryxdesign/core/Link';

const REPO = 'https://github.com/bakathefish/Flood';
const RAW = 'https://raw.githubusercontent.com/bakathefish/Flood/master/';
const AXIS = '#8a93a0', GRID = '#2b313b', TIP_BG = '#1b2027', TIP_BD = '#3a414c', TIP_FG = '#e6e9ee', FLOODED = '#3ad0c0', DRY = '#565f6b';

async function loadCsv(url) {
  const text = await (await fetch(url)).text();
  return Papa.parse(text, {header: true, skipEmptyLines: true}).data;
}

const PRED_T = {
  en: {title: 'Predicted flood risk by district, held out to 2025', cap: 'Each bar is the district’s peak predicted probability across the 2025 windows, from a model trained only on 2015 to 2024. Teal flooded, grey did not. It ranked the flooded districts on top.'},
  hi: {title: 'ज़िलेवार अनुमानित बाढ़ जोखिम, 2025 पर होल्ड-आउट', cap: 'हर बार 2025 की विंडोज़ में ज़िले की उच्चतम अनुमानित संभावना है, केवल 2015 से 2024 पर प्रशिक्षित मॉडल से। टील डूबे, ग्रे नहीं। इसने डूबे ज़िलों को शीर्ष पर रखा।'},
  pa: {title: 'ਜ਼ਿਲ੍ਹਾ-ਵਾਰ ਅਨੁਮਾਨਿਤ ਹੜ੍ਹ ਖ਼ਤਰਾ, 2025 ਉੱਤੇ ਹੋਲਡ-ਆਊਟ', cap: 'ਹਰ ਬਾਰ 2025 ਦੀਆਂ ਵਿੰਡੋਜ਼ ਵਿੱਚ ਜ਼ਿਲ੍ਹੇ ਦੀ ਸਭ ਤੋਂ ਵੱਧ ਅਨੁਮਾਨਿਤ ਸੰਭਾਵਨਾ ਹੈ, ਸਿਰਫ਼ 2015 ਤੋਂ 2024 ਉੱਤੇ ਸਿਖਲਾਈ ਮਾਡਲ ਤੋਂ। ਟੀਲ ਡੁੱਬੇ, ਸਲੇਟੀ ਨਹੀਂ। ਇਸ ਨੇ ਡੁੱਬੇ ਜ਼ਿਲ੍ਹਿਆਂ ਨੂੰ ਸਿਖਰ ’ਤੇ ਰੱਖਿਆ।'},
};

const P_T = {
  en: {
    eyebrow: 'Proof · held out to 2025',
    title: 'Graded by the worst flood since 1988',
    intro: 'The forecast and the maps were trained on 2015–24, then handed 2025 — a year they had never seen — and let it grade them. Every satellite claim is gated by a number written down before the run, with PASS or FAIL shipped either way.',
    stats: [
      {v: '81.7%', l: 'of mapped flood pixels confirmed by a different satellite (Sentinel-2 optical, 237 truth points). Pre-declared gate: 60%.'},
      {v: 'ρ = 0.72', l: 'rank agreement between our 2025 satellite damage map and the government’s Special Girdawari survey across all 20 districts (0.56 over the 16 named).'},
      {v: '450+', l: 'automated tests, written before the code they check.'},
      {v: '3', l: 'cross-checks: Sentinel-2 optical (different sensor), the government ground survey, and Copernicus GFM (different algorithm, which also seeded the labels).'},
    ],
    honesty: 'We also benchmarked an imported deep-learning U-Net: it scored IoU 0.63 in the lab but under-segmented Punjab badly (recall 0.24). Our simpler stack beat it, and we published that result instead of hiding it. Failures ship in the verification log too.',
    take: 'Take the documents',
    links: [
      {t: 'Method paper — every threshold, model, and validation', u: REPO + '/blob/master/docs/METHOD.md'},
      {t: 'Verification log — pre-declared bands, actuals, PASS/FAIL', u: REPO + '/blob/master/docs/VERIFICATION-LOG.md'},
      {t: '20 district briefs — one printable page per DC office', u: REPO + '/tree/master/briefs'},
      {t: 'Synopsis (PDF) — the whole project in 5 pages', u: RAW + 'docs/SAILAAB-synopsis.pdf'},
      {t: 'Sustainability & deployment plan (PDF)', u: RAW + 'docs/SAILAAB-business-plan.pdf'},
      {t: 'Source code (MIT) — reproduce every number', u: REPO},
    ],
  },
  hi: {
    eyebrow: 'प्रमाण · 2025 पर होल्ड-आउट',
    title: '1988 के बाद की सबसे भीषण बाढ़ ने परखा',
    intro: 'पूर्वानुमान और नक्शे 2015–24 पर प्रशिक्षित हुए, फिर 2025 — जो उन्होंने कभी नहीं देखा था — सौंपा गया और उसी ने परखा। हर सैटेलाइट दावा रन से पहले लिखी गई संख्या से बंधा है, PASS या FAIL दोनों प्रकाशित।',
    stats: [
      {v: '81.7%', l: 'मैप किए बाढ़ पिक्सल एक अलग सैटेलाइट (Sentinel-2 ऑप्टिकल, 237 सत्य-बिंदु) द्वारा पुष्ट। पूर्व-घोषित गेट: 60%।'},
      {v: 'ρ = 0.72', l: 'हमारे 2025 सैटेलाइट क्षति नक्शे और सरकार के विशेष गिरदावरी सर्वे के बीच रैंक-मेल, सभी 20 ज़िलों में (16 नामित पर 0.56)।'},
      {v: '450+', l: 'स्वचालित टेस्ट, जिस कोड को जाँचते हैं उससे पहले लिखे गए।'},
      {v: '3', l: 'क्रॉस-जाँच: Sentinel-2 ऑप्टिकल (अलग सेंसर), सरकारी ज़मीनी सर्वे, और Copernicus GFM (अलग एल्गोरिदम, जिसने लेबल भी दिए)।'},
    ],
    honesty: 'हमने एक आयातित डीप-लर्निंग U-Net भी बेंचमार्क किया: लैब में IoU 0.63, पर पंजाब में बुरी तरह under-segment (recall 0.24)। हमारा सरल स्टैक जीता, और हमने वह परिणाम छिपाने के बजाय प्रकाशित किया। असफलताएँ भी वेरिफिकेशन लॉग में जाती हैं।',
    take: 'दस्तावेज़ लें',
    links: [
      {t: 'विधि पेपर — हर थ्रेशोल्ड, मॉडल और सत्यापन', u: REPO + '/blob/master/docs/METHOD.md'},
      {t: 'वेरिफिकेशन लॉग — पूर्व-घोषित बैंड, वास्तविक, PASS/FAIL', u: REPO + '/blob/master/docs/VERIFICATION-LOG.md'},
      {t: '20 ज़िला ब्रीफ़ — हर DC दफ़्तर के लिए एक प्रिंट-योग्य पेज', u: REPO + '/tree/master/briefs'},
      {t: 'सारांश (PDF) — पूरी परियोजना 5 पेज में', u: RAW + 'docs/SAILAAB-synopsis.pdf'},
      {t: 'स्थिरता व परिनियोजन योजना (PDF)', u: RAW + 'docs/SAILAAB-business-plan.pdf'},
      {t: 'सोर्स कोड (MIT) — हर संख्या पुनरुत्पन्न करें', u: REPO},
    ],
  },
  pa: {
    eyebrow: 'ਪ੍ਰਮਾਣ · 2025 ਉੱਤੇ ਹੋਲਡ-ਆਊਟ',
    title: '1988 ਤੋਂ ਬਾਅਦ ਦੀ ਸਭ ਤੋਂ ਭਿਆਨਕ ਹੜ੍ਹ ਨੇ ਪਰਖਿਆ',
    intro: 'ਭਵਿੱਖਬਾਣੀ ਤੇ ਨਕਸ਼ੇ 2015–24 ਉੱਤੇ ਸਿਖਲਾਈ ਹੋਏ, ਫਿਰ 2025 — ਜੋ ਉਨ੍ਹਾਂ ਕਦੇ ਨਹੀਂ ਵੇਖਿਆ ਸੀ — ਸੌਂਪਿਆ ਗਿਆ ਤੇ ਉਸੇ ਨੇ ਪਰਖਿਆ। ਹਰ ਸੈਟੇਲਾਈਟ ਦਾਅਵਾ ਰਨ ਤੋਂ ਪਹਿਲਾਂ ਲਿਖੀ ਸੰਖਿਆ ਨਾਲ ਬੱਝਾ ਹੈ, PASS ਜਾਂ FAIL ਦੋਵੇਂ ਪ੍ਰਕਾਸ਼ਿਤ।',
    stats: [
      {v: '81.7%', l: 'ਮੈਪ ਕੀਤੇ ਹੜ੍ਹ ਪਿਕਸਲ ਇੱਕ ਵੱਖਰੇ ਸੈਟੇਲਾਈਟ (Sentinel-2 ਆਪਟੀਕਲ, 237 ਸੱਚ-ਬਿੰਦੂ) ਦੁਆਰਾ ਪੁਸ਼ਟ। ਪੂਰਵ-ਘੋਸ਼ਿਤ ਗੇਟ: 60%।'},
      {v: 'ρ = 0.72', l: 'ਸਾਡੇ 2025 ਸੈਟੇਲਾਈਟ ਨੁਕਸਾਨ ਨਕਸ਼ੇ ਅਤੇ ਸਰਕਾਰ ਦੇ ਖ਼ਾਸ ਗਿਰਦਾਵਰੀ ਸਰਵੇ ਵਿਚਕਾਰ ਰੈਂਕ-ਮੇਲ, ਸਾਰੇ 20 ਜ਼ਿਲ੍ਹਿਆਂ ਵਿੱਚ (16 ਨਾਮਿਤ ਉੱਤੇ 0.56)।'},
      {v: '450+', l: 'ਆਟੋਮੈਟਿਕ ਟੈਸਟ, ਜਿਸ ਕੋਡ ਨੂੰ ਜਾਂਚਦੇ ਹਨ ਉਸ ਤੋਂ ਪਹਿਲਾਂ ਲਿਖੇ।'},
      {v: '3', l: 'ਕ੍ਰਾਸ-ਜਾਂਚ: Sentinel-2 ਆਪਟੀਕਲ (ਵੱਖਰਾ ਸੈਂਸਰ), ਸਰਕਾਰੀ ਜ਼ਮੀਨੀ ਸਰਵੇ, ਤੇ Copernicus GFM (ਵੱਖਰਾ ਐਲਗੋਰਿਦਮ, ਜਿਸ ਨੇ ਲੇਬਲ ਵੀ ਦਿੱਤੇ)।'},
    ],
    honesty: 'ਅਸੀਂ ਇੱਕ ਆਯਾਤ ਡੀਪ-ਲਰਨਿੰਗ U-Net ਵੀ ਬੈਂਚਮਾਰਕ ਕੀਤਾ: ਲੈਬ ਵਿੱਚ IoU 0.63, ਪਰ ਪੰਜਾਬ ਵਿੱਚ ਬੁਰੀ ਤਰ੍ਹਾਂ under-segment (recall 0.24)। ਸਾਡਾ ਸਰਲ ਸਟੈਕ ਜਿੱਤਿਆ, ਤੇ ਅਸੀਂ ਉਹ ਨਤੀਜਾ ਲੁਕਾਉਣ ਦੀ ਬਜਾਏ ਪ੍ਰਕਾਸ਼ਿਤ ਕੀਤਾ। ਅਸਫ਼ਲਤਾਵਾਂ ਵੀ ਵੈਰੀਫਿਕੇਸ਼ਨ ਲੌਗ ਵਿੱਚ ਜਾਂਦੀਆਂ ਹਨ।',
    take: 'ਦਸਤਾਵੇਜ਼ ਲਓ',
    links: [
      {t: 'ਵਿਧੀ ਪੇਪਰ — ਹਰ ਥ੍ਰੈਸ਼ਹੋਲਡ, ਮਾਡਲ ਤੇ ਸਤਿਆਪਨ', u: REPO + '/blob/master/docs/METHOD.md'},
      {t: 'ਵੈਰੀਫਿਕੇਸ਼ਨ ਲੌਗ — ਪੂਰਵ-ਘੋਸ਼ਿਤ ਬੈਂਡ, ਵਾਸਤਵਿਕ, PASS/FAIL', u: REPO + '/blob/master/docs/VERIFICATION-LOG.md'},
      {t: '20 ਜ਼ਿਲ੍ਹਾ ਬਰੀਫ਼ — ਹਰ DC ਦਫ਼ਤਰ ਲਈ ਇੱਕ ਪ੍ਰਿੰਟ-ਯੋਗ ਪੇਜ', u: REPO + '/tree/master/briefs'},
      {t: 'ਸਾਰ (PDF) — ਪੂਰਾ ਪ੍ਰੋਜੈਕਟ 5 ਪੇਜਾਂ ਵਿੱਚ', u: RAW + 'docs/SAILAAB-synopsis.pdf'},
      {t: 'ਸਥਿਰਤਾ ਤੇ ਤੈਨਾਤੀ ਯੋਜਨਾ (PDF)', u: RAW + 'docs/SAILAAB-business-plan.pdf'},
      {t: 'ਸੋਰਸ ਕੋਡ (MIT) — ਹਰ ਸੰਖਿਆ ਮੁੜ-ਪੈਦਾ ਕਰੋ', u: REPO},
    ],
  },
};

export default function ProofSection({lang}) {
  const t = P_T[lang] || P_T.en;
  const pt = PRED_T[lang] || PRED_T.en;
  const [preds, setPreds] = useState([]);

  useEffect(() => {
    let on = true;
    loadCsv('assets/forecaster_2025_hindcast.csv').then((data) => {
      if (!on) return;
      const peak = {};
      data.forEach((d) => {
        const name = d.district;
        if (!name) return;
        const p = +d.p_event || 0;
        const flooded = String(d.flood_event) === '1' || parseFloat(d.flood_event) >= 0.5;
        if (!(name in peak)) peak[name] = {district: name, p: 0, flooded: false};
        peak[name].p = Math.max(peak[name].p, p);
        peak[name].flooded = peak[name].flooded || flooded;
      });
      setPreds(Object.values(peak).sort((a, b) => b.p - a.p).slice(0, 8).map((d) => ({district: d.district, pct: Math.round(d.p * 100), flooded: d.flooded})));
    }).catch(() => {});
    return () => { on = false; };
  }, []);

  return (
    <Section variant="transparent" padding={0} dividers={['top']}>
      <HStack justify="center" width="100%">
        <VStack width="100%" maxWidth={1080} paddingInline={4} paddingBlock={9} gap={5} hAlign="center" id="proof">
          <VStack gap={2}>
            <Text type="label" color="accent">{t.eyebrow}</Text>
            <Heading level={2}>{t.title}</Heading>
          </VStack>
          <VStack maxWidth={760}>
            <Text type="large" color="secondary">{t.intro}</Text>
          </VStack>
          <Grid columns={{minWidth: 240, max: 4}} gap={4} width="100%">
            {t.stats.map((s, i) => (
              <Card key={i} padding={4}>
                <VStack gap={2}>
                  <Heading level={3} type="display-2" color="accent">{s.v}</Heading>
                  <Text type="supporting" color="secondary">{s.l}</Text>
                </VStack>
              </Card>
            ))}
          </Grid>
          <VStack maxWidth={780}>
            <Text color="secondary">{t.honesty}</Text>
          </VStack>

          {preds.length > 0 && (
            <VStack gap={3} width="100%">
              <Text type="label" color="secondary">{pt.title}</Text>
              <div style={{width: '100%', height: 320}}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={preds} margin={{top: 18, right: 12, left: 0, bottom: 8}}>
                    <CartesianGrid stroke={GRID} vertical={false} />
                    <XAxis dataKey="district" interval={0} angle={-30} textAnchor="end" height={72} tick={{fill: AXIS, fontSize: 11}} axisLine={{stroke: GRID}} tickLine={false} />
                    <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{fill: AXIS, fontSize: 12}} axisLine={false} tickLine={false} width={44} />
                    <Tooltip formatter={(v) => [`${v}%`, 'flood risk']} contentStyle={{background: TIP_BG, border: `1px solid ${TIP_BD}`, borderRadius: 6, color: TIP_FG, fontSize: 13}} labelStyle={{color: AXIS}} cursor={{fill: '#ffffff0a'}} />
                    <Bar dataKey="pct" radius={[3, 3, 0, 0]} maxBarSize={48}>
                      {preds.map((d, i) => (<Cell key={i} fill={d.flooded ? FLOODED : DRY} />))}
                      <LabelList dataKey="pct" position="top" formatter={(v) => `${v}%`} fill={AXIS} fontSize={11} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <VStack maxWidth={720}><Text type="supporting" color="secondary">{pt.cap}</Text></VStack>
            </VStack>
          )}

          <VStack gap={3} width="100%">
            <Text type="label" color="secondary">{t.take}</Text>
            <VStack gap={0}>
              {t.links.map((l, i) => (
                <React.Fragment key={i}>
                  <VStack paddingBlock={2}><Link href={l.u} isStandalone>{l.t}</Link></VStack>
                </React.Fragment>
              ))}
            </VStack>
          </VStack>
        </VStack>
      </HStack>
    </Section>
  );
}
