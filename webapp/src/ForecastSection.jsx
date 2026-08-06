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
    lead: 'A three-day flood forecast for every district in Punjab.',
    intro: 'Gradient boosting over a decade of daily satellite flood observations, with history features that carry recent flooding across neighbouring districts. Open, reproducible, running live this monsoon, in a state whose reviewed CWC station table listed no flood-forecast station.',
    explain: 'Every 6 hours it asks one question of each district: will the satellite see flooding here within the next three days? It uses only what is known on the day it runs.',
    boardNote: 'Tested on seasons it had never seen, with the alert level set from earlier seasons only, it raised about 28 alerts a season and roughly one in three was followed by real flooding within three days. It catches about one flood onset in four, so a quiet board is not a guarantee of safety, and a district the satellite did not image is shown as unknown rather than dry.',
    liveHead: 'Live risk · this window',
    districtCol: 'District',
    unknown: 'not imaged',
    unavailable: 'Forecast unavailable for this cycle: the satellite coverage needed to make it was missing or too old. This is NOT an all-clear.',
    riskCol: 'risk score',
    waterCol: 'water now',
    summary: 'Every season is forecast using only the seasons before it, so the model never sees its own future. On that test its ranking beat a persistence baseline in each of the four seasons that contained flooding, and in 2025, the season with the most flood days in the record, average precision reached 0.549 against 0.096. Much of that comes from history features that carry recent flooding across neighbouring districts, decaying over about three days. The ranking is the solid result and the alerting is modest: this is a selective trigger, not a comprehensive warning system. All of it is retrospective; the 2026 monsoon is the real test. The full audit, including an earlier number we had to retract, is below.',
    seeProof: 'See how it did in 2025, and the full validation →',
  },
  hi: {
    no: '01', title: 'पूर्वानुमान',
    lead: 'पंजाब के हर ज़िले के लिए तीन दिन का बाढ़ पूर्वानुमान।',
    intro: 'एक XGBoost मॉडल, दशक भर के सैटेलाइट-आधारित बाढ़ लेबल (2015–24) पर प्रशिक्षित। खुला, पुनरुत्पाद्य और इस मानसून लाइव — उस राज्य में जहाँ शून्य आधिकारिक बाढ़-पूर्वानुमान स्टेशन थे।',
    explain: 'हर 6 घंटे यह हर ज़िले से एक सवाल पूछता है: क्या अगले तीन दिनों में सैटेलाइट यहाँ बाढ़ देखेगा? यह केवल उसी दिन तक की जानकारी का उपयोग करता है।',
    boardNote: 'जोखिम मानसून के साथ चलता है: शांत विंडो में हर ज़िला लगभग शून्य दिखाता है, और बाढ़ की स्थिति बनते ही यह बढ़ता है। नीचे 2025 का होल्ड-आउट रन दिखाता है कि असली घटना के दौरान बोर्ड कैसा दिखता था।',
    liveHead: 'लाइव जोखिम · यह विंडो',
    districtCol: 'ज़िला',
    unknown: 'चित्र नहीं',
    unavailable: 'इस चक्र के लिए पूर्वानुमान उपलब्ध नहीं: इसे बनाने के लिए ज़रूरी सैटेलाइट कवरेज नहीं थी या बहुत पुरानी थी। यह सुरक्षा की सूचना नहीं है।',
    riskCol: 'जोखिम स्कोर',
    waterCol: 'अभी जल',
    summary: 'बाईं ओर की तालिका हर ज़िले के बाढ़ जोखिम की मॉडल की लाइव रैंकिंग है। केवल 2015 से 2024 पर प्रशिक्षित और 2025 पर होल्ड-आउट, इसने सबसे ज़्यादा प्रभावित ज़िलों को शीर्ष के पास रखा। एक सरल बेसलाइन जो पिछली विंडो की बाढ़ को आगे बढ़ाता है, इसके लगभग बराबर है, इसलिए इसे एक ईमानदार खुली रैंकिंग समझें, कोई सटीक भविष्यवक्ता नहीं। पूरा होल्ड-आउट सत्यापन, और सैटेलाइट नक्शा सरकार के ज़मीनी सर्वे से कैसे मेल खाता है, नीचे है।',
    seeProof: 'देखें 2025 में यह कैसा रहा, और पूरा सत्यापन →',
  },
  pa: {
    no: '01', title: 'ਭਵਿੱਖਬਾਣੀ',
    lead: 'ਪੰਜਾਬ ਦੇ ਹਰ ਜ਼ਿਲ੍ਹੇ ਲਈ ਤਿੰਨ ਦਿਨਾਂ ਦੀ ਹੜ੍ਹ ਭਵਿੱਖਬਾਣੀ।',
    intro: 'ਇੱਕ XGBoost ਮਾਡਲ, ਦਹਾਕੇ ਭਰ ਦੇ ਸੈਟੇਲਾਈਟ-ਆਧਾਰਿਤ ਹੜ੍ਹ ਲੇਬਲਾਂ (2015–24) ਉੱਤੇ ਸਿਖਲਾਈ। ਖੁੱਲ੍ਹਾ, ਮੁੜ-ਪੈਦਾ ਕਰਨਯੋਗ ਅਤੇ ਇਸ ਮਾਨਸੂਨ ਲਾਈਵ — ਉਸ ਸੂਬੇ ਵਿੱਚ ਜਿੱਥੇ ਜ਼ੀਰੋ ਸਰਕਾਰੀ ਹੜ੍ਹ-ਭਵਿੱਖਬਾਣੀ ਸਟੇਸ਼ਨ ਸਨ।',
    explain: 'ਹਰ 6 ਘੰਟੇ ਇਹ ਹਰ ਜ਼ਿਲ੍ਹੇ ਤੋਂ ਇੱਕ ਸਵਾਲ ਪੁੱਛਦਾ ਹੈ: ਕੀ ਅਗਲੇ ਤਿੰਨ ਦਿਨਾਂ ਵਿੱਚ ਸੈਟੇਲਾਈਟ ਇੱਥੇ ਹੜ੍ਹ ਵੇਖੇਗਾ? ਇਹ ਸਿਰਿਫ਼ ਉਸੇ ਦਿਨ ਤੱਕ ਦੀ ਜਾਣਕਾਰੀ ਵਰਤਦਾ ਹੈ।',
    boardNote: 'ਖ਼ਤਰਾ ਮਾਨਸੂਨ ਨਾਲ ਚੱਲਦਾ ਹੈ: ਸ਼ਾਂਤ ਵਿੰਡੋ ਵਿੱਚ ਹਰ ਜ਼ਿਲ੍ਹਾ ਲਗਭਗ ਜ਼ੀਰੋ ਦਿਖਾਉਂਦਾ ਹੈ, ਅਤੇ ਹੜ੍ਹ ਦੀਆਂ ਹਾਲਤਾਂ ਬਣਦਿਆਂ ਹੀ ਇਹ ਵਧਦਾ ਹੈ। ਹੇਠਾਂ 2025 ਦਾ ਹੋਲਡ-ਆਊਟ ਰਨ ਦਿਖਾਉਂਦਾ ਹੈ ਕਿ ਅਸਲ ਘਟਨਾ ਦੌਰਾਨ ਬੋਰਡ ਕਿਹੋ ਜਿਹਾ ਦਿਖਦਾ ਸੀ।',
    liveHead: 'ਲਾਈਵ ਖ਼ਤਰਾ · ਇਹ ਵਿੰਡੋ',
    districtCol: 'ਜ਼ਿਲ੍ਹਾ',
    unknown: 'ਤਸਵੀਰ ਨਹੀਂ',
    unavailable: 'ਇਸ ਚੱਕਰ ਲਈ ਭਵਿੱਖਬਾਣੀ ਉਪਲਬਧ ਨਹੀਂ: ਇਸ ਨੂੰ ਬਣਾਉਣ ਲਈ ਲੋੜੀਂਦੀ ਸੈਟੇਲਾਈਟ ਕਵਰੇਜ ਨਹੀਂ ਸੀ ਜਾਂ ਬਹੁਤ ਪੁਰਾਣੀ ਸੀ। ਇਹ ਸੁਰੱਖਿਆ ਦੀ ਸੂਚਨਾ ਨਹੀਂ ਹੈ।',
    riskCol: 'ਖ਼ਤਰਾ ਸਕੋਰ',
    waterCol: 'ਹੁਣ ਪਾਣੀ',
    summary: 'ਖੱਬੇ ਪਾਸੇ ਦੀ ਸਾਰਣੀ ਹਰ ਜ਼ਿਲ੍ਹੇ ਦੇ ਹੜ੍ਹ ਖ਼ਤਰੇ ਦੀ ਮਾਡਲ ਦੀ ਲਾਈਵ ਰੈਂਕਿੰਗ ਹੈ। ਸਿਰਫ਼ 2015 ਤੋਂ 2024 ਉੱਤੇ ਸਿਖਲਾਈ ਅਤੇ 2025 ਉੱਤੇ ਹੋਲਡ-ਆਊਟ, ਇਸ ਨੇ ਸਭ ਤੋਂ ਵੱਧ ਪ੍ਰਭਾਵਿਤ ਜ਼ਿਲ੍ਹਿਆਂ ਨੂੰ ਸਿਖਰ ਦੇ ਨੇੜੇ ਰੱਖਿਆ। ਇੱਕ ਸਰਲ ਬੇਸਲਾਈਨ ਜੋ ਪਿਛਲੀ ਵਿੰਡੋ ਦੇ ਹੜ੍ਹ ਨੂੰ ਅੱਗੇ ਲੈ ਜਾਂਦਾ ਹੈ, ਇਸ ਦੇ ਲਗਭਗ ਬਰਾਬਰ ਹੈ, ਇਸ ਲਈ ਇਸ ਨੂੰ ਇੱਕ ਇਮਾਨਦਾਰ ਖੁੱਲ੍ਹੀ ਰੈਂਕਿੰਗ ਸਮਝੋ, ਕੋਈ ਸਟੀਕ ਭਵਿੱਖਬਾਣੀਕਾਰ ਨਹੀਂ। ਪੂਰਾ ਹੋਲਡ-ਆਊਟ ਸਤਿਆਪਨ, ਅਤੇ ਸੈਟੇਲਾਈਟ ਨਕਸ਼ਾ ਸਰਕਾਰ ਦੇ ਜ਼ਮੀਨੀ ਸਰਵੇ ਨਾਲ ਕਿਵੇਂ ਮੇਲ ਖਾਂਦਾ ਹੈ, ਹੇਠਾਂ ਹੈ।',
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
          <VStack maxWidth={780}>
            <Text color="secondary">{t.boardNote}</Text>
          </VStack>

          {nc && nc.forecast && nc.forecast.status === 'unavailable' && (
            <VStack maxWidth={780} gap={2}>
              <StatusDot variant="warning" label="unavailable" />
              <Text type="large">{t.unavailable}</Text>
            </VStack>
          )}

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
                    // A null score means the forecast could not be made for this
                    // district. Coercing it to zero would print a reassuring
                    // number for a district nobody looked at.
                    const known = d.p_event !== null && d.p_event !== undefined;
                    const risk = known ? (+d.p_event).toFixed(3) : t.unknown;
                    const water = d.covered === false || d.observed_km2 === null
                      ? t.unknown
                      : (+d.observed_km2 || 0).toFixed(1) + ' km²';
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
