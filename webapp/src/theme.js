import {defineTheme} from '@astryxdesign/core/theme';
import {gothicTheme} from '@astryxdesign/theme-gothic';

// Astryx's premade "Gothic" dark palette (deep blue-gray surfaces) kept as-is,
// with just a serif heading so it reads editorial rather than stock.
export const sailaabTheme = defineTheme({
  name: 'sailaab',
  extends: gothicTheme,
  typography: {
    scale: {base: 16, ratio: 1.25},
    heading: {
      family: 'Iowan Old Style',
      fallbacks: 'Palatino, "Palatino Linotype", Georgia, "Times New Roman", serif',
    },
    body: {
      family: 'system-ui',
      fallbacks: '-apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    },
  },
  radius: {base: 2, multiplier: 1},
});
