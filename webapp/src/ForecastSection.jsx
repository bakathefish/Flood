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
import {num, resolveForecastState} from './forecastSchema';

const RAW = 'https://raw.githubusercontent.com/bakathefish/Flood/master/';

const F_T = {
  en: {
    no: '01', title: 'The forecast',
    lead: 'A three-day flood forecast for every district in Punjab.',
    intro: 'Gradient boosting over a decade of daily satellite flood observations, with self-exciting features that carry recent flooding across neighbouring districts. Open, reproducible, running live this monsoon, in a state whose reviewed CWC station table listed no flood-forecast station.',
    explain: 'Every 6 hours it asks one question of each district: will the satellite see flooding here within the next three days? It uses only what is known on the day it runs.',
    boardNote: 'Tested on seasons it had never seen, with the alert level set from earlier seasons only, it raised about 24 alerts a season and roughly one in three was followed by real flooding within three days. It catches about one flood onset in four, so a quiet board is not a guarantee of safety. A district the satellite did not image is listed separately as unknown, never mixed into the ranking and never dropped from the page.',
    liveHead: 'Live risk · this window',
    districtCol: 'District',
    rankCol: 'rank',
    tierCol: 'tier',
    waterCol: 'water now',
    tierWatch: 'watch',
    tierElevated: 'elevated',
    tierLow: 'low',
    legend: 'Tiers, not probabilities. "watch" means the score cleared the alert level measured in back-testing; "elevated" means the district leads today\'s ranking without clearing it. The number beside each row is a ranking score with no calibration behind it: use it to compare districts against each other, never as a chance of flooding.',
    thresholdIs: 'Alert level',
    unknownHead: 'Not imaged this cycle',
    unknownNote: 'The satellite did not return usable coverage for these districts, so no forecast could be made for them. Unknown is not the same as dry.',
    unavailable: 'Forecast unavailable for this cycle: the satellite coverage needed to make it was missing or too old, so no district ranking is shown. This is NOT an all-clear. Absence of imagery is absence of information.',
    inactive: 'The forecaster is outside its season. It is trained and verified on the core monsoon only, and it activates on',
    summary: 'Every season is forecast using only the seasons before it, so the model never sees its own future. Pooled over all district-days its average precision is 0.249 against a 3.07% base rate, but that pooled figure is not its typical season: averaged season by season the mean is 0.176 and the median 0.083. Performance is uneven. It wins clearly in 2025, and in 2023 the same model without the excitation features beats it, 0.243 to 0.145. The ranking is the useful output and the alerting is modest: this is a selective trigger, not a comprehensive warning system. All of it is retrospective and chosen after seeing these seasons; the 2026 monsoon is the real test. The full audit, including a headline number we had to retract, is below.',
    seeProof: 'See how it did in 2025, and the full validation →',
  },
  hi: {
    no: '01', title: 'पूर्वानुमान',
    lead: 'पंजाब के हर ज़िले के लिए तीन दिन का बाढ़ पूर्वानुमान।',
    intro: 'एक दशक के दैनिक सैटेलाइट बाढ़ अवलोकनों पर ग्रेडिएंट बूस्टिंग, जिसमें ऐसी विशेषताएँ हैं जो हाल की बाढ़ को पड़ोसी ज़िलों तक ले जाती हैं। खुला, पुनरुत्पाद्य और इस मानसून लाइव — उस राज्य में जहाँ समीक्षित CWC तालिका में एक भी बाढ़-पूर्वानुमान स्टेशन दर्ज नहीं था।',
    explain: 'हर 6 घंटे यह हर ज़िले से एक सवाल पूछता है: क्या अगले तीन दिनों में सैटेलाइट यहाँ बाढ़ देखेगा? यह केवल उसी दिन तक की जानकारी का उपयोग करता है।',
    boardNote: 'जिन मौसमों को इसने कभी नहीं देखा था, उन पर परीक्षण करने पर, और चेतावनी का स्तर केवल पहले के मौसमों से तय करने पर, इसने प्रति मौसम लगभग 24 चेतावनियाँ दीं और लगभग तीन में से एक के बाद तीन दिनों के भीतर सचमुच बाढ़ आई। यह लगभग चार में से एक बाढ़ की शुरुआत पकड़ता है, इसलिए शांत बोर्ड सुरक्षा की गारंटी नहीं है। जिस ज़िले की सैटेलाइट तस्वीर नहीं मिली, उसे अलग से अज्ञात के रूप में दिखाया जाता है — न रैंकिंग में मिलाया जाता है, न पन्ने से हटाया जाता है।',
    liveHead: 'लाइव जोखिम · यह विंडो',
    districtCol: 'ज़िला',
    rankCol: 'क्रम',
    tierCol: 'स्तर',
    waterCol: 'अभी जल',
    tierWatch: 'निगरानी',
    tierElevated: 'बढ़ा हुआ',
    tierLow: 'कम',
    legend: 'ये स्तर हैं, संभावनाएँ नहीं। "निगरानी" का अर्थ है कि स्कोर बैक-टेस्टिंग में मापे गए चेतावनी स्तर से ऊपर गया; "बढ़ा हुआ" का अर्थ है कि ज़िला आज की रैंकिंग में आगे है पर उस स्तर तक नहीं पहुँचा। हर पंक्ति के साथ दी गई संख्या एक रैंकिंग स्कोर है जिसका कोई अंशांकन नहीं है: इससे ज़िलों की आपस में तुलना करें, इसे बाढ़ की संभावना कभी न समझें।',
    thresholdIs: 'चेतावनी स्तर',
    unknownHead: 'इस चक्र में तस्वीर नहीं',
    unknownNote: 'इन ज़िलों के लिए सैटेलाइट से उपयोगी कवरेज नहीं मिली, इसलिए इनका पूर्वानुमान नहीं बनाया जा सका। अज्ञात होना सूखा होना नहीं है।',
    unavailable: 'इस चक्र के लिए पूर्वानुमान उपलब्ध नहीं: इसे बनाने के लिए ज़रूरी सैटेलाइट कवरेज नहीं थी या बहुत पुरानी थी, इसलिए कोई ज़िला रैंकिंग नहीं दिखाई गई। यह सुरक्षा की सूचना नहीं है। तस्वीर का न होना जानकारी का न होना है।',
    inactive: 'पूर्वानुमानक अपने मौसम से बाहर है। यह केवल मुख्य मानसून पर प्रशिक्षित और सत्यापित है, और यह सक्रिय होता है',
    summary: 'हर मौसम का पूर्वानुमान केवल उससे पहले के मौसमों से बनाया जाता है, इसलिए मॉडल कभी अपना भविष्य नहीं देखता। सभी ज़िला-दिनों को मिलाकर इसकी औसत परिशुद्धता 0.249 है, जबकि आधार दर 3.07% है — पर यह सम्मिलित आँकड़ा इसका सामान्य मौसम नहीं है: मौसम-दर-मौसम औसत 0.176 और माध्यिका 0.083 है। प्रदर्शन असमान है। 2025 में यह स्पष्ट रूप से जीतता है, और 2023 में उत्तेजना-विशेषताओं के बिना वही मॉडल इसे 0.243 बनाम 0.145 से हरा देता है। रैंकिंग ही उपयोगी परिणाम है और चेतावनी सीमित है: यह एक चयनात्मक ट्रिगर है, पूर्ण चेतावनी प्रणाली नहीं। यह सब पूर्वव्यापी है और इन्हीं मौसमों को देखकर चुना गया है; असली परीक्षा 2026 का मानसून है। पूरा ऑडिट, उस मुख्य आँकड़े सहित जिसे हमें वापस लेना पड़ा, नीचे है।',
    seeProof: 'देखें 2025 में यह कैसा रहा, और पूरा सत्यापन →',
  },
  pa: {
    no: '01', title: 'ਭਵਿੱਖਬਾਣੀ',
    lead: 'ਪੰਜਾਬ ਦੇ ਹਰ ਜ਼ਿਲ੍ਹੇ ਲਈ ਤਿੰਨ ਦਿਨਾਂ ਦੀ ਹੜ੍ਹ ਭਵਿੱਖਬਾਣੀ।',
    intro: 'ਇੱਕ ਦਹਾਕੇ ਦੇ ਰੋਜ਼ਾਨਾ ਸੈਟੇਲਾਈਟ ਹੜ੍ਹ ਨਿਰੀਖਣਾਂ ਉੱਤੇ ਗ੍ਰੇਡੀਐਂਟ ਬੂਸਟਿੰਗ, ਜਿਸ ਵਿੱਚ ਅਜਿਹੀਆਂ ਵਿਸ਼ੇਸ਼ਤਾਵਾਂ ਹਨ ਜੋ ਹਾਲੀਆ ਹੜ੍ਹ ਨੂੰ ਗੁਆਂਢੀ ਜ਼ਿਲ੍ਹਿਆਂ ਤੱਕ ਲੈ ਜਾਂਦੀਆਂ ਹਨ। ਖੁੱਲ੍ਹਾ, ਮੁੜ-ਪੈਦਾ ਕਰਨਯੋਗ ਅਤੇ ਇਸ ਮਾਨਸੂਨ ਲਾਈਵ — ਉਸ ਸੂਬੇ ਵਿੱਚ ਜਿੱਥੇ ਸਮੀਖਿਆ ਕੀਤੀ CWC ਸੂਚੀ ਵਿੱਚ ਇੱਕ ਵੀ ਹੜ੍ਹ-ਭਵਿੱਖਬਾਣੀ ਸਟੇਸ਼ਨ ਦਰਜ ਨਹੀਂ ਸੀ।',
    explain: 'ਹਰ 6 ਘੰਟੇ ਇਹ ਹਰ ਜ਼ਿਲ੍ਹੇ ਤੋਂ ਇੱਕ ਸਵਾਲ ਪੁੱਛਦਾ ਹੈ: ਕੀ ਅਗਲੇ ਤਿੰਨ ਦਿਨਾਂ ਵਿੱਚ ਸੈਟੇਲਾਈਟ ਇੱਥੇ ਹੜ੍ਹ ਵੇਖੇਗਾ? ਇਹ ਸਿਰਫ਼ ਉਸੇ ਦਿਨ ਤੱਕ ਦੀ ਜਾਣਕਾਰੀ ਵਰਤਦਾ ਹੈ।',
    boardNote: 'ਜਿਹੜੇ ਮੌਸਮ ਇਸ ਨੇ ਕਦੇ ਨਹੀਂ ਵੇਖੇ ਸਨ, ਉਨ੍ਹਾਂ ਉੱਤੇ ਪਰਖ ਕਰਨ ਤੇ, ਅਤੇ ਚੇਤਾਵਨੀ ਦਾ ਪੱਧਰ ਸਿਰਫ਼ ਪਹਿਲੇ ਮੌਸਮਾਂ ਤੋਂ ਤੈਅ ਕਰਨ ਤੇ, ਇਸ ਨੇ ਪ੍ਰਤੀ ਮੌਸਮ ਲਗਭਗ 24 ਚੇਤਾਵਨੀਆਂ ਦਿੱਤੀਆਂ ਅਤੇ ਲਗਭਗ ਤਿੰਨ ਵਿੱਚੋਂ ਇੱਕ ਤੋਂ ਬਾਅਦ ਤਿੰਨ ਦਿਨਾਂ ਦੇ ਅੰਦਰ ਸੱਚਮੁੱਚ ਹੜ੍ਹ ਆਇਆ। ਇਹ ਲਗਭਗ ਚਾਰ ਵਿੱਚੋਂ ਇੱਕ ਹੜ੍ਹ ਦੀ ਸ਼ੁਰੂਆਤ ਫੜਦਾ ਹੈ, ਇਸ ਲਈ ਸ਼ਾਂਤ ਬੋਰਡ ਸੁਰੱਖਿਆ ਦੀ ਗਾਰੰਟੀ ਨਹੀਂ ਹੈ। ਜਿਸ ਜ਼ਿਲ੍ਹੇ ਦੀ ਸੈਟੇਲਾਈਟ ਤਸਵੀਰ ਨਹੀਂ ਮਿਲੀ, ਉਸ ਨੂੰ ਵੱਖਰੇ ਤੌਰ ਤੇ ਅਣਜਾਣ ਵਜੋਂ ਦਿਖਾਇਆ ਜਾਂਦਾ ਹੈ — ਨਾ ਰੈਂਕਿੰਗ ਵਿੱਚ ਰਲਾਇਆ ਜਾਂਦਾ, ਨਾ ਪੰਨੇ ਤੋਂ ਹਟਾਇਆ ਜਾਂਦਾ।',
    liveHead: 'ਲਾਈਵ ਖ਼ਤਰਾ · ਇਹ ਵਿੰਡੋ',
    districtCol: 'ਜ਼ਿਲ੍ਹਾ',
    rankCol: 'ਕ੍ਰਮ',
    tierCol: 'ਪੱਧਰ',
    waterCol: 'ਹੁਣ ਪਾਣੀ',
    tierWatch: 'ਨਿਗਰਾਨੀ',
    tierElevated: 'ਵਧਿਆ ਹੋਇਆ',
    tierLow: 'ਘੱਟ',
    legend: 'ਇਹ ਪੱਧਰ ਹਨ, ਸੰਭਾਵਨਾਵਾਂ ਨਹੀਂ। "ਨਿਗਰਾਨੀ" ਦਾ ਮਤਲਬ ਹੈ ਕਿ ਸਕੋਰ ਬੈਕ-ਟੈਸਟਿੰਗ ਵਿੱਚ ਮਾਪੇ ਗਏ ਚੇਤਾਵਨੀ ਪੱਧਰ ਤੋਂ ਉੱਤੇ ਗਿਆ; "ਵਧਿਆ ਹੋਇਆ" ਦਾ ਮਤਲਬ ਹੈ ਕਿ ਜ਼ਿਲ੍ਹਾ ਅੱਜ ਦੀ ਰੈਂਕਿੰਗ ਵਿੱਚ ਅੱਗੇ ਹੈ ਪਰ ਉਸ ਪੱਧਰ ਤੱਕ ਨਹੀਂ ਪਹੁੰਚਿਆ। ਹਰ ਕਤਾਰ ਨਾਲ ਦਿੱਤਾ ਨੰਬਰ ਇੱਕ ਰੈਂਕਿੰਗ ਸਕੋਰ ਹੈ ਜਿਸ ਦਾ ਕੋਈ ਅੰਸ਼ਾਂਕਣ ਨਹੀਂ: ਇਸ ਨਾਲ ਜ਼ਿਲ੍ਹਿਆਂ ਦੀ ਆਪਸ ਵਿੱਚ ਤੁਲਨਾ ਕਰੋ, ਇਸ ਨੂੰ ਹੜ੍ਹ ਦੀ ਸੰਭਾਵਨਾ ਕਦੇ ਨਾ ਸਮਝੋ।',
    thresholdIs: 'ਚੇਤਾਵਨੀ ਪੱਧਰ',
    unknownHead: 'ਇਸ ਚੱਕਰ ਵਿੱਚ ਤਸਵੀਰ ਨਹੀਂ',
    unknownNote: 'ਇਨ੍ਹਾਂ ਜ਼ਿਲ੍ਹਿਆਂ ਲਈ ਸੈਟੇਲਾਈਟ ਤੋਂ ਵਰਤੋਂਯੋਗ ਕਵਰੇਜ ਨਹੀਂ ਮਿਲੀ, ਇਸ ਲਈ ਇਨ੍ਹਾਂ ਦੀ ਭਵਿੱਖਬਾਣੀ ਨਹੀਂ ਬਣਾਈ ਜਾ ਸਕੀ। ਅਣਜਾਣ ਹੋਣਾ ਸੁੱਕਾ ਹੋਣਾ ਨਹੀਂ ਹੈ।',
    unavailable: 'ਇਸ ਚੱਕਰ ਲਈ ਭਵਿੱਖਬਾਣੀ ਉਪਲਬਧ ਨਹੀਂ: ਇਸ ਨੂੰ ਬਣਾਉਣ ਲਈ ਲੋੜੀਂਦੀ ਸੈਟੇਲਾਈਟ ਕਵਰੇਜ ਨਹੀਂ ਸੀ ਜਾਂ ਬਹੁਤ ਪੁਰਾਣੀ ਸੀ, ਇਸ ਲਈ ਕੋਈ ਜ਼ਿਲ੍ਹਾ ਰੈਂਕਿੰਗ ਨਹੀਂ ਦਿਖਾਈ ਗਈ। ਇਹ ਸੁਰੱਖਿਆ ਦੀ ਸੂਚਨਾ ਨਹੀਂ ਹੈ। ਤਸਵੀਰ ਦਾ ਨਾ ਹੋਣਾ ਜਾਣਕਾਰੀ ਦਾ ਨਾ ਹੋਣਾ ਹੈ।',
    inactive: 'ਭਵਿੱਖਬਾਣੀਕਾਰ ਆਪਣੇ ਮੌਸਮ ਤੋਂ ਬਾਹਰ ਹੈ। ਇਹ ਸਿਰਫ਼ ਮੁੱਖ ਮਾਨਸੂਨ ਉੱਤੇ ਸਿਖਲਾਈ ਅਤੇ ਸਤਿਆਪਿਤ ਹੈ, ਅਤੇ ਇਹ ਸਰਗਰਮ ਹੁੰਦਾ ਹੈ',
    summary: 'ਹਰ ਮੌਸਮ ਦੀ ਭਵਿੱਖਬਾਣੀ ਸਿਰਫ਼ ਉਸ ਤੋਂ ਪਹਿਲੇ ਮੌਸਮਾਂ ਤੋਂ ਬਣਾਈ ਜਾਂਦੀ ਹੈ, ਇਸ ਲਈ ਮਾਡਲ ਕਦੇ ਆਪਣਾ ਭਵਿੱਖ ਨਹੀਂ ਵੇਖਦਾ। ਸਾਰੇ ਜ਼ਿਲ੍ਹਾ-ਦਿਨਾਂ ਨੂੰ ਮਿਲਾ ਕੇ ਇਸ ਦੀ ਔਸਤ ਸ਼ੁੱਧਤਾ 0.249 ਹੈ, ਜਦਕਿ ਆਧਾਰ ਦਰ 3.07% ਹੈ — ਪਰ ਇਹ ਮਿਲਿਆ-ਜੁਲਿਆ ਅੰਕੜਾ ਇਸ ਦਾ ਆਮ ਮੌਸਮ ਨਹੀਂ ਹੈ: ਮੌਸਮ-ਦਰ-ਮੌਸਮ ਔਸਤ 0.176 ਅਤੇ ਮੱਧਕ 0.083 ਹੈ। ਪ੍ਰਦਰਸ਼ਨ ਅਸਮਾਨ ਹੈ। 2025 ਵਿੱਚ ਇਹ ਸਾਫ਼ ਤੌਰ ਤੇ ਜਿੱਤਦਾ ਹੈ, ਅਤੇ 2023 ਵਿੱਚ ਉਤੇਜਨਾ-ਵਿਸ਼ੇਸ਼ਤਾਵਾਂ ਤੋਂ ਬਿਨਾਂ ਉਹੀ ਮਾਡਲ ਇਸ ਨੂੰ 0.243 ਬਨਾਮ 0.145 ਨਾਲ ਹਰਾ ਦਿੰਦਾ ਹੈ। ਰੈਂਕਿੰਗ ਹੀ ਲਾਭਦਾਇਕ ਨਤੀਜਾ ਹੈ ਅਤੇ ਚੇਤਾਵਨੀ ਸੀਮਤ ਹੈ: ਇਹ ਇੱਕ ਚੋਣਵਾਂ ਟ੍ਰਿਗਰ ਹੈ, ਪੂਰੀ ਚੇਤਾਵਨੀ ਪ੍ਰਣਾਲੀ ਨਹੀਂ। ਇਹ ਸਭ ਪਿਛਲਖੁਰੀ ਹੈ ਅਤੇ ਇਨ੍ਹਾਂ ਹੀ ਮੌਸਮਾਂ ਨੂੰ ਵੇਖ ਕੇ ਚੁਣਿਆ ਗਿਆ ਹੈ; ਅਸਲ ਪਰਖ 2026 ਦਾ ਮਾਨਸੂਨ ਹੈ। ਪੂਰਾ ਆਡਿਟ, ਉਸ ਮੁੱਖ ਅੰਕੜੇ ਸਮੇਤ ਜੋ ਸਾਨੂੰ ਵਾਪਸ ਲੈਣਾ ਪਿਆ, ਹੇਠਾਂ ਹੈ।',
    seeProof: 'ਵੇਖੋ 2025 ਵਿੱਚ ਇਹ ਕਿਵੇਂ ਰਿਹਾ, ਅਤੇ ਪੂਰਾ ਸਤਿਆਪਨ →',
  },
};

export default function ForecastSection({lang}) {
  const t = F_T[lang] || F_T.en;
  const [nc, setNc] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let on = true;
    fetch(RAW + 'monitor/nowcast.json')
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((j) => { if (on) { setNc(j); setFailed(false); } })
      // Swallowing this left the section blank, which reads as nothing to
      // report. If we cannot reach the feed we do not know anything, and the
      // page has to say so.
      .catch(() => { if (on) { setNc(null); setFailed(true); } });
    return () => { on = false; };
  }, []);

  const {state, scored, unimaged, threshold: rawThreshold} =
    resolveForecastState(nc, {fetchFailed: failed});
  const rows = scored.slice(0, 8);
  const preCore = state === 'inactive';
  const unavailable = state === 'unavailable';
  const showBoard = state === 'board';
  const threshold = rawThreshold === null ? null : rawThreshold.toFixed(3);

  const tierLabel = {watch: t.tierWatch, elevated: t.tierElevated, low: t.tierLow};

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

          {preCore && (
            <VStack maxWidth={780} gap={2}>
              <StatusDot variant="neutral" label="inactive" />
              <Text type="large">{t.inactive}{nc && nc.activates ? ` ${nc.activates}.` : '.'}</Text>
            </VStack>
          )}

          {unavailable && (
            <VStack maxWidth={780} gap={2}>
              <StatusDot variant="warning" label="unavailable" />
              <Text type="large">{t.unavailable}</Text>
            </VStack>
          )}

          {showBoard && (
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
                      <Text type="supporting" color="secondary">{t.tierCol}</Text>
                      <Text type="supporting" color="secondary">{t.waterCol}</Text>
                    </HStack>
                  </HStack>
                  {rows.map((d) => {
                    // Tier and rank are the operational output. The raw score
                    // sits beside the name as secondary text, because a bare
                    // decimal reads as a percentage to anyone in a hurry.
                    // An unrecognised tier is shown as unknown rather than
                    // quietly downgraded: defaulting a broken field to "low"
                    // would let the primary output manufacture reassurance.
                    // Guaranteed valid: an invalid tier anywhere suppresses the
                    // whole board rather than being rendered as unknown here.
                    const tier = d.tier;
                    // `+x || 0` printed a confident 0.0 km² for a malformed
                    // value, which reads as "imaged, and dry".
                    const km2 = d.covered === false ? null : num(d.observed_km2);
                    const water = km2 === null ? '—' : km2.toFixed(1) + ' km²';
                    return (
                      <React.Fragment key={d.district}>
                        <Divider />
                        <HStack justify="between" vAlign="center" paddingBlock={2} gap={3}>
                          <HStack gap={2} vAlign="baseline" wrap="wrap">
                            <Text color="secondary" hasTabularNumbers type="supporting">{d.rank}</Text>
                            <Text>{d.district}</Text>
                            <Text type="supporting" color="secondary" hasTabularNumbers>{num(d.p_event).toFixed(3)}</Text>
                          </HStack>
                          <HStack gap={5} vAlign="center">
                            {tier === 'watch'
                              ? <Badge variant="error" label={tierLabel.watch} />
                              : tier === 'elevated'
                                ? <Badge variant="orange" label={tierLabel.elevated} />
                                : <Text type="supporting" color="secondary">{tierLabel.low}</Text>}
                            <Text color="secondary" hasTabularNumbers>{water}</Text>
                          </HStack>
                        </HStack>
                      </React.Fragment>
                    );
                  })}
                  <Divider />
                </VStack>
                <VStack gap={1}>
                  <Text type="supporting" color="secondary">{t.legend}</Text>
                  {threshold && (
                    <Text type="supporting" color="secondary" hasTabularNumbers>{t.thresholdIs}: {threshold}</Text>
                  )}
                </VStack>
              </VStack>
              <VStack maxWidth={440} justify="center">
                <Text type="large" color="secondary">{t.summary}</Text>
              </VStack>
            </Grid>
          )}

          {unimaged.length > 0 && (
            <VStack maxWidth={780} gap={2}>
              <HStack gap={2} vAlign="center" wrap="wrap">
                <StatusDot variant="warning" label="unknown" />
                <Text type="label" color="secondary">{t.unknownHead}</Text>
              </HStack>
              <Text color="secondary">{t.unknownNote}</Text>
              <Text>{unimaged.map((d) => d.district).join(' · ')}</Text>
            </VStack>
          )}

          <Link href="#proof" isStandalone>{t.seeProof}</Link>
        </VStack>
      </HStack>
    </Section>
  );
}
