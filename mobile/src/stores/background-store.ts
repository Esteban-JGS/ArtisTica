import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

export const BACKGROUND_OPTIONS = [
  {
    id: 'madera-clara',
    label: 'Madera clara',
    uri: 'https://images.unsplash.com/photo-1585773818428-b50bebdc2344',
  },
  {
    id: 'madera-oscura',
    label: 'Madera oscura',
    uri: 'https://images.unsplash.com/photo-1543751416-705d3e34d02a',
  },
  {
    id: 'concreto',
    label: 'Concreto',
    uri: 'https://images.unsplash.com/photo-1708894462826-ba3fa93b41b7',
  },
] as const;

export type BackgroundId = (typeof BACKGROUND_OPTIONS)[number]['id'];

export function backgroundImageUri(id: BackgroundId, width: number) {
  const option = BACKGROUND_OPTIONS.find((item) => item.id === id) ?? BACKGROUND_OPTIONS[1];
  return `${option.uri}?auto=format&fit=crop&w=${width}&q=60`;
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
