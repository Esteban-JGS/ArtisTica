import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

// "Corcho" usa una textura local en vez de una foto de Unsplash porque
// tiene que repetirse sin costura (ver app-background.tsx): parte de una
// textura CC0 de ambientCG (ambientcg.com/a/Cork001), tenida hacia el
// color de marca (colors.accent) a partir de su luminancia original,
// a diferencia de las fotos sueltas de las otras opciones.
const CORK_TEXTURE = require('@/assets/images/texture-cork.avif');

export const BACKGROUND_OPTIONS = [
  {
    id: 'madera-clara',
    label: 'Madera clara',
    kind: 'remote',
    uri: 'https://images.unsplash.com/photo-1585773818428-b50bebdc2344',
  },
  {
    id: 'madera-oscura',
    label: 'Madera oscura',
    kind: 'remote',
    uri: 'https://images.unsplash.com/photo-1543751416-705d3e34d02a',
  },
  {
    id: 'concreto',
    label: 'Concreto',
    kind: 'remote',
    uri: 'https://images.unsplash.com/photo-1708894462826-ba3fa93b41b7',
  },
  {
    id: 'corcho',
    label: 'Corcho',
    kind: 'local',
    source: CORK_TEXTURE,
  },
] as const;

export type BackgroundId = (typeof BACKGROUND_OPTIONS)[number]['id'];

// Para opciones remotas arma la URL recortada al ancho pedido; para la
// local devuelve el modulo del asset tal cual, ya que require() no
// admite armar la ruta en tiempo de ejecucion.
export function backgroundSource(id: BackgroundId, width: number) {
  const option = BACKGROUND_OPTIONS.find((item) => item.id === id) ?? BACKGROUND_OPTIONS[1];
  if (option.kind === 'local') {
    return option.source;
  }
  return { uri: `${option.uri}?auto=format&fit=crop&w=${width}&q=60` };
}

type BackgroundState = {
  backgroundId: BackgroundId;
  setBackgroundId: (id: BackgroundId) => void;
};

export const useBackgroundStore = create<BackgroundState>()(
  persist(
    (set) => ({
      backgroundId: 'madera-oscura',
      setBackgroundId: (backgroundId) => set({ backgroundId }),
    }),
    {
      name: 'background-preference',
      storage: createJSONStorage(() => AsyncStorage),
    },
  ),
);
