# Artística — Mobile (React Native + Expo)

Frontend mobile-first de Artística. Territorio de Brian; el backend (`/backend`) no toca esta carpeta.

## Stack

- Expo (SDK 57) + Expo Router (file-based routing en `src/app`)
- TypeScript
- NativeWind (Tailwind para RN)
- Zustand (estado de sesión/auth)
- TanStack Query (cache/sync de llamadas a FastAPI)
- Supabase JS Client (auth + signed upload URLs)
- React Hook Form + Zod (validación de formularios)
- FlashList (feed con scroll performante)
- Expo Notifications

## Estructura

```
mobile/
├── src/
│   ├── app/          # rutas (Expo Router)
│   ├── components/
│   ├── constants/
│   └── hooks/
├── assets/
└── docs/             # propuesta técnica y prototipos de diseño
```

Tabs previstos: Inicio / Explorar / Crear / Mensajes / Perfil.

## Desarrollo

```bash
npm install
npm run start
```
