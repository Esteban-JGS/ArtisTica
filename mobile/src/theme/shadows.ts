import { colors } from './colors';

// Shared elevation presets for anything that floats above the page —
// header cards, tab pills, the navbar. All three share the same warm
// shadow tint (colors.ink[700]) so they read as one consistent "lift",
// just at different intensities.
export const FLOAT_SHADOW = {
  shadowColor: colors.ink[700],
  shadowOpacity: 0.12,
  shadowRadius: 10,
  shadowOffset: { width: 0, height: 4 },
  elevation: 5,
};

export const PILL_SHADOW = {
  shadowColor: colors.ink[700],
  shadowOpacity: 0.16,
  shadowRadius: 10,
  shadowOffset: { width: 0, height: 4 },
  elevation: 6,
};

export const NOTE_SHADOW = {
  shadowColor: colors.ink[700],
  shadowOpacity: 0.2,
  shadowRadius: 10,
  shadowOffset: { width: 0, height: 6 },
  elevation: 6,
};
