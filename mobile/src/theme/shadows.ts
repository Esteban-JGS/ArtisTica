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
// una larga y suave que lo despega del tablero. Con boxShadow, porque la
// elevation de Android da una sombra gris pareja que se ve plastica.
// Dibuja el contorno de la caja que la lleva: esa caja tiene que medir
// lo mismo que el papel, o la sombra delata el espacio de mas.
export const NOTE_SHADOW = {
  boxShadow: '0px 1px 2px rgba(48,28,12,0.40), 0px 8px 16px rgba(48,28,12,0.28)',
};
