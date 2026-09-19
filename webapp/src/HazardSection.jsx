import React, {useState, useEffect} from 'react';
import {Section} from '@astryxdesign/core/Section';
import {VStack} from '@astryxdesign/core/VStack';
import {HStack} from '@astryxdesign/core/HStack';
import {Text} from '@astryxdesign/core/Text';
import {Heading} from '@astryxdesign/core/Heading';
import {Badge} from '@astryxdesign/core/Badge';
import {StatusDot} from '@astryxdesign/core/StatusDot';
import {Banner} from '@astryxdesign/core/Banner';
import {Link} from '@astryxdesign/core/Link';
import {Divider} from '@astryxdesign/core/Divider';
import {HORIZONS, resolveHazardState} from './hazardSchema';

const RAW = 'https://raw.githubusercontent.com/bakathefish/Flood/master/';
const FEED = RAW + 'punjabflood/outputs/forecast/latest.json';
const VERIFY = 'https://github.com/bakathefish/Flood/blob/master/punjabflood/docs/verification.md';
const RECORDS = 'https://github.com/bakathefish/Flood/blob/master/punjabflood/outputs/forecast/';

// Every string the section shows, in the three languages of the page.
const H_T = {
  en: {
    no: '01', title: 'River watch',
    lead: 'Will Bhakra or Pong have to open its spillway in the next five days?',
    intro: 'Punjab floods when a dam is already near full and heavy rain falls on the hills above it. Every morning this watch reads the dam bulletin, the rain that fell over the last six days, four weather models and a 51-member ensemble for the next five, and at Bhakra the snow melting above the rain gauges. It then answers one question per dam: the chance the spillway has to open on each of the next five days.',
    issued: (d, b) => `Issued ${d}${b ? `, dam readings as on ${b}` : ''}. Updated once a day by the public pipeline.`,
    live: 'live', stale: 'stale', off: 'unreachable', bad: 'unreadable',
    staleTitle: (n) => `This watch is ${n} days old.`,
    staleDesc: 'The daily run has not produced a newer one. The figures below are the last issued, shown with their date, not today’s state.',
    offTitle: 'The river watch is unreachable right now.',
    offDesc: 'This is a connection problem, not an all-clear. Retry shortly.',
    badTitle: 'The river watch feed could not be read.',
    badDesc: 'The file arrived but is not in the form the page expects. This is a publishing fault, not an all-clear.',
    loading: 'Reading the latest watch…',
    damsHead: 'Dams',
    colDam: 'Dam', colLevel: 'Level', colStore: 'Full', colFlow: 'In → out (cusecs)',
    colChance: 'Chance the spillway is forced, day 1 to 5',
    chanceNote: 'Each cell is the share of the ensemble in which the reservoir runs out of room by that day, under the widest error budget the model prints (rain spread, ordinary inflow error and the flood-scale volume error). A dash means the feed did not carry that number.',
    noRanjit: 'Ranjit Sagar has no public daily bulletin, so it has no dam row; its catchment is watched for rain below.',
    wxHead: 'Rain over the catchments',
    colCatch: 'Catchment', colFallen: 'Fallen', colNext: 'Next 3 days',
    days: (n) => `${n} d`,
    quiet: 'quiet', watch: 'watch', alert: 'alert', unknown: 'unknown',
    wxNote: 'Fallen rain is the IMD real-time grid where it covers the catchment and a model’s past days where it does not. The next three days are the primary model’s total, with its rank against the record for this date (p90 means only one date in ten has seen more). Watch and alert levels were fixed before this season and never tuned to it.',
    reachHead: 'Where the water arrives',
    colStation: 'Station', colPeak: 'Peak (cusecs)', colDate: 'Date', colClass: 'Class',
    below: 'below Low',
    reachNote: 'Dam releases routed downstream with the Punjab Water Resources Department’s travel times and classed against its own Low, Medium and High thresholds.',
    snow: (recent, days, fc, pack) => `Snowmelt at Bhakra: ${recent} mm of water over the last ${days} days, ${fc} mm expected over the next five days; pack ${pack} mm (a bookkeeping figure from a degree-day model, not a measured depth). The inflow model carries it.`,
    snowOff: 'Snowmelt at Bhakra: the melt inputs could not be built for this run, so the term contributed nothing.',
    verify: 'How well it has done so far',
    record: 'This run’s record',
  },
  hi: {
    no: '01', title: 'नदी निगरानी',
    lead: 'क्या अगले पाँच दिनों में भाखड़ा या पौंग को अपना स्पिलवे खोलना पड़ेगा?',
    intro: 'पंजाब में बाढ़ तब आती है जब बाँध पहले से लगभग भरा हो और उसके ऊपर की पहाड़ियों पर भारी बारिश हो। यह निगरानी हर सुबह बाँध का बुलेटिन, पिछले छह दिनों की बारिश, अगले पाँच दिनों के लिए चार मौसम मॉडल और 51 सदस्यों का एन्सेम्बल, और भाखड़ा पर वर्षामापी के ऊपर पिघलती बर्फ़ पढ़ती है। फिर हर बाँध के लिए एक सवाल का जवाब देती है: अगले पाँच दिनों में हर दिन स्पिलवे खुलने की संभावना।',
    issued: (d, b) => `जारी ${d}${b ? `, बाँध के आँकड़े ${b} तक` : ''}। सार्वजनिक पाइपलाइन द्वारा दिन में एक बार अपडेट।`,
    live: 'लाइव', stale: 'पुराना', off: 'अनुपलब्ध', bad: 'अपठनीय',
    staleTitle: (n) => `यह निगरानी ${n} दिन पुरानी है।`,
    staleDesc: 'दैनिक रन ने नयी निगरानी नहीं बनाई। नीचे के आँकड़े अंतिम जारी हैं, अपनी तारीख़ के साथ, आज की स्थिति नहीं।',
    offTitle: 'नदी निगरानी अभी अनुपलब्ध है।',
    offDesc: 'यह कनेक्शन समस्या है, ऑल-क्लियर नहीं। थोड़ी देर बाद पुनः प्रयास करें।',
    badTitle: 'नदी निगरानी की फ़ीड पढ़ी नहीं जा सकी।',
    badDesc: 'फ़ाइल आई तो, पर उस रूप में नहीं जिसकी पेज को अपेक्षा है। यह प्रकाशन की गड़बड़ी है, ऑल-क्लियर नहीं।',
    loading: 'नवीनतम निगरानी पढ़ी जा रही है…',
    damsHead: 'बाँध',
    colDam: 'बाँध', colLevel: 'स्तर', colStore: 'भरा', colFlow: 'आवक → निकास (क्यूसेक)',
    colChance: 'स्पिलवे खुलने की संभावना, दिन 1 से 5',
    chanceNote: 'हर खाना एन्सेम्बल का वह हिस्सा है जिसमें जलाशय की जगह उस दिन तक खत्म हो जाती है, मॉडल के सबसे चौड़े त्रुटि-बजट के तहत (बारिश का फैलाव, सामान्य आवक त्रुटि और बाढ़-स्तर आयतन त्रुटि)। डैश का अर्थ है कि फ़ीड में वह आँकड़ा नहीं था।',
    noRanjit: 'रणजीत सागर का कोई सार्वजनिक दैनिक बुलेटिन नहीं, इसलिए उसकी बाँध पंक्ति नहीं है; नीचे उसके जलग्रहण क्षेत्र की बारिश देखी जाती है।',
    wxHead: 'जलग्रहण क्षेत्रों पर बारिश',
    colCatch: 'क्षेत्र', colFallen: 'हुई', colNext: 'अगले 3 दिन',
    days: (n) => `${n} दिन`,
    quiet: 'शांत', watch: 'निगरानी', alert: 'अलर्ट', unknown: 'अज्ञात',
    wxNote: 'हुई बारिश IMD रियल-टाइम ग्रिड से है जहाँ वह क्षेत्र को कवर करती है, अन्यथा मॉडल के पिछले दिनों से। अगले तीन दिन मुख्य मॉडल का योग हैं, इस तारीख़ के रिकॉर्ड के सापेक्ष रैंक के साथ (p90 यानी दस में से केवल एक तारीख़ पर इससे अधिक हुई)। निगरानी और अलर्ट स्तर इस मौसम से पहले तय किए गए थे और इस पर कभी ट्यून नहीं किए गए।',
    reachHead: 'पानी कहाँ पहुँचता है',
    colStation: 'स्टेशन', colPeak: 'शिखर (क्यूसेक)', colDate: 'तारीख़', colClass: 'वर्ग',
    below: 'निम्न (Low) से नीचे',
    reachNote: 'बाँधों का निकास पंजाब जल संसाधन विभाग के यात्रा-समय से नीचे पहुँचाया गया और उसी की निम्न, मध्यम और उच्च (Low, Medium, High) सीमाओं से वर्गीकृत।',
    snow: (recent, days, fc, pack) => `भाखड़ा पर बर्फ़ पिघलाव: पिछले ${days} दिनों में ${recent} mm पानी, अगले पाँच दिनों में ${fc} mm अपेक्षित; पैक ${pack} mm (डिग्री-डे मॉडल का लेखा आँकड़ा, मापी गई गहराई नहीं)। आवक मॉडल इसे शामिल करता है।`,
    snowOff: 'भाखड़ा पर बर्फ़ पिघलाव: इस रन के लिए पिघलाव इनपुट नहीं बन सके, इसलिए इस पद का योगदान शून्य रहा।',
    verify: 'अब तक यह कितना सही रहा',
    record: 'इस रन का रिकॉर्ड',
  },
  pa: {
    no: '01', title: 'ਦਰਿਆ ਨਿਗਰਾਨੀ',
    lead: 'ਕੀ ਅਗਲੇ ਪੰਜ ਦਿਨਾਂ ਵਿੱਚ ਭਾਖੜਾ ਜਾਂ ਪੌਂਗ ਨੂੰ ਆਪਣਾ ਸਪਿਲਵੇ ਖੋਲ੍ਹਣਾ ਪਵੇਗਾ?',
    intro: 'ਪੰਜਾਬ ਵਿੱਚ ਹੜ੍ਹ ਉਦੋਂ ਆਉਂਦਾ ਹੈ ਜਦੋਂ ਡੈਮ ਪਹਿਲਾਂ ਹੀ ਲਗਭਗ ਭਰਿਆ ਹੋਵੇ ਅਤੇ ਉਸ ਦੇ ਉੱਪਰਲੀਆਂ ਪਹਾੜੀਆਂ ਉੱਤੇ ਭਾਰੀ ਮੀਂਹ ਪਵੇ। ਇਹ ਨਿਗਰਾਨੀ ਹਰ ਸਵੇਰ ਡੈਮ ਦਾ ਬੁਲੇਟਿਨ, ਪਿਛਲੇ ਛੇ ਦਿਨਾਂ ਦਾ ਮੀਂਹ, ਅਗਲੇ ਪੰਜ ਦਿਨਾਂ ਲਈ ਚਾਰ ਮੌਸਮ ਮਾਡਲ ਅਤੇ 51 ਮੈਂਬਰਾਂ ਦਾ ਐਨਸੈਂਬਲ, ਅਤੇ ਭਾਖੜਾ ਉੱਤੇ ਮੀਂਹ-ਮਾਪਕਾਂ ਤੋਂ ਉੱਪਰ ਪਿਘਲਦੀ ਬਰਫ਼ ਪੜ੍ਹਦੀ ਹੈ। ਫਿਰ ਹਰ ਡੈਮ ਲਈ ਇੱਕ ਸਵਾਲ ਦਾ ਜਵਾਬ ਦਿੰਦੀ ਹੈ: ਅਗਲੇ ਪੰਜ ਦਿਨਾਂ ਵਿੱਚ ਹਰ ਦਿਨ ਸਪਿਲਵੇ ਖੁੱਲਣ ਦੀ ਸੰਭਾਵਨਾ।',
    issued: (d, b) => `ਜਾਰੀ ${d}${b ? `, ਡੈਮ ਦੇ ਅੰਕੜੇ ${b} ਤੱਕ` : ''}। ਜਨਤਕ ਪਾਈਪਲਾਈਨ ਵੱਲੋਂ ਦਿਨ ਵਿੱਚ ਇੱਕ ਵਾਰ ਅਪਡੇਟ।`,
    live: 'ਲਾਈਵ', stale: 'ਪੁਰਾਣਾ', off: 'ਅਣਉਪਲਬਧ', bad: 'ਅਪੜ੍ਹਨਯੋਗ',
    staleTitle: (n) => `ਇਹ ਨਿਗਰਾਨੀ ${n} ਦਿਨ ਪੁਰਾਣੀ ਹੈ।`,
    staleDesc: 'ਰੋਜ਼ਾਨਾ ਰਨ ਨੇ ਨਵੀਂ ਨਿਗਰਾਨੀ ਨਹੀਂ ਬਣਾਈ। ਹੇਠਾਂ ਦੇ ਅੰਕੜੇ ਆਖਰੀ ਜਾਰੀ ਹਨ, ਆਪਣੀ ਤਾਰੀਖ਼ ਨਾਲ, ਅੱਜ ਦੀ ਹਾਲਤ ਨਹੀਂ।',
    offTitle: 'ਦਰਿਆ ਨਿਗਰਾਨੀ ਹੁਣੇ ਅਣਉਪਲਬਧ ਹੈ।',
    offDesc: 'ਇਹ ਕਨੈਕਸ਼ਨ ਸਮੱਸਿਆ ਹੈ, ਆਲ-ਕਲੀਅਰ ਨਹੀਂ। ਥੋੜ੍ਹੀ ਦੇਰ ਬਾਅਦ ਮੁੜ ਕੋਸ਼ਿਸ਼ ਕਰੋ।',
    badTitle: 'ਦਰਿਆ ਨਿਗਰਾਨੀ ਦੀ ਫ਼ੀਡ ਪੜ੍ਹੀ ਨਹੀਂ ਜਾ ਸਕੀ।',
    badDesc: 'ਫ਼ਾਈਲ ਆਈ ਤਾਂ, ਪਰ ਉਸ ਰੂਪ ਵਿੱਚ ਨਹੀਂ ਜਿਸ ਦੀ ਪੰਨੇ ਨੂੰ ਉਮੀਦ ਹੈ। ਇਹ ਪ੍ਰਕਾਸ਼ਨ ਦੀ ਗੜਬੜ ਹੈ, ਆਲ-ਕਲੀਅਰ ਨਹੀਂ।',
    loading: 'ਨਵੀਨਤਮ ਨਿਗਰਾਨੀ ਪੜ੍ਹੀ ਜਾ ਰਹੀ ਹੈ…',
    damsHead: 'ਡੈਮ',
    colDam: 'ਡੈਮ', colLevel: 'ਪੱਧਰ', colStore: 'ਭਰਿਆ', colFlow: 'ਆਮਦ → ਨਿਕਾਸ (ਕਿਊਸੈਕ)',
    colChance: 'ਸਪਿਲਵੇ ਖੁੱਲਣ ਦੀ ਸੰਭਾਵਨਾ, ਦਿਨ 1 ਤੋਂ 5',
    chanceNote: 'ਹਰ ਖਾਨਾ ਐਨਸੈਂਬਲ ਦਾ ਉਹ ਹਿੱਸਾ ਹੈ ਜਿਸ ਵਿੱਚ ਜਲ ਭੰਡਾਰ ਦੀ ਥਾਂ ਉਸ ਦਿਨ ਤੱਕ ਮੁੱਕ ਜਾਂਦੀ ਹੈ, ਮਾਡਲ ਦੇ ਸਭ ਤੋਂ ਚੌੜੇ ਤਰੁਟੀ-ਬਜਟ ਹੇਠ (ਮੀਂਹ ਦਾ ਫੈਲਾਅ, ਆਮ ਆਮਦ ਤਰੁਟੀ ਅਤੇ ਹੜ੍ਹ-ਪੱਧਰ ਆਇਤਨ ਤਰੁਟੀ)। ਡੈਸ਼ ਦਾ ਮਤਲਬ ਹੈ ਕਿ ਫ਼ੀਡ ਵਿੱਚ ਉਹ ਅੰਕੜਾ ਨਹੀਂ ਸੀ।',
    noRanjit: 'ਰਣਜੀਤ ਸਾਗਰ ਦਾ ਕੋਈ ਜਨਤਕ ਰੋਜ਼ਾਨਾ ਬੁਲੇਟਿਨ ਨਹੀਂ, ਇਸ ਲਈ ਉਸ ਦੀ ਡੈਮ ਕਤਾਰ ਨਹੀਂ; ਹੇਠਾਂ ਉਸ ਦੇ ਜਲ-ਗ੍ਰਹਿਣ ਖੇਤਰ ਦਾ ਮੀਂਹ ਦੇਖਿਆ ਜਾਂਦਾ ਹੈ।',
    wxHead: 'ਜਲ-ਗ੍ਰਹਿਣ ਖੇਤਰਾਂ ਉੱਤੇ ਮੀਂਹ',
    colCatch: 'ਖੇਤਰ', colFallen: 'ਪਿਆ', colNext: 'ਅਗਲੇ 3 ਦਿਨ',
    days: (n) => `${n} ਦਿਨ`,
    quiet: 'ਸ਼ਾਂਤ', watch: 'ਨਿਗਰਾਨੀ', alert: 'ਅਲਰਟ', unknown: 'ਅਣਜਾਣ',
    wxNote: 'ਪਿਆ ਮੀਂਹ IMD ਰੀਅਲ-ਟਾਈਮ ਗਰਿਡ ਤੋਂ ਹੈ ਜਿੱਥੇ ਉਹ ਖੇਤਰ ਨੂੰ ਕਵਰ ਕਰਦੀ ਹੈ, ਨਹੀਂ ਤਾਂ ਮਾਡਲ ਦੇ ਪਿਛਲੇ ਦਿਨਾਂ ਤੋਂ। ਅਗਲੇ ਤਿੰਨ ਦਿਨ ਮੁੱਖ ਮਾਡਲ ਦਾ ਜੋੜ ਹਨ, ਇਸ ਤਾਰੀਖ਼ ਦੇ ਰਿਕਾਰਡ ਦੇ ਮੁਕਾਬਲੇ ਰੈਂਕ ਨਾਲ (p90 ਮਤਲਬ ਦਸ ਵਿੱਚੋਂ ਸਿਰਫ਼ ਇੱਕ ਤਾਰੀਖ਼ ਨੇ ਇਸ ਤੋਂ ਵੱਧ ਵੇਖਿਆ)। ਨਿਗਰਾਨੀ ਅਤੇ ਅਲਰਟ ਪੱਧਰ ਇਸ ਮੌਸਮ ਤੋਂ ਪਹਿਲਾਂ ਤੈਅ ਕੀਤੇ ਗਏ ਸਨ ਅਤੇ ਇਸ ਉੱਤੇ ਕਦੇ ਟਿਊਨ ਨਹੀਂ ਕੀਤੇ ਗਏ।',
    reachHead: 'ਪਾਣੀ ਕਿੱਥੇ ਪਹੁੰਚਦਾ ਹੈ',
    colStation: 'ਸਟੇਸ਼ਨ', colPeak: 'ਸਿਖਰ (ਕਿਊਸੈਕ)', colDate: 'ਤਾਰੀਖ਼', colClass: 'ਵਰਗ',
    below: 'ਘੱਟ (Low) ਤੋਂ ਹੇਠਾਂ',
    reachNote: 'ਡੈਮਾਂ ਦਾ ਨਿਕਾਸ ਪੰਜਾਬ ਜਲ ਸਰੋਤ ਵਿਭਾਗ ਦੇ ਸਫ਼ਰ-ਸਮੇਂ ਨਾਲ ਹੇਠਾਂ ਪਹੁੰਚਾਇਆ ਗਿਆ ਅਤੇ ਉਸੇ ਦੀਆਂ ਘੱਟ, ਦਰਮਿਆਨਾ ਅਤੇ ਉੱਚ (Low, Medium, High) ਹੱਦਾਂ ਨਾਲ ਵਰਗਿਆਇਆ।',
    snow: (recent, days, fc, pack) => `ਭਾਖੜਾ ਉੱਤੇ ਬਰਫ਼ ਪਿਘਲਾਅ: ਪਿਛਲੇ ${days} ਦਿਨਾਂ ਵਿੱਚ ${recent} mm ਪਾਣੀ, ਅਗਲੇ ਪੰਜ ਦਿਨਾਂ ਵਿੱਚ ${fc} mm ਦੀ ਉਮੀਦ; ਪੈਕ ${pack} mm (ਡਿਗਰੀ-ਡੇ ਮਾਡਲ ਦਾ ਹਿਸਾਬੀ ਅੰਕੜਾ, ਮਾਪੀ ਹੋਈ ਡੂੰਘਾਈ ਨਹੀਂ)। ਆਮਦ ਮਾਡਲ ਇਸ ਨੂੰ ਸ਼ਾਮਲ ਕਰਦਾ ਹੈ।`,
    snowOff: 'ਭਾਖੜਾ ਉੱਤੇ ਬਰਫ਼ ਪਿਘਲਾਅ: ਇਸ ਰਨ ਲਈ ਪਿਘਲਾਅ ਇਨਪੁਟ ਨਹੀਂ ਬਣ ਸਕੇ, ਇਸ ਲਈ ਇਸ ਪਦ ਦਾ ਯੋਗਦਾਨ ਸਿਫ਼ਰ ਰਿਹਾ।',
    verify: 'ਹੁਣ ਤੱਕ ਇਹ ਕਿੰਨਾ ਸਹੀ ਰਿਹਾ',
    record: 'ਇਸ ਰਨ ਦਾ ਰਿਕਾਰਡ',
  },
};

// Indian digit grouping for cusecs; "—" for anything the feed did not carry.
function cusecs(x) {
  return x === null ? '—' : Math.round(x).toLocaleString('en-IN');
}

function pct(p) {
  return p === null ? '—' : `${Math.round(p * 100)}%`;
}

function ColHead({children, width, justify}) {
  return (
    <VStack width={width} maxWidth="100%" hAlign={justify === 'end' ? 'end' : 'start'}>
      <Text type="label" color="secondary">{children}</Text>
    </VStack>
  );
}

function Cell({children, width, justify, type = 'code', color = 'primary'}) {
  return (
    <VStack width={width} maxWidth="100%" hAlign={justify === 'end' ? 'end' : 'start'}>
      <Text type={type} color={color} hasTabularNumbers>{children}</Text>
    </VStack>
  );
}

function LevelChip({level, t}) {
  if (level === 'alert') return <Badge variant="error" label={t.alert} />;
  if (level === 'watch') return <Badge variant="orange" label={t.watch} />;
  if (level === 'quiet') {
    return (
      <HStack gap={2} vAlign="center">
        <StatusDot variant="neutral" label={t.quiet} />
        <Text type="supporting" color="secondary">{t.quiet}</Text>
      </HStack>
    );
  }
  return <Badge variant="blue" label={t.unknown} />;
}

export default function HazardSection({lang}) {
  const t = H_T[lang] || H_T.en;
  const [feed, setFeed] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let on = true;
    fetch(FEED)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((j) => { if (on) { setFeed(j); setFailed(false); } })
      // A swallowed failure leaves the section blank, and blank reads as
      // nothing to report. The page has to say it does not know.
      .catch(() => { if (on) { setFeed(null); setFailed(true); } });
    return () => { on = false; };
  }, []);

  const h = resolveHazardState(feed, {fetchFailed: failed, nowMs: Date.now(), lang});
  const watch = h.state === 'watch';
  const dot = h.state === 'unavailable'
    ? {variant: 'warning', label: h.reason === 'malformed' ? t.bad : t.off}
    : h.stale ? {variant: 'warning', label: t.stale} : {variant: 'accent', label: t.live};

  return (
    <Section variant="transparent" padding={0} dividers={['bottom']}>
      <HStack justify="center" width="100%">
        <VStack width="100%" maxWidth={1120} paddingInline={4} paddingBlock={9} gap={6} hAlign="start" id="rivers">
          <VStack width="100%" gap={3}>
            <Divider />
            <HStack gap={4} vAlign="baseline" wrap="wrap" paddingBlock={1}>
              <Text type="code" color="accent">{t.no}</Text>
              <Heading level={2}>{t.title}</Heading>
              <HStack gap={2} vAlign="center">
                <StatusDot variant={dot.variant} label={dot.label} isPulsing={watch && !h.stale} />
                <Text type="label" color="secondary">{dot.label}</Text>
              </HStack>
            </HStack>
          </VStack>
          <VStack maxWidth={900}>
            <Heading level={3} type="display-3">{t.lead}</Heading>
          </VStack>
          <VStack maxWidth={680} gap={4}>
            <Text type="large" color="secondary">{t.intro}</Text>
            {watch && <Text color="secondary">{t.issued(h.issue_label, h.bulletin_label)}</Text>}
          </VStack>

          {h.state === 'loading' && (
            <Text color="secondary">{t.loading}</Text>
          )}

          {h.state === 'unavailable' && (
            <VStack width="100%" maxWidth={820}>
              <Banner
                status="warning"
                title={h.reason === 'malformed' ? t.badTitle : t.offTitle}
                description={h.reason === 'malformed' ? t.badDesc : t.offDesc}
              />
            </VStack>
          )}

          {watch && h.stale && (
            <VStack width="100%" maxWidth={820}>
              <Banner status="warning" title={t.staleTitle(h.ageDays)} description={t.staleDesc} />
            </VStack>
          )}

          {watch && (
            <>
              {/* The dam board: one ruled row per dam, five horizon cells at
                  the end. The five cells are the section's one loud element;
                  everything else is set quiet around them. */}
              <VStack width="100%" gap={3}>
                <Text type="label" color="accent">{t.damsHead}</Text>
                <VStack width="100%" gap={0}>
                  <HStack gap={4} vAlign="baseline" paddingBlock={2} wrap="wrap" width="100%">
                    <ColHead width={130}>{t.colDam}</ColHead>
                    <ColHead width={110} justify="end">{t.colLevel}</ColHead>
                    <ColHead width={60} justify="end">{t.colStore}</ColHead>
                    <ColHead width={170} justify="end">{t.colFlow}</ColHead>
                    <VStack width={300} maxWidth="100%" hAlign="end" gap={1}>
                      <Text type="label" color="secondary">{t.colChance}</Text>
                      <HStack gap={0} width={300} maxWidth="100%" justify="end">
                        {h.horizon_labels.map((lbl, i) => (
                          <VStack key={HORIZONS[i]} width={60} hAlign="end">
                            <Text type="supporting" color="secondary" hasTabularNumbers>{lbl}</Text>
                          </VStack>
                        ))}
                      </HStack>
                    </VStack>
                  </HStack>
                  {h.dams.map((d) => (
                    <React.Fragment key={d.name}>
                      <Divider />
                      <HStack gap={4} vAlign="center" paddingBlock={3} wrap="wrap" width="100%">
                        <Cell width={130} type="body">{d.label}</Cell>
                        <Cell width={110} justify="end">{d.level_ft === null ? '—' : `${d.level_ft.toFixed(2)} ft`}</Cell>
                        <Cell width={60} justify="end">{d.storage_fraction === null ? '—' : `${Math.round(d.storage_fraction * 100)}%`}</Cell>
                        <Cell width={170} justify="end" color="secondary">{`${cusecs(d.inflow_cusecs)} → ${cusecs(d.outflow_cusecs)}`}</Cell>
                        <HStack gap={0} width={300} maxWidth="100%" justify="end">
                          {HORIZONS.map((day, i) => {
                            const p = d.p[i];
                            const hot = p !== null && p >= 0.5;
                            const warm = p !== null && p >= 0.1 && p < 0.5;
                            return (
                              <VStack key={day} width={60} hAlign="end" gap={0}>
                                {hot
                                  ? <Badge variant="error" label={pct(p)} />
                                  : warm
                                    ? <Badge variant="orange" label={pct(p)} />
                                    : <Text type="code" color={p === null ? 'secondary' : 'primary'} hasTabularNumbers>{pct(p)}</Text>}
                              </VStack>
                            );
                          })}
                        </HStack>
                      </HStack>
                    </React.Fragment>
                  ))}
                  <Divider />
                </VStack>
                <VStack maxWidth={780} gap={1}>
                  <Text type="supporting" color="secondary">{t.chanceNote}</Text>
                  {!h.dams.some((d) => d.name === 'Ranjit Sagar') && (
                    <Text type="supporting" color="secondary">{t.noRanjit}</Text>
                  )}
                </VStack>
              </VStack>

              {h.snowmelt && (
                <VStack maxWidth={780}>
                  <Text color="secondary">
                    {h.snowmelt.applied && h.snowmelt.recent_mm !== null && h.snowmelt.forecast_mm !== null && h.snowmelt.pack_mm !== null
                      ? t.snow(h.snowmelt.recent_mm.toFixed(1), h.snowmelt.recent_days, h.snowmelt.forecast_mm.toFixed(1), Math.round(h.snowmelt.pack_mm))
                      : t.snowOff}
                  </Text>
                </VStack>
              )}

              {h.weather.length > 0 && (
                <VStack width="100%" gap={3}>
                  <Text type="label" color="accent">{t.wxHead}</Text>
                  <VStack width="100%" gap={0}>
                    <HStack gap={4} vAlign="baseline" paddingBlock={2} wrap="wrap" width="100%">
                      <ColHead width={190}>{t.colCatch}</ColHead>
                      <VStack width={110} maxWidth="100%" />
                      <ColHead width={150} justify="end">{t.colFallen}</ColHead>
                      <ColHead width={170} justify="end">{t.colNext}</ColHead>
                    </HStack>
                    {h.weather.map((w) => (
                      <React.Fragment key={w.name}>
                        <Divider />
                        <HStack gap={4} vAlign="center" paddingBlock={2} wrap="wrap" width="100%">
                          <Cell width={190} type="body">{w.label}</Cell>
                          <VStack width={110} maxWidth="100%"><LevelChip level={w.level} t={t} /></VStack>
                          <Cell width={150} justify="end">
                            {w.observed_total_mm === null ? '—' : `${w.observed_total_mm.toFixed(1)} mm`}
                            {w.observed_days === null ? '' : ` / ${t.days(w.observed_days)}`}
                          </Cell>
                          <Cell width={170} justify="end">
                            {w.next3_mm === null ? '—' : `${w.next3_mm.toFixed(1)} mm`}
                            {w.next3_percentile === null ? '' : ` (p${Math.round(w.next3_percentile)})`}
                          </Cell>
                        </HStack>
                      </React.Fragment>
                    ))}
                    <Divider />
                  </VStack>
                  <VStack maxWidth={780}>
                    <Text type="supporting" color="secondary">{t.wxNote}</Text>
                  </VStack>
                </VStack>
              )}

              {h.reaches.length > 0 && (
                <VStack width="100%" gap={3}>
                  <Text type="label" color="accent">{t.reachHead}</Text>
                  <VStack width="100%" gap={0}>
                    <HStack gap={4} vAlign="baseline" paddingBlock={2} wrap="wrap" width="100%">
                      <ColHead width={300}>{t.colStation}</ColHead>
                      <ColHead width={130} justify="end">{t.colPeak}</ColHead>
                      <ColHead width={110} justify="end">{t.colDate}</ColHead>
                      <ColHead width={110} justify="end">{t.colClass}</ColHead>
                    </HStack>
                    {h.reaches.map((r) => (
                      <React.Fragment key={r.station}>
                        <Divider />
                        <HStack gap={4} vAlign="center" paddingBlock={2} wrap="wrap" width="100%">
                          <VStack width={300} maxWidth="100%">
                            <HStack gap={2} vAlign="baseline" wrap="wrap">
                              <Text>{r.label}</Text>
                              {r.river_label && <Text type="supporting" color="secondary">{r.river_label}</Text>}
                            </HStack>
                          </VStack>
                          <Cell width={130} justify="end">{cusecs(r.peak_cusecs)}</Cell>
                          <Cell width={110} justify="end" color="secondary">{r.peak_label || '—'}</Cell>
                          <VStack width={110} maxWidth="100%" hAlign="end">
                            {r.cls === 'High'
                              ? <Badge variant="error" label={r.cls_label} />
                              : r.cls === 'Medium'
                                ? <Badge variant="orange" label={r.cls_label} />
                                : r.cls === 'Low'
                                  ? <Badge variant="blue" label={r.cls_label} />
                                  : <Text type="supporting" color="secondary">{r.cls === 'below' ? t.below : t.unknown}</Text>}
                          </VStack>
                        </HStack>
                      </React.Fragment>
                    ))}
                    <Divider />
                  </VStack>
                  <VStack maxWidth={780}>
                    <Text type="supporting" color="secondary">{t.reachNote}</Text>
                  </VStack>
                </VStack>
              )}

              <VStack maxWidth={780} gap={2}>
                {h.disclaimer && <Text type="supporting" color="secondary">{h.disclaimer}</Text>}
                <HStack gap={5} vAlign="baseline" wrap="wrap">
                  <Link href={VERIFY} isStandalone>{t.verify}</Link>
                  {h.record && <Link href={RECORDS + h.record} isStandalone>{t.record}</Link>}
                </HStack>
              </VStack>
            </>
          )}
        </VStack>
      </HStack>
    </Section>
  );
}
