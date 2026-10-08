import { create } from 'zustand';

// Las mismas provincias que acepta el backend (src/domain/perfiles.py)
export const PROVINCES = ['San José', 'Alajuela', 'Cartago', 'Heredia', 'Guanacaste', 'Puntarenas', 'Limón'];

// El mismo rechazo que hace el backend: el contacto va por la plataforma
const PHONE_PATTERN = /(?<!\d)(?:\+?506[\s.-]?)?[245678]\d{3}[\s.-]?\d{4}(?!\d)/;
const WHATSAPP_PATTERN = /whatsapp|wa\.me/i;

export function hasForbiddenContact(text: string) {
  return PHONE_PATTERN.test(text) || WHATSAPP_PATTERN.test(text);
}

export type OwnProfile = {
  handle: string;
  role: string;
  bio: string;
  about: string;
  place: string;
  commissionsOpen: boolean;
  priceLow: number;
  priceHigh: number;
  openUntil: string;
};

type ProfileState = {
  profile: OwnProfile;
  updateProfile: (changes: Partial<OwnProfile>) => void;
};

// Mock de sesion como posts-store: se resetea al recargar la app. Cuando
// exista la sesion real, esto sale de GET /perfiles/yo y se guarda con
// PATCH /perfiles/yo.
export const useProfileStore = create<ProfileState>((set) => ({
  profile: {
    handle: 'lunaatelier',
    role: 'Ilustradora digital',
    bio: 'Creo mundos suaves para quienes todavía creen en la magia cotidiana.',
    about:
      'Ilustradora digital especializada en escenas íntimas y paletas suaves. Trabajo por comisión desde 2019: retratos, portadas editoriales y personajes.',
    place: 'San José',
    commissionsOpen: true,
    priceLow: 40,
    priceHigh: 120,
    openUntil: 'noviembre',
  },
  updateProfile: (changes) => set((state) => ({ profile: { ...state.profile, ...changes } })),
}));
