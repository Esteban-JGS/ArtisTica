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

// Papel sobre corcho: una sombra corta y firme que marca el borde, mas
// una suave que lo despega del tablero. Con boxShadow, porque la
// elevation de Android da una sombra gris pareja que se ve plastica. La
// segunda se mantiene corta: con mas desplazamiento, Android la dibuja
// casi sin difuminar y parece un canto del papel.
export const NOTE_SHADOW = {
  boxShadow: '0px 1px 2px rgba(48,28,12,0.32), 0px 3px 10px rgba(48,28,12,0.20)',
};
