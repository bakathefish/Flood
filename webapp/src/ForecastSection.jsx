import React, {useState, useEffect} from 'react';
import {Section} from '@astryxdesign/core/Section';
import {VStack} from '@astryxdesign/core/VStack';
import {HStack} from '@astryxdesign/core/HStack';
import {Grid} from '@astryxdesign/core/Grid';
import {Text} from '@astryxdesign/core/Text';
import {Heading} from '@astryxdesign/core/Heading';
import {Badge} from '@astryxdesign/core/Badge';
import {StatusDot} from '@astryxdesign/core/StatusDot';
import {Link} from '@astryxdesign/core/Link';
import {Divider} from '@astryxdesign/core/Divider';

const RAW = 'https://raw.githubusercontent.com/bakathefish/Flood/master/';

const F_T = {
  en: {
    no: '01', title: 'The forecast',
    lead: 'Punjab’s first district-level flood forecast.',
    intro: 'An XGBoost model, trained on a decade of satellite-derived flood labels (2015–24). Open, reproducible, and running live this monsoon — in a state that had zero official flood-forecast stations.',
    explain: 'Every 6 hours it scores each district: the chance it floods in the next 10 days.',
    liveHead: 'Live risk · this window',
    districtCol: 'District',
    riskCol: 'flood risk',
    waterCol: 'water now',
    summary: 'The table on the left is the model’s live ranking of each district’s flood risk. Trained only on 2015 to 2024 and held out to 2025, it put the worst-hit districts near the top. A one-line baseline that just carries forward last window’s flooding nearly matches it, so read this as an honest open ranking, not a precise oracle. The full held-out validation, and how the satellite map compares to the government’s ground survey, is below.',
    seeProof: 'See how it did in 2025, and the full validation →',
  },
  hi: {
    no: '01', title: 'पूर्वानुमान',
    lead: 'पंजाब का पहला ज़िला-स्तरीय बाढ़ पूर्वानुमान।',
    intro: 'एक XGBoost मॉडल, दशक भर के सैटेलाइट-आधारित बाढ़ लेबल (2015–24) पर प्रशिक्षित। खुला, पुनरुत्पाद्य और इस मानसून लाइव — उस राज्य में जहाँ शून्य आधिकारिक बाढ़-पूर्वानुमान स्टेशन थे।',
    explain: 'हर 6 घंटे यह हर ज़िले को स्कोर करता है: अगले 10 दिनों में उसके डूबने की संभावना।',
    liveHead: 'लाइव जोखिम · यह विंडो',
    districtCol: 'ज़िला',
    riskCol: 'बाढ़ जोखिम',
    waterCol: 'अभी जल',
    summary: 'बाईं ओर की तालिका हर ज़िले के बाढ़ जोखिम की मॉडल की लाइव रैंकिंग है। केवल 2015 से 2024 पर प्रशिक्षित और 2025 पर होल्ड-आउट, इसने सबसे ज़्यादा प्रभावित ज़िलों को शीर्ष के पास रखा। एक सरल बेसलाइन जो पिछली विंडो की बाढ़ को आगे बढ़ाता है, इसके लगभग बराबर है, इसलिए इसे एक ईमानदार खुली रैंकिंग समझें, कोई सटीक भविष्यवक्ता नहीं। पूरा होल्ड-आउट सत्यापन, और सैटेलाइट नक्शा सरकार के ज़मीनी सर्वे से कैसे मेल खाता है, नीचे है।',
    seeProof: 'देखें 2025 में यह कैसा रहा, और पूरा सत्यापन →',
  },
  pa: {
    no: '01', title: 'ਭਵਿੱਖਬਾਣੀ',
    lead: 'ਪੰਜਾਬ ਦੀ ਪਹਿਲੀ ਜ਼ਿਲ੍ਹਾ-ਪੱਧਰੀ ਹੜ੍ਹ ਭਵਿੱਖਬਾਣੀ।',
    intro: 'ਇੱਕ XGBoost ਮਾਡਲ, ਦਹਾਕੇ ਭਰ ਦੇ ਸੈਟੇਲਾਈਟ-ਆਧਾਰਿਤ ਹੜ੍ਹ ਲੇਬਲਾਂ (2015–24) ਉੱਤੇ ਸਿਖਲਾਈ। ਖੁੱਲ੍ਹਾ, ਮੁੜ-ਪੈਦਾ ਕਰਨਯੋਗ ਅਤੇ ਇਸ ਮਾਨਸੂਨ ਲਾਈਵ — ਉਸ ਸੂਬੇ ਵਿੱਚ ਜਿੱਥੇ ਜ਼ੀਰੋ ਸਰਕਾਰੀ ਹੜ੍ਹ-ਭਵਿੱਖਬਾਣੀ ਸਟੇਸ਼ਨ ਸਨ।',
    explain: 'ਹਰ 6 ਘੰਟੇ ਇਹ ਹਰ ਜ਼ਿਲ੍ਹੇ ਨੂੰ ਸਕੋਰ ਕਰਦਾ ਹੈ: ਅਗਲੇ 10 ਦਿਨਾਂ ਵਿੱਚ ਉਸ ਦੇ ਡੁੱਬਣ ਦੀ ਸੰਭਾਵਨਾ।',
    liveHead: 'ਲਾਈਵ ਖ਼ਤਰਾ · ਇਹ ਵਿੰਡੋ',
    districtCol: 'ਜ਼ਿਲ੍ਹਾ',
    riskCol: 'ਹੜ੍ਹ ਖ਼ਤਰਾ',
    waterCol: 'ਹੁਣ ਪਾਣੀ',
    summary: 'ਖੱਬੇ ਪਾਸੇ ਦੀ ਸਾਰਣੀ ਹਰ ਜ਼ਿਲ੍ਹੇ ਦੇ ਹੜ੍ਹ ਖ਼ਤਰੇ ਦੀ ਮਾਡਲ ਦੀ ਲਾਈਵ ਰੈਂਕਿੰਗ ਹੈ। ਸਿਰਫ਼ 2015 ਤੋਂ 2024 ਉੱਤੇ ਸਿਖਲਾਈ ਅਤੇ 2025 ਉੱਤੇ ਹੋਲਡ-ਆਊਟ, ਇਸ ਨੇ ਸਭ ਤੋਂ ਵੱਧ ਪ੍ਰਭਾਵਿਤ ਜ਼ਿਲ੍ਹਿਆਂ ਨੂੰ ਸਿਖਰ ਦੇ ਨੇੜੇ ਰੱਖਿਆ। ਇੱਕ ਸਰਲ ਬੇਸਲਾਈਨ ਜੋ ਪਿਛਲੀ ਵਿੰਡੋ ਦੀ ਹੜ੍ਹ ਨੂੰ ਅੱਗੇ ਲੈ ਜਾਂਦਾ ਹੈ, ਇਸ ਦੇ ਲਗਭਗ ਬਰਾਬਰ ਹੈ, ਇਸ ਲਈ ਇਸ ਨੂੰ ਇੱਕ ਇਮਾਨਦਾਰ ਖੁੱਲ੍ਹੀ ਰੈਂਕਿੰਗ ਸਮਝੋ, ਕੋਈ ਸਟੀਕ ਭਵਿੱਖਬਾਣੀਕਾਰ ਨਹੀਂ। ਪੂਰਾ ਹੋਲਡ-ਆਊਟ ਸਤਿਆਪਨ, ਅਤੇ ਸੈਟੇਲਾਈਟ ਨਕਸ਼ਾ ਸਰਕਾਰ ਦੇ ਜ਼ਮੀਨੀ ਸਰਵੇ ਨਾਲ ਕਿਵੇਂ ਮੇਲ ਖਾਂਦਾ ਹੈ, ਹੇਠਾਂ ਹੈ।',
    seeProof: 'ਵੇਖੋ 2025 ਵਿੱਚ ਇਹ ਕਿਵੇਂ ਰਿਹਾ, ਅਤੇ ਪੂਰਾ ਸਤਿਆਪਨ →',
  },
};

export default function ForecastSection({lang}) {
  const t = F_T[lang] || F_T.en;
  const [nc, setNc] = useState(null);

  useEffect(() => {
    let on = true;
    fetch(RAW + 'monitor/nowcast.json').then((r) => r.json()).then((j) => on && setNc(j)).catch(() => {});
    return () => { on = false; };
  }, []);

  const rows = nc && nc.districts
    ? [...nc.districts].sort((a, b) => (+b.p_event || 0) - (+a.p_event || 0)).slice(0, 8)
    : [];

  return (
    <Section variant="transparent" padding={0} dividers={['bottom']}>
      <HStack justify="center" width="100%">
        <VStack width="100%" maxWidth={1080} paddingInline={4} paddingBlock={9} gap={5} hAlign="center" id="forecast">
          <HStack gap={3} vAlign="center" wrap="wrap">
            <Text type="label" color="accent">{t.no}</Text>
            <Heading level={2}>{t.title}</Heading>
            <Badge variant="blue" label="AI" />
          </HStack>
          <Heading level={3} type="display-3">{t.lead}</Heading>
          <VStack maxWidth={780} gap={3}>
            <Text type="large" color="secondary">{t.intro}</Text>
            <Text type="large">{t.explain}</Text>
          </VStack>

          {rows.length > 0 && (
            <Grid columns={{minWidth: 300, max: 2}} gap={6} align="start" width="100%">
              <VStack width="100%" maxWidth={460} gap={3}>
                <HStack gap={2} vAlign="center" wrap="wrap">
                  <StatusDot variant="accent" label="live" isPulsing />
                  <Text type="label" color="secondary">{t.liveHead}{nc ? ` · ${nc.window_start} → ${nc.window_end}` : ''}</Text>
                </HStack>
                <VStack width="100%" gap={0}>
                  <HStack justify="between" vAlign="baseline" gap={3} paddingBlock={1}>
                    <Text type="supporting" color="secondary">{t.districtCol}</Text>
                    <HStack gap={5} vAlign="baseline">
                      <Text type="supporting" color="secondary">{t.riskCol}</Text>
                      <Text type="supporting" color="secondary">{t.waterCol}</Text>
                    </HStack>
                  </HStack>
                  {rows.map((d) => {
                    const pct = (+d.p_event || 0) * 100;
                    const risk = pct >= 0.1 ? pct.toFixed(1) + '%' : '<0.1%';
                    const water = (+d.observed_km2 || 0).toFixed(1) + ' km²';
                    return (
                      <React.Fragment key={d.district}>
                        <Divider />
                        <HStack justify="between" vAlign="center" paddingBlock={2} gap={3}>
                          <Text>{d.district}</Text>
                          <HStack gap={5} vAlign="baseline">
                            <Text color="accent" hasTabularNumbers>{risk}</Text>
                            <Text color="secondary" hasTabularNumbers>{water}</Text>
                          </HStack>
                        </HStack>
                      </React.Fragment>
                    );
                  })}
                  <Divider />
                </VStack>
              </VStack>
              <VStack maxWidth={440} justify="center">
                <Text type="large" color="secondary">{t.summary}</Text>
              </VStack>
            </Grid>
          )}

          <Link href="#proof" isStandalone>{t.seeProof}</Link>
        </VStack>
      </HStack>
    </Section>
  );
}
