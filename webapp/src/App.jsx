import React, {useState, useEffect} from 'react';
import {AppShell} from '@astryxdesign/core/AppShell';
import {Section} from '@astryxdesign/core/Section';
import {VStack} from '@astryxdesign/core/VStack';
import {HStack} from '@astryxdesign/core/HStack';
import {Grid} from '@astryxdesign/core/Grid';
import {Text} from '@astryxdesign/core/Text';
import {Heading} from '@astryxdesign/core/Heading';
import {Divider} from '@astryxdesign/core/Divider';
import {Link} from '@astryxdesign/core/Link';
import {Button} from '@astryxdesign/core/Button';
import {Badge} from '@astryxdesign/core/Badge';
import {StatusDot} from '@astryxdesign/core/StatusDot';
import {Card} from '@astryxdesign/core/Card';
import MapSection from './MapSection';
import AlertSection from './AlertSection';
import ForecastSection from './ForecastSection';
import ProofSection from './ProofSection';

const RAW = 'https://raw.githubusercontent.com/bakathefish/Flood/master/';

// full-bleed page band with a centered reading column
function Band({children, dividers, paddingBlock = 6, maxWidth = 1080, variant = 'transparent'}) {
  return (
    <Section variant={variant} padding={0} dividers={dividers}>
      <HStack justify="center" width="100%">
        <VStack width="100%" maxWidth={maxWidth} paddingInline={4} paddingBlock={paddingBlock} gap={0} hAlign="center">
          {children}
        </VStack>
      </HStack>
    </Section>
  );
}

function StatBig({label, value}) {
  return (
    <VStack gap={1}>
      <Text type="supporting" color="secondary">{label}</Text>
      <Text size="2xl" color="accent" hasTabularNumbers>{value}</Text>
    </VStack>
  );
}

const LANGS = [
  {code: 'en', label: 'EN'},
  {code: 'hi', label: 'हिन्दी'},
  {code: 'pa', label: 'ਪੰਜਾਬੀ'},
];

const T = {
  en: {
    eyebrow: 'Punjab · open flood intelligence · live this monsoon',
    h1: 'The flood forecast Punjab never had.',
    lede: 'In August 2025 Punjab saw its worst flood since 1988. All 23 districts went under, about 3.55 lakh people were affected, and India’s flood-forecast network had zero stations in the state. Sailaab rebuilds that capability in the open, and it is running right now.',
    seeLive: 'See it live →',
    source: 'Source & method',
    gap: 'flood-forecast stations in Punjab. 226 exist across 22 other states. That absence is the gap this project fills.',
    who1L: 'Built for',
    who1: 'District disaster and revenue officers, relief agencies, and flood-exposed residents who read Punjabi or Hindi.',
    who2L: 'Reaches everyone',
    who2: 'Free, no login, trilingual, low-bandwidth, printable offline briefs, and designed for accessibility: high-contrast text, image alt-text, language-tagged content.',
    who3L: 'Toward the UN goals',
    who3: 'SDG 2 zero hunger (crop-loss quantification), 11 resilient communities, and 13 climate adaptation.',
    sysTitle: 'The system',
    sysIntro: 'Five modules, one open pipeline, from raw satellite radar to a plain-language alert in three languages. Every number is reproducible from public data.',
    techL: 'Built on',
    tech: 'Sentinel-1 SAR via Microsoft Planetary Computer (STAC) and Google Earth Engine · scikit-learn Random Forest · XGBoost with SHAP, conformal prediction and ablation · a PyTorch U-Net baseline · Leaflet + Recharts + Astryx on the front end · GitHub Actions CI every 6 hours · hand-written trilingual alert templates filled from the live numbers. 450+ tests, written before the code.',
    respTitle: 'Responsible by design',
    resp1L: 'Ethics', resp1: 'Advisory, not a replacement for official warnings — a human stays in the loop.',
    resp2L: 'Privacy', resp2: 'No personal data. Every input is public Earth-observation imagery and aggregate district statistics.',
    resp3L: 'Environment', resp3: 'Light models on free-tier compute — negligible carbon, in service of climate adaptation (SDG 13).',
    resp4L: 'Uncertainty & bias', resp4: 'Conformal intervals are calibrated on average but under-covered the 2025 extreme, a failure we publish rather than hide, alongside the rice-transplant false positive and both spatial folds.',
    liveTitle: 'Live this monsoon',
    liveHead: 'Live monitor · runs itself every 6 hours, no keys, no accounts',
    liveCap: 'The newest Sentinel-1 radar pass over Punjab, fetched and rendered automatically on public CI. Dark tones are standing water.',
    liveAlt: 'Newest Sentinel-1 radar pass over Punjab',
    liveLastL: 'Latest pass',
    liveCovL: 'Coverage',
    liveFloodL: 'Water flagged',
    liveLoading: 'querying…',
  },
  hi: {
    eyebrow: 'खुली बाढ़ इंटेलिजेंस · इस मानसून लाइव',
    h1: 'वह बाढ़ पूर्वानुमान जो पंजाब के पास कभी नहीं था।',
    lede: 'अगस्त 2025 में पंजाब ने 1988 के बाद की सबसे भीषण बाढ़ झेली: सभी 23 ज़िले, ~3.55 लाख लोग प्रभावित, और भारत के बाढ़-पूर्वानुमान नेटवर्क में राज्य के शून्य स्टेशन। सैलाब यह क्षमता खुले में फिर से बनाता है, और यह अभी चल रहा है।',
    seeLive: 'लाइव देखें →',
    source: 'स्रोत और विधि',
    gap: 'पंजाब में बाढ़-पूर्वानुमान स्टेशन। 22 अन्य राज्यों में 226 मौजूद हैं। यही कमी यह परियोजना भरती है।',
    who1L: 'किसके लिए',
    who1: 'ज़िला आपदा व राजस्व अधिकारी, राहत एजेंसियाँ, और पंजाबी या हिन्दी पढ़ने वाले बाढ़-प्रभावित निवासी।',
    who2L: 'सबकी पहुँच',
    who2: 'मुफ़्त, बिना लॉगिन, त्रिभाषी, कम-बैंडविड्थ, प्रिंट-योग्य ऑफ़लाइन ब्रीफ़, और सुलभता के लिए बनाया गया: उच्च-कंट्रास्ट टेक्स्ट, चित्र alt-टेक्स्ट, भाषा-चिह्नित सामग्री।',
    who3L: 'UN लक्ष्यों की ओर',
    who3: 'SDG 2 शून्य भूख (फ़सल-हानि आकलन), 11 सुदृढ़ समुदाय, और 13 जलवायु अनुकूलन।',
    sysTitle: 'सिस्टम',
    sysIntro: 'पाँच मॉड्यूल, एक खुली पाइपलाइन: कच्चे सैटेलाइट रडार से तीन भाषाओं में सरल-भाषा चेतावनी तक। हर आँकड़ा सार्वजनिक डेटा से पुनरुत्पाद्य।',
    techL: 'किस पर बना',
    tech: 'Sentinel-1 SAR — Microsoft Planetary Computer (STAC) व Google Earth Engine · scikit-learn Random Forest · XGBoost — SHAP, conformal prediction व ablation सहित · PyTorch U-Net बेसलाइन · फ्रंट-एंड पर Leaflet + Recharts + Astryx · हर 6 घंटे GitHub Actions CI · लाइव आँकड़ों से भरे हस्तलिखित त्रिभाषी चेतावनी टेम्पलेट। 450+ टेस्ट, कोड से पहले लिखे।',
    respTitle: 'ज़िम्मेदारी से बना',
    resp1L: 'नैतिकता', resp1: 'सलाहकारी, आधिकारिक चेतावनियों का विकल्प नहीं — मनुष्य निर्णय में शामिल रहता है।',
    resp2L: 'निजता', resp2: 'कोई व्यक्तिगत डेटा नहीं। हर इनपुट सार्वजनिक भू-निरीक्षण चित्र और समग्र ज़िला आँकड़े हैं।',
    resp3L: 'पर्यावरण', resp3: 'हल्के मॉडल, फ्री-टियर कंप्यूट — नगण्य कार्बन, जलवायु अनुकूलन (SDG 13) की सेवा में।',
    resp4L: 'अनिश्चितता व पक्षपात', resp4: 'Conformal अंतराल औसतन कैलिब्रेटेड हैं पर 2025 के चरम पर कम कवरेज दे गए, एक असफलता जिसे हम छिपाने के बजाय प्रकाशित करते हैं, धान-रोपाई के ग़लत-सकारात्मक और दोनों स्थानिक फ़ोल्ड के साथ।',
    liveTitle: 'इस मानसून लाइव',
    liveHead: 'लाइव मॉनिटर · हर 6 घंटे अपने आप, बिना कुंजी, बिना खाते',
    liveCap: 'पंजाब पर नवीनतम Sentinel-1 रडार पास, सार्वजनिक CI पर अपने आप लाया और रेंडर किया गया। गहरे रंग स्थिर जल हैं।',
    liveAlt: 'पंजाब पर नवीनतम Sentinel-1 रडार पास',
    liveLastL: 'नवीनतम पास',
    liveCovL: 'कवरेज',
    liveFloodL: 'चिह्नित जल',
    liveLoading: 'खोजा जा रहा है…',
  },
  pa: {
    eyebrow: 'ਖੁੱਲ੍ਹੀ ਹੜ੍ਹ ਖੁਫ਼ੀਆ ਜਾਣਕਾਰੀ · ਇਸ ਮਾਨਸੂਨ ਲਾਈਵ',
    h1: 'ਉਹ ਹੜ੍ਹ ਭਵਿੱਖਬਾਣੀ ਜੋ ਪੰਜਾਬ ਕੋਲ ਕਦੇ ਨਹੀਂ ਸੀ।',
    lede: 'ਅਗਸਤ 2025 ਵਿੱਚ ਪੰਜਾਬ ਨੇ 1988 ਤੋਂ ਬਾਅਦ ਦਾ ਸਭ ਤੋਂ ਭਿਆਨਕ ਹੜ੍ਹ ਝੱਲਿਆ: ਸਾਰੇ 23 ਜ਼ਿਲ੍ਹੇ, ~3.55 ਲੱਖ ਲੋਕ ਪ੍ਰਭਾਵਿਤ, ਅਤੇ ਭਾਰਤ ਦੇ ਹੜ੍ਹ-ਭਵਿੱਖਬਾਣੀ ਨੈੱਟਵਰਕ ਵਿੱਚ ਸੂਬੇ ਦੇ ਜ਼ੀਰੋ ਸਟੇਸ਼ਨ। ਸੈਲਾਬ ਇਹ ਸਮਰੱਥਾ ਖੁੱਲ੍ਹੇ ਵਿੱਚ ਮੁੜ ਉਸਾਰਦਾ ਹੈ, ਅਤੇ ਇਹ ਹੁਣੇ ਚੱਲ ਰਿਹਾ ਹੈ।',
    seeLive: 'ਲਾਈਵ ਵੇਖੋ →',
    source: 'ਸਰੋਤ ਅਤੇ ਵਿਧੀ',
    gap: 'ਪੰਜਾਬ ਵਿੱਚ ਹੜ੍ਹ-ਭਵਿੱਖਬਾਣੀ ਸਟੇਸ਼ਨ। 22 ਹੋਰ ਸੂਬਿਆਂ ਵਿੱਚ 226 ਹਨ। ਇਹੀ ਘਾਟ ਇਹ ਪ੍ਰੋਜੈਕਟ ਪੂਰੀ ਕਰਦਾ ਹੈ।',
    who1L: 'ਕਿਸ ਲਈ',
    who1: 'ਜ਼ਿਲ੍ਹਾ ਆਫ਼ਤ ਤੇ ਮਾਲ ਅਧਿਕਾਰੀ, ਰਾਹਤ ਏਜੰਸੀਆਂ, ਅਤੇ ਪੰਜਾਬੀ ਜਾਂ ਹਿੰਦੀ ਪੜ੍ਹਨ ਵਾਲੇ ਹੜ੍ਹ-ਪ੍ਰਭਾਵਿਤ ਵਾਸੀ।',
    who2L: 'ਸਭ ਤੱਕ ਪਹੁੰਚ',
    who2: 'ਮੁਫ਼ਤ, ਬਿਨਾਂ ਲੌਗਿਨ, ਤਿੰਨ-ਭਾਸ਼ੀ, ਘੱਟ-ਬੈਂਡਵਿਡਥ, ਪ੍ਰਿੰਟ-ਯੋਗ ਆਫ਼ਲਾਈਨ ਬਰੀਫ਼, ਅਤੇ ਪਹੁੰਚਯੋਗਤਾ ਲਈ ਬਣਾਇਆ: ਉੱਚ-ਕੰਟ੍ਰਾਸਟ ਟੈਕਸਟ, ਤਸਵੀਰ alt-ਟੈਕਸਟ, ਭਾਸ਼ਾ-ਚਿੰਨ੍ਹਿਤ ਸਮੱਗਰੀ।',
    who3L: 'UN ਟੀਚਿਆਂ ਵੱਲ',
    who3: 'SDG 2 ਜ਼ੀਰੋ ਭੁੱਖ (ਫ਼ਸਲ-ਨੁਕਸਾਨ ਆਕਲਨ), 11 ਮਜ਼ਬੂਤ ਭਾਈਚਾਰੇ, ਅਤੇ 13 ਜਲਵਾਯੂ ਅਨੁਕੂਲਨ।',
    sysTitle: 'ਸਿਸਟਮ',
    sysIntro: 'ਪੰਜ ਮੋਡਿਊਲ, ਇੱਕ ਖੁੱਲ੍ਹੀ ਪਾਈਪਲਾਈਨ: ਕੱਚੇ ਸੈਟੇਲਾਈਟ ਰਾਡਾਰ ਤੋਂ ਤਿੰਨ ਭਾਸ਼ਾਵਾਂ ਵਿੱਚ ਸਰਲ-ਭਾਸ਼ਾ ਚੇਤਾਵਨੀ ਤੱਕ। ਹਰ ਅੰਕੜਾ ਜਨਤਕ ਡੇਟਾ ਤੋਂ ਮੁੜ-ਪੈਦਾ ਕਰਨਯੋਗ।',
    techL: 'ਕਿਸ ਉੱਤੇ ਬਣਿਆ',
    tech: 'Sentinel-1 SAR — Microsoft Planetary Computer (STAC) ਤੇ Google Earth Engine · scikit-learn Random Forest · XGBoost — SHAP, conformal prediction ਤੇ ablation ਸਮੇਤ · PyTorch U-Net ਬੇਸਲਾਈਨ · ਫ਼੍ਰੰਟ-ਐਂਡ ਉੱਤੇ Leaflet + Recharts + Astryx · ਹਰ 6 ਘੰਟੇ GitHub Actions CI · ਲਾਈਵ ਅੰਕੜਿਆਂ ਤੋਂ ਭਰੇ ਹੱਥ-ਲਿਖਤ ਤਿੰਨ-ਭਾਸ਼ੀ ਚੇਤਾਵਨੀ ਟੈਂਪਲੇਟ। 450+ ਟੈਸਟ, ਕੋਡ ਤੋਂ ਪਹਿਲਾਂ ਲਿਖੇ।',
    respTitle: 'ਜ਼ਿੰਮੇਵਾਰੀ ਨਾਲ ਬਣਿਆ',
    resp1L: 'ਨੈਤਿਕਤਾ', resp1: 'ਸਲਾਹਕਾਰੀ, ਸਰਕਾਰੀ ਚੇਤਾਵਨੀਆਂ ਦਾ ਬਦਲ ਨਹੀਂ — ਮਨੁੱਖ ਫ਼ੈਸਲੇ ਵਿੱਚ ਸ਼ਾਮਲ ਰਹਿੰਦਾ ਹੈ।',
    resp2L: 'ਨਿੱਜਤਾ', resp2: 'ਕੋਈ ਨਿੱਜੀ ਡੇਟਾ ਨਹੀਂ। ਹਰ ਇਨਪੁੱਟ ਜਨਤਕ ਭੂ-ਨਿਰੀਖਣ ਤਸਵੀਰਾਂ ਤੇ ਸਮੁੱਚੇ ਜ਼ਿਲ੍ਹਾ ਅੰਕੜੇ ਹਨ।',
    resp3L: 'ਵਾਤਾਵਰਣ', resp3: 'ਹਲਕੇ ਮਾਡਲ, ਫ੍ਰੀ-ਟੀਅਰ ਕੰਪਿਊਟ — ਨਿਗੂਣਾ ਕਾਰਬਨ, ਜਲਵਾਯੂ ਅਨੁਕੂਲਨ (SDG 13) ਦੀ ਸੇਵਾ ਵਿੱਚ।',
    resp4L: 'ਅਨਿਸ਼ਚਿਤਤਾ ਤੇ ਪੱਖਪਾਤ', resp4: 'Conformal ਅੰਤਰਾਲ ਔਸਤਨ ਕੈਲੀਬ੍ਰੇਟਿਡ ਹਨ ਪਰ 2025 ਦੇ ਸਿਖਰ ਉੱਤੇ ਘੱਟ ਕਵਰੇਜ ਦੇ ਗਏ, ਇੱਕ ਅਸਫ਼ਲਤਾ ਜੋ ਅਸੀਂ ਲੁਕਾਉਣ ਦੀ ਬਜਾਏ ਪ੍ਰਕਾਸ਼ਿਤ ਕਰਦੇ ਹਾਂ, ਝੋਨਾ-ਲਵਾਈ ਦੇ ਗ਼ਲਤ-ਸਕਾਰਾਤਮਕ ਤੇ ਦੋਵੇਂ ਸਥਾਨਿਕ ਫ਼ੋਲਡ ਦੇ ਨਾਲ।',
    liveTitle: 'ਇਸ ਮਾਨਸੂਨ ਲਾਈਵ',
    liveHead: 'ਲਾਈਵ ਮਾਨੀਟਰ · ਹਰ 6 ਘੰਟੇ ਆਪਣੇ ਆਪ, ਬਿਨਾਂ ਕੁੰਜੀ, ਬਿਨਾਂ ਖਾਤੇ',
    liveCap: 'ਪੰਜਾਬ ਉੱਤੇ ਨਵੀਨਤਮ Sentinel-1 ਰਾਡਾਰ ਪਾਸ, ਜਨਤਕ CI ਉੱਤੇ ਆਪਣੇ ਆਪ ਲਿਆਂਦਾ ਤੇ ਰੈਂਡਰ ਕੀਤਾ। ਗੂੜ੍ਹੇ ਰੰਗ ਖੜ੍ਹਾ ਪਾਣੀ ਹਨ।',
    liveAlt: 'ਪੰਜਾਬ ਉੱਤੇ ਨਵੀਨਤਮ Sentinel-1 ਰਾਡਾਰ ਪਾਸ',
    liveLastL: 'ਨਵੀਨਤਮ ਪਾਸ',
    liveCovL: 'ਕਵਰੇਜ',
    liveFloodL: 'ਚਿੰਨ੍ਹਿਤ ਪਾਣੀ',
    liveLoading: 'ਲੱਭਿਆ ਜਾ ਰਿਹਾ ਹੈ…',
  },
};

const MODULES = [
  {
    tag: null,
    en: {name: 'Atlas', desc: 'Sentinel-1 radar change detection and a Random Forest map of standing water, per district, with how long each area stayed submerged.'},
    hi: {name: 'एटलस', desc: 'Sentinel-1 रडार परिवर्तन-पहचान और स्थिर जल का Random Forest नक्शा, हर ज़िले के लिए, यह भी कि कौन-सा क्षेत्र कितने समय जलमग्न रहा।'},
    pa: {name: 'ਐਟਲਸ', desc: 'Sentinel-1 ਰਾਡਾਰ ਤਬਦੀਲੀ-ਪਛਾਣ ਅਤੇ ਖੜ੍ਹੇ ਪਾਣੀ ਦਾ Random Forest ਨਕਸ਼ਾ, ਹਰ ਜ਼ਿਲ੍ਹੇ ਲਈ, ਨਾਲੇ ਕਿਹੜਾ ਖੇਤਰ ਕਿੰਨਾ ਚਿਰ ਡੁੱਬਿਆ ਰਿਹਾ।'},
  },
  {
    tag: null,
    en: {name: 'Decade hazard', desc: 'Eleven monsoons turned into recurrence zones and 91 tehsils scored, naming the places that flood again and again.'},
    hi: {name: 'दशक जोखिम', desc: 'ग्यारह मानसून पुनरावृत्ति-क्षेत्रों में बदले और 91 तहसीलें स्कोर कीं, उन जगहों को नाम देते हुए जो बार-बार डूबती हैं।'},
    pa: {name: 'ਦਹਾਕਾ ਖ਼ਤਰਾ', desc: 'ਗਿਆਰਾਂ ਮਾਨਸੂਨ ਮੁੜ-ਆਵਰਤੀ ਖੇਤਰਾਂ ਵਿੱਚ ਬਦਲੇ ਅਤੇ 91 ਤਹਿਸੀਲਾਂ ਸਕੋਰ ਕੀਤੀਆਂ, ਉਹ ਥਾਵਾਂ ਨਾਮ ਲੈ ਕੇ ਜੋ ਵਾਰ-ਵਾਰ ਡੁੱਬਦੀਆਂ ਹਨ।'},
  },
  {
    tag: null,
    en: {name: 'Impact', desc: "Crop hectares lost, the damage band in rupees, population exposed, and dam headroom, all on the government's own yield figures."},
    hi: {name: 'प्रभाव', desc: 'डूबी फ़सल हेक्टेयर, रुपयों में क्षति-बैंड, प्रभावित जनसंख्या, और बाँध हेडरूम, सब सरकार के अपने उपज आँकड़ों पर।'},
    pa: {name: 'ਪ੍ਰਭਾਵ', desc: 'ਡੁੱਬੀ ਫ਼ਸਲ ਹੈਕਟੇਅਰ, ਰੁਪਏ ਵਿੱਚ ਨੁਕਸਾਨ-ਬੈਂਡ, ਪ੍ਰਭਾਵਿਤ ਆਬਾਦੀ, ਅਤੇ ਡੈਮ ਹੈੱਡਰੂਮ, ਸਭ ਸਰਕਾਰ ਦੇ ਆਪਣੇ ਝਾੜ ਅੰਕੜਿਆਂ ਉੱਤੇ।'},
  },
  {
    tag: 'AI',
    en: {name: 'Forecaster', desc: "An XGBoost district-risk model trained on the pipeline's own decade of labels, explained with SHAP and stress-tested by ablation."},
    hi: {name: 'पूर्वानुमानक', desc: 'पाइपलाइन के अपने दशक-भर के लेबल पर प्रशिक्षित XGBoost ज़िला-जोखिम मॉडल, SHAP से समझाया और ablation से परखा।'},
    pa: {name: 'ਭਵਿੱਖਬਾਣੀਕਾਰ', desc: 'ਪਾਈਪਲਾਈਨ ਦੇ ਆਪਣੇ ਦਹਾਕੇ ਦੇ ਲੇਬਲਾਂ ਉੱਤੇ ਸਿੱਖਿਆ XGBoost ਜ਼ਿਲ੍ਹਾ-ਖ਼ਤਰਾ ਮਾਡਲ, SHAP ਨਾਲ ਸਮਝਾਇਆ ਤੇ ablation ਨਾਲ ਪਰਖਿਆ।'},
  },
  {
    tag: null,
    en: {name: 'Live monitor', desc: 'Each new satellite pass becomes a district damage figure and an auto-written alert in Punjabi, Hindi, and English, automatically.'},
    hi: {name: 'लाइव मॉनिटर', desc: 'हर नया सैटेलाइट पास अपने आप ज़िला क्षति-आँकड़ा और पंजाबी, हिन्दी व अंग्रेज़ी में स्वतः-लिखित चेतावनी बन जाता है।'},
    pa: {name: 'ਲਾਈਵ ਮਾਨੀਟਰ', desc: 'ਹਰ ਨਵਾਂ ਸੈਟੇਲਾਈਟ ਪਾਸ ਆਪਣੇ ਆਪ ਜ਼ਿਲ੍ਹਾ ਨੁਕਸਾਨ-ਅੰਕੜਾ ਅਤੇ ਪੰਜਾਬੀ, ਹਿੰਦੀ ਤੇ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਸਵੈ-ਲਿਖਤ ਚੇਤਾਵਨੀ ਬਣ ਜਾਂਦਾ ਹੈ।'},
  },
];

// The live monitor: rendered as a deliberate dark console panel (Astryx dark
// mode) so the dark radar image sits natively instead of clashing with the
// warm page. This is the novel, working part, so it leads.
function LiveSection({t}) {
  const [live, setLive] = useState(null);
  useEffect(() => {
    let on = true;
    fetch(RAW + 'monitor/latest.json')
      .then((r) => r.json())
      .then((j) => on && setLive(j))
      .catch(() => {});
    return () => {
      on = false;
    };
  }, []);
  const pct = live ? Math.round((live.coverage_fraction || 0) * 100) + '%' : '—';
  const km2 = live ? (+live.total_flooded_km2 || 0).toLocaleString() + ' km²' : '—';
  return (
    <Band dividers={['bottom']} paddingBlock={8}>
      <VStack gap={5} id="live">
        <HStack gap={3} vAlign="center">
          <StatusDot variant="accent" label="live" isPulsing />
          <Text type="label" color="secondary">{t.liveHead}</Text>
        </HStack>
        <HStack gap={3} vAlign="center">
          <Text type="label" color="accent">02</Text>
          <Heading level={2}>{t.liveTitle}</Heading>
        </HStack>
        <Grid columns={{minWidth: 320, max: 2}} gap={6} align="stretch">
          <Card padding={1}>
            <img
              src={RAW + 'monitor/latest.jpg'}
              alt={t.liveAlt}
              loading="lazy"
              style={{width: '100%', height: 'auto', display: 'block', borderRadius: 'var(--radius-inner, 2px)', filter: 'saturate(1.1) contrast(1.03)'}}
            />
          </Card>
          <VStack gap={5} justify="center">
            <StatBig label={t.liveLastL} value={live ? live.latest_pass : t.liveLoading} />
            <Divider />
            <StatBig label={t.liveCovL} value={pct} />
            <Divider />
            <StatBig label={t.liveFloodL} value={km2} />
            <Divider />
            <Text type="supporting" color="secondary">{t.liveCap}</Text>
          </VStack>
        </Grid>
      </VStack>
    </Band>
  );
}

export default function App() {
  const [lang, setLang] = useState('en');
  const t = T[lang];

  return (
    <AppShell height="auto" contentPadding={0} variant="surface">
      {/* masthead */}
      <Band dividers={['bottom']} paddingBlock={3}>
        <HStack justify="between" vAlign="center" width="100%">
          <Text type="label" color="primary">SAILAAB</Text>
          <HStack gap={1} vAlign="center">
            {LANGS.map((l) => (
              <Button
                key={l.code}
                variant={lang === l.code ? 'primary' : 'ghost'}
                onClick={() => setLang(l.code)}
              >
                {l.label}
              </Button>
            ))}
          </HStack>
        </HStack>
      </Band>

      {/* hero */}
      <Band paddingBlock={9}>
        <VStack gap={4} maxWidth={740}>
          <Text type="label" color="secondary">{t.eyebrow}</Text>
          <Heading level={1} type="display-1">{t.h1}</Heading>
          <Text type="large" color="secondary">{t.lede}</Text>
          <HStack gap={5} vAlign="center" wrap="wrap">
            <Link href="#forecast" isStandalone>{t.seeLive}</Link>
            <Link href="https://github.com/bakathefish/Flood" isStandalone>{t.source}</Link>
          </HStack>
        </VStack>
      </Band>

      {/* prediction leads, with its alert output; then the monitor and the record */}
      <ForecastSection lang={lang} />
      <AlertSection lang={lang} />
      <LiveSection t={t} />
      <MapSection lang={lang} />

      {/* how it is built */}
      <Band paddingBlock={8} maxWidth={1080}>
        <VStack gap={5} width="100%">
          <HStack gap={3} vAlign="center">
            <Text type="label" color="accent">04</Text>
            <Heading level={2}>{t.sysTitle}</Heading>
          </HStack>
          <VStack gap={2} maxWidth={640}>
            <Text type="large" color="secondary">{t.sysIntro}</Text>
          </VStack>
          <VStack gap={0}>
            {MODULES.map((m, i) => (
              <React.Fragment key={i}>
                <Divider />
                <HStack gap={4} vAlign="start" paddingBlock={3} wrap="wrap">
                  <Text type="supporting" hasTabularNumbers>{String(i + 1).padStart(2, '0')}</Text>
                  <VStack gap={1} width={190}>
                    <HStack gap={2} vAlign="center" wrap="wrap">
                      <Text type="label">{m[lang].name}</Text>
                      {m.tag && <Badge variant="blue" label={m.tag} />}
                    </HStack>
                  </VStack>
                  <VStack width={440}>
                    <Text color="secondary">{m[lang].desc}</Text>
                  </VStack>
                </HStack>
              </React.Fragment>
            ))}
          </VStack>
          <VStack gap={2} maxWidth={800}>
            <Text type="label" color="accent">{t.techL}</Text>
            <Text color="secondary">{t.tech}</Text>
          </VStack>
        </VStack>
      </Band>

      {/* responsible AI: ethics, privacy, environment, uncertainty */}
      <Band paddingBlock={7} dividers={['bottom']}>
        <VStack gap={4} width="100%">
          <Heading level={2}>{t.respTitle}</Heading>
          <Grid columns={{minWidth: 260, max: 2}} gap={5}>
            <VStack gap={1}><Text type="label" color="accent">{t.resp1L}</Text><Text color="secondary">{t.resp1}</Text></VStack>
            <VStack gap={1}><Text type="label" color="accent">{t.resp2L}</Text><Text color="secondary">{t.resp2}</Text></VStack>
            <VStack gap={1}><Text type="label" color="accent">{t.resp3L}</Text><Text color="secondary">{t.resp3}</Text></VStack>
            <VStack gap={1}><Text type="label" color="accent">{t.resp4L}</Text><Text color="secondary">{t.resp4}</Text></VStack>
          </Grid>
        </VStack>
      </Band>

      {/* context: the gap */}
      <Band paddingBlock={6} dividers={['top', 'bottom']}>
        <HStack gap={5} vAlign="center" wrap="wrap">
          <Heading level={2} type="display-1" color="accent">0</Heading>
          <VStack maxWidth={520}>
            <Text type="large" color="secondary">{t.gap}</Text>
          </VStack>
        </HStack>
      </Band>

      {/* context: who it is for + inclusion + SDGs */}
      <Band paddingBlock={6} dividers={['bottom']}>
        <Grid columns={{minWidth: 240, max: 3}} gap={5} width="100%">
          <VStack gap={2}>
            <Text type="label" color="secondary">{t.who1L}</Text>
            <Text color="secondary">{t.who1}</Text>
          </VStack>
          <VStack gap={2}>
            <Text type="label" color="secondary">{t.who2L}</Text>
            <Text color="secondary">{t.who2}</Text>
          </VStack>
          <VStack gap={2}>
            <Text type="label" color="secondary">{t.who3L}</Text>
            <Text color="secondary">{t.who3}</Text>
          </VStack>
        </Grid>
      </Band>

      {/* proof, at the very end */}
      <ProofSection lang={lang} />

      {/* footer */}
      <Section variant="transparent" padding={0} dividers={['top']}>
        <HStack justify="center" width="100%">
          <VStack width="100%" maxWidth={1080} paddingInline={4} paddingBlock={5} gap={1}>
            <Text type="supporting" color="secondary">SAILAAB · built by a Punjab student during the 2026 monsoon · India AI Impact Festival 2026 · Code MIT · Maps &amp; tables CC-BY-4.0 · Contains modified Copernicus Sentinel &amp; CEMS-GFM data</Text>
            <Link href="https://github.com/bakathefish/Flood" isStandalone>github.com/bakathefish/Flood</Link>
          </VStack>
        </HStack>
      </Section>
    </AppShell>
  );
}
