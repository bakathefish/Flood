import {defineTheme} from '@astryxdesign/core/theme';

/* Sailaab — a gazette, not a dashboard.
 *
 * The page is a light warm-paper document: an official record you could
 * print and hand to a district officer. The one dark moment is the live
 * radar monitor, mounted like a plate in a report, which is where the
 * instrument shows through. That contrast is the whole idea, and it is
 * built with the design system's own MediaTheme rather than against it.
 *
 * Type is three roles across three scripts (see public/fonts/faces.css):
 * a serif for headings, because a flood record should read like a record;
 * IBM Plex Sans for running text, which is the institutional-technical
 * register this subject actually occupies; and IBM Plex Mono for every
 * figure, timestamp and source line, so the numbers are visibly machine
 * output rather than prose.
 */

// One accent, and it is the colour of water. Links, section numerals and
// the flood ramp all resolve to it, so nothing on the page is coloured
// decoratively. Alert red and elevated ochre stay reserved for severity.
const WATER = '#0B5563';
const WATER_ON_DARK = '#5FC2D2';

export const sailaabTheme = defineTheme({
  name: 'sailaab',
  typography: {
    scale: {base: 16, ratio: 1.25},
    // Each stack runs roman → Devanagari → Gurmukhi, so a Hindi or Punjabi
    // heading picks up the matching Noto Serif instead of dropping to a
    // system face halfway through the type system.
    heading: {
      family: 'Sailaab Serif',
      fallbacks: '"Sailaab Serif Deva", "Sailaab Serif Guru", Georgia, "Times New Roman", serif',
      weights: {1: 'semibold', 2: 'semibold', 3: 'semibold'},
    },
    body: {
      family: 'Sailaab Sans',
      fallbacks: '"Sailaab Sans Deva", "Sailaab Sans Guru", -apple-system, "Segoe UI", Roboto, sans-serif',
    },
    // Plex Mono carries no Devanagari or Gurmukhi, and there is no Indic
    // monospace in this set, so the kickers and column heads in the Hindi
    // and Punjabi editions fall through to the matching Noto Sans rather
    // than to whatever the operating system happens to have.
    code: {
      family: 'Sailaab Mono',
      fallbacks: '"Sailaab Sans Deva", "Sailaab Sans Guru", ui-monospace, Menlo, Consolas, monospace',
    },
  },
  // Near-square. A flood record does not have rounded corners; the only
  // curvature on the page is the 2px softening on plates and chips.
  radius: {base: 2, multiplier: 1},
  tokens: {
    // ---- ground: warm newsprint, with plates sitting brighter on it ----
    '--color-background-body': ['#F4F1EA', '#12140F'],
    '--color-background-surface': ['#FBF9F4', '#1A1D17'],
    '--color-background-card': ['#FFFFFF', '#21241D'],
    '--color-background-popover': ['#FFFFFF', '#282C24'],
    '--color-background-muted': ['#1A18120A', '#FFFFFF0A'],
    '--color-background-inverted': ['#16150F', '#FBF9F4'],

    // ---- ink: warm near-black, never pure #000 on paper ----
    '--color-text-primary': ['#16150F', '#E9E7DE'],
    '--color-text-secondary': ['#57534A', '#A9A69B'],
    '--color-text-disabled': ['#8E897D', '#6C695F'],
    '--color-text-accent': [WATER, WATER_ON_DARK],
    '--color-icon-primary': ['#16150F', '#E9E7DE'],
    '--color-icon-secondary': ['#57534A', '#A9A69B'],
    '--color-icon-accent': [WATER, WATER_ON_DARK],

    // ---- hairlines: the page is ruled, so the rules must be quiet ----
    '--color-border': ['#16150F1F', '#E9E7DE1F'],
    '--color-border-emphasized': ['#16150F42', '#E9E7DE38'],
    '--color-track': ['#DAD5C9', '#3A3E34'],
    '--color-skeleton': ['#E4E0D5', '#33372C'],

    '--color-accent': [WATER, WATER_ON_DARK],
    '--color-accent-muted': ['#0B556322', '#5FC2D226'],
    '--color-on-accent': ['#FFFFFF', '#12140F'],
    '--color-overlay-hover': ['#16150F0A', '#FFFFFF0D'],
    '--color-overlay-pressed': ['#16150F16', '#FFFFFF1A'],
    '--color-shadow': ['#16150F14', '#00000059'],

    // ---- severity: reserved, and only ever used for severity ----
    '--color-error': ['#A32B1D', '#FF8168'],
    '--color-error-muted': ['#A32B1D26', '#FF816830'],
    '--color-icon-red': ['#A32B1D', '#FF8168'],
    '--color-border-red': ['#A32B1D', '#FF8168'],
    '--color-text-red': ['#6E1A10', '#FFC2B4'],
    '--color-background-red': ['#A32B1D1F', '#FF816822'],

    '--color-warning': ['#8A5A0E', '#E2AC45'],
    '--color-warning-muted': ['#8A5A0E26', '#E2AC4530'],
    '--color-on-warning': ['#FFFFFF', '#12140F'],
    '--color-icon-orange': ['#8A5A0E', '#E2AC45'],
    '--color-border-orange': ['#8A5A0E', '#E2AC45'],
    '--color-text-orange': ['#5A3A06', '#F4D9A6'],
    '--color-background-orange': ['#8A5A0E1F', '#E2AC4522'],

    '--color-success': ['#2E6B39', '#79BE86'],
    '--color-success-muted': ['#2E6B3926', '#79BE8630'],

    // The "AI" tag and other enumerated chips borrow the water hue rather
    // than the stock blue, so the page never carries two unrelated blues.
    '--color-icon-blue': [WATER, WATER_ON_DARK],
    '--color-border-blue': [WATER, WATER_ON_DARK],
    '--color-text-blue': ['#083E4A', '#B7E6EE'],
    '--color-background-blue': ['#0B55631A', '#5FC2D21F'],
  },

  // On the dark radar plate the accent has to lift off a near-black
  // ground; the default on-dark tokens keep the paper hues and go muddy.
  onDark: {
    tokens: {
      '--color-accent': WATER_ON_DARK,
      '--color-text-accent': WATER_ON_DARK,
      '--color-icon-accent': WATER_ON_DARK,
      '--color-text-primary': '#EDEBE2',
      '--color-text-secondary': '#A9A69B',
      '--color-border': '#EDEBE224',
      '--color-border-emphasized': '#EDEBE23D',
    },
  },

  components: {
    // Kickers and column heads: small, spaced, uppercase, in the data face.
    // This is the page's connective tissue, and it is what makes a section
    // head read as a label on a record rather than a heading on a deck.
    text: {
      'type:label': {
        fontFamily: 'var(--font-family-code)',
        fontSize: 'var(--font-size-sm)',
        fontWeight: 'var(--font-weight-medium)',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        // Devanagari and Gurmukhi are not letterspaced: tracking pulls
        // conjuncts and matras away from the consonants they belong to, and
        // neither script has a case to transform. The roman kicker keeps its
        // tracking; the Hindi and Punjabi editions get the face without it.
        ':lang(hi)': {letterSpacing: 'normal', textTransform: 'none'},
        ':lang(pa)': {letterSpacing: 'normal', textTransform: 'none'},
      },
      'type:supporting': {
        letterSpacing: '0.005em',
        lineHeight: '1.6',
      },
      // Astryx sets `large` semibold, which is right for a UI emphasis token
      // and wrong for a lede: a whole paragraph of semibold reads as shouting
      // and flattens the contrast with the headings above it.
      'type:large': {
        fontWeight: 'var(--font-weight-normal)',
        lineHeight: '1.55',
      },
      // 17px/1.62. Measured against the two public monitoring sites this page
      // is trying to sit beside: NASA Earth Observatory runs 17.6px on a 29px
      // line over a ~708px measure, and USGS Water Data uses the same near
      // black on white. 16px was a screen-UI default, not a reading size.
      'type:body': {
        fontSize: '1.0625rem',
        lineHeight: '1.62',
      },
      // Figures, ratios and km² readings. Tabular by default so a column
      // of numbers lines up without every call site asking for it.
      'type:code': {
        fontFeatureSettings: '"tnum" 1, "zero" 1',
        letterSpacing: '-0.005em',
      },
      // A custom type for the headline read-offs: the four proof figures,
      // the selected district's value, the live monitor's three numbers.
      // It exists because the `size` prop loses to a themed `type` on this
      // build, so `type="code" size="3xl"` silently rendered at 16px; a type
      // that carries its own size cannot be undone that way.
      'type:figure': {
        fontFamily: 'var(--font-family-code)',
        fontSize: 'clamp(1.75rem, 1.15rem + 1.9vw, 2.4375rem)',
        fontWeight: 'var(--font-weight-medium)',
        lineHeight: '1.1',
        letterSpacing: '-0.02em',
        fontFeatureSettings: '"tnum" 1, "zero" 1',
      },
    },
    heading: {
      base: {
        letterSpacing: '-0.012em',
        textWrap: 'balance',
      },
      // The display sizes are re-stated here because the generated
      // display-* rules lose to the level-* rules on this build, so a
      // `type="display-1"` hero was silently rendering at heading-1 size.
      // Stating them also lets the hero scale with the viewport, which a
      // fixed token step cannot do: 38px on a phone, 61px on a desktop.
      'type:display-1': {
        fontSize: 'clamp(2.375rem, 1.15rem + 4.6vw, 3.8125rem)',
        lineHeight: '1.08',
        letterSpacing: '-0.022em',
        fontWeight: 'var(--font-weight-semibold)',
      },
      'type:display-2': {
        fontSize: 'clamp(1.9375rem, 1.2rem + 2.9vw, 3.0625rem)',
        lineHeight: '1.12',
        letterSpacing: '-0.018em',
        fontWeight: 'var(--font-weight-semibold)',
      },
      'type:display-3': {
        fontSize: 'clamp(1.5625rem, 1.1rem + 1.9vw, 2.4375rem)',
        lineHeight: '1.18',
        letterSpacing: '-0.015em',
        fontWeight: 'var(--font-weight-normal)',
      },
    },
    // Plates, not cards: a hairline and a flat ground, no lift.
    card: {
      base: {
        borderRadius: '2px',
        borderWidth: '1px',
        borderStyle: 'solid',
        borderColor: 'var(--color-border-emphasized)',
        boxShadow: 'none',
      },
    },
    // The language switch and the map layer switch are the only chrome on
    // the page; they read as instrument controls in the data face.
    'segmented-control-item': {
      base: {
        fontFamily: 'var(--font-family-code)',
        fontSize: 'var(--font-size-sm)',
        letterSpacing: '0.04em',
      },
    },
    badge: {
      base: {
        fontFamily: 'var(--font-family-code)',
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        borderRadius: '2px',
      },
    },
    button: {
      base: {borderRadius: '2px'},
    },
    banner: {
      base: {borderRadius: '2px'},
    },
  },
});

/* Chart and map colour, kept beside the theme so the data hues and the
 * interface hues cannot drift apart. Sequential ramps are one hue running
 * light to dark, which is the only honest encoding for a magnitude; the
 * no-data grey is deliberately outside every ramp so "we did not look"
 * can never be mistaken for "we looked and found little". */
/* Every value below was checked with the dataviz validator against the paper
 * surface (#FBF9F4), not eyeballed. The three ramps pass monotone lightness,
 * a >=0.06 lightness gap between steps, a light end that still clears the
 * page at >=2:1, and a hue spread under 6 degrees. The pale ends of the old
 * dark-mode ramps sat at 1.12:1 here, which would have made the calmest
 * districts disappear into the paper.
 *
 * No-data is the one case colour cannot carry. A neutral grey against the
 * ochre ramp separates by only dE 7.4, well under the 15 floor, so an
 * unobserved district is drawn with a hatch and a dashed outline instead —
 * texture, not tint. That is deliberate: "we did not look here" has to be
 * unmistakable, and it is the claim the whole page rests on. */
export const dataColors = {
  // standing water / flood extent — the accent hue, run out as a ramp
  water: ['#7FB0BC', '#5D99A8', '#3F7F8F', '#255F70', '#0B4351'],
  // how many seasons a district flooded — ochre, distinct from water
  recurrence: ['#C4A96E', '#AC9053', '#93773B', '#795F27', '#5C4715'],
  // rupee damage — rust, warmer again, and never mistaken for severity red
  impact: ['#CE9A80', '#B67B61', '#9C5F45', '#81462E', '#63311B'],
  // the hatch that means "not imaged": lines on bare paper, no fill tint
  noDataHatch: '#8C8477',
  // the proof chart's two outcomes: dE 19.2 normal, 14.8 protan, both >=3:1
  floodedBar: '#0D5F6F',
  dryBar: '#8C8477',
  // chart furniture on paper
  axis: '#57534A',
  grid: '#16150F1A',
  tipBg: '#FFFFFF',
  tipBorder: '#16150F42',
  tipFg: '#16150F',
  mapOutline: '#16150F4D',
  mapHover: '#A32B1D',
};
