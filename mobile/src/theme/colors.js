// Single source of truth for the app's color palette.
//
// Plain CommonJS (not TypeScript) on purpose: tailwind.config.js requires
// this file directly at build time, and Node can't load .ts files without
// extra tooling. Every className token (`bg-accent`, `text-sand-100`, ...)
// comes from `colors` here, and any file that needs a raw color value in
// JS — an Ionicons `color` prop, a `shadowColor`, a LiquidGlassView tint —
// should import it from here instead of retyping a hex string by hand.
const colors = {
  ink: {
    DEFAULT: '#201d1a',
    700: '#3d362f',
    600: '#4a423a',
  },
  accent: {
    DEFAULT: '#c2653b',
    dark: '#a1512d',
    darker: '#ae5731',
  },
  sand: {
    50: '#fdf8f3',
    100: '#f7f5f1',
    200: '#efece7',
    300: '#e2ddd5',
  },
  stone: {
    400: '#a49a90',
    500: '#9b9187',
    600: '#948b82',
    700: '#8b8279',
    800: '#7f766d',
    900: '#5c534b',
  },
  gold: '#d99a3f',
  sage: '#3f6b63',
};

// The four "artist role" colors — used for avatars, role badges, washi
// tape, comment avatars, etc. `base` is the solid color (avatars, tape),
// `bg`/`fg` are the tinted pill a role badge uses. Previously these were
// hand-derived twice (once in avatar.tsx, once in home.tsx) and could
// drift out of sync; now there's one definition.
const roleColors = {
  terracota: { base: colors.accent.DEFAULT, bg: 'rgba(194,101,59,0.14)', fg: colors.accent.dark },
  verde: { base: colors.sage, bg: 'rgba(63,107,99,0.16)', fg: colors.sage },
  mostaza: { base: colors.gold, bg: 'rgba(217,154,63,0.2)', fg: '#93641f' },
  taupe: { base: colors.stone[700], bg: 'rgba(139,130,121,0.16)', fg: colors.stone[900] },
};

module.exports = { colors, roleColors };
