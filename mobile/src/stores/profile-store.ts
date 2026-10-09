import { create } from 'zustand';

import type { roleColors } from '@/theme';

// Las mismas provincias que acepta el backend (src/domain/perfiles.py)
export const PROVINCES = ['San José', 'Alajuela', 'Cartago', 'Heredia', 'Guanacaste', 'Puntarenas', 'Limón'];

// El mismo rechazo que hace el backend: el contacto va por la plataforma
const PHONE_PATTERN = /(?<!\d)(?:\+?506[\s.-]?)?[245678]\d{3}[\s.-]?\d{4}(?!\d)/;
const WHATSAPP_PATTERN = /whatsapp|wa\.me/i;
const SINPE_PATTERN = /sinpe/i;

export function hasForbiddenContact(text: string) {
  return PHONE_PATTERN.test(text) || WHATSAPP_PATTERN.test(text);
}

// En el chat no se bloquea: solo se avisa (Documento Maestro 2.6)
export function mentionsOffPlatformPayment(text: string) {
  return hasForbiddenContact(text) || SINPE_PATTERN.test(text);
}

// Mismas reglas que normalizar_handle en el backend
const HANDLE_PATTERN = /^[a-z0-9_]{3,30}$/;
const RESERVED_HANDLES = ['yo', 'admin', 'artistica', 'soporte', 'api'];

export function handleError(handle: string) {
  if (!HANDLE_PATTERN.test(handle)) return 'Entre 3 y 30 letras minúsculas, números o guion bajo.';
  if (RESERVED_HANDLES.includes(handle)) return 'Ese nombre de usuario está reservado.';
  return null;
}

export type OwnProfile = {
  name: string;
  handle: string;
  initial: string;
  color: keyof typeof roleColors;
  isArtist: boolean;
  verified: boolean;
  photo: string | null;
  role: string;
  bio: string;
  about: string;
  place: string;
  commissionsOpen: boolean;
  priceLow: number;
  priceHigh: number;
  openUntil: string;
  // Nulo en una cuenta recien creada: todavia no hay historial que mostrar
  stats: { responseDays: number; delivered: number; followers: string } | null;
};

// La cuenta de la demo, con historial (ver posts-store)
export const DEMO_ACCOUNT = { email: 'luna@artistica.cr', password: 'artistica2026' };

const DEMO_PROFILE: OwnProfile = {
  name: 'Luna Atelier',
  handle: 'lunaatelier',
  initial: 'L',
  color: 'terracota',
  isArtist: true,
  verified: true,
  photo: 'https://picsum.photos/seed/luna-atelier-avatar/300/300',
  role: 'Ilustradora digital',
  bio: 'Creo mundos suaves para quienes todavía creen en la magia cotidiana.',
  about:
    'Ilustradora digital especializada en escenas íntimas y paletas suaves. Trabajo por comisión desde 2019: retratos, portadas editoriales y personajes.',
  place: 'San José',
  commissionsOpen: true,
  priceLow: 40,
  priceHigh: 120,
  openUntil: 'noviembre',
  stats: { responseDays: 1, delivered: 156, followers: '12.4k' },
};

type ProfileState = {
  profile: OwnProfile;
  signIn: () => void;
  register: (data: { name: string; handle: string; isArtist: boolean }) => void;
  becomeArtist: () => void;
  updateProfile: (changes: Partial<OwnProfile>) => void;
};

// Mock de sesion como posts-store: se resetea al recargar la app. Cuando
// exista la sesion real, el perfil sale de GET /perfiles/yo, el registro
// es POST /perfiles y los cambios van por PATCH /perfiles/yo.
export const useProfileStore = create<ProfileState>((set) => ({
  profile: DEMO_PROFILE,
  signIn: () => set({ profile: DEMO_PROFILE }),
  register: ({ name, handle, isArtist }) =>
    set({
      profile: {
        name,
        handle,
        initial: name.charAt(0).toUpperCase(),
        color: 'verde',
        isArtist,
        verified: false,
        photo: null,
        role: '',
        bio: '',
        about: '',
        place: 'San José',
        commissionsOpen: false,
        priceLow: 20,
        priceHigh: 60,
        openUntil: '',
        stats: null,
      },
    }),
  becomeArtist: () => set((state) => ({ profile: { ...state.profile, isArtist: true } })),
  updateProfile: (changes) => set((state) => ({ profile: { ...state.profile, ...changes } })),
}));
