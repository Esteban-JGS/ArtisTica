# Stack tecnológico

## Backend / API

**Python 3.12** \- Lenguaje. El componente de IA de la rúbrica vive en Python; otro lenguaje obliga a un segundo servicio.

**FastAPI** \- Framework web. Genera /docs navegable solo: esa es tu demo de API en defensa.

**Uvicorn** \- Servidor que ejecuta FastAPI. Es cómo se corre.

**Pydantic v2 (+ pydantic-settings)** \- Valida datos de entrada y carga variables de entorno tipadas. Ya viene con FastAPI; rechaza lo inválido antes de tu lógica.

**SQLAlchemy 2.0** \- ORM. El escrow necesita transacciones explícitas: marcar entregado y liberar pago pasan juntos o no pasan.

**psycopg3** \- Driver de PostgreSQL. SQLAlchemy traduce a SQL, psycopg lo transmite.

**Alembic** \- Migraciones versionadas. Sin esto sincronizás esquema con Brian a mano.

**PyJWT** \- Verifica la firma del token de Supabase. Sin ese paso, cualquiera fabrica un token y se hace pasar por otro artista.

**httpx** \- Cliente HTTP. Llama la API de ONVO y es el cliente de pruebas de FastAPI en pytest.

**Cola de trabajos en Postgres** \- Tabla jobs con SKIP LOCKED \+ worker. Clasificar con IA tarda segundos y no puede bloquear el request; usa la base que ya tenés en vez de Redis.

**ONVO Pay (sandbox) o TiloPay** \- Pasarela. Costarricense, entorno real, sin depender de una entidad en Estados Unidos.

## Base de datos

**Supabase (PostgreSQL 15\)** \- El escrow necesita ACID: el dinero no puede quedar en estado intermedio. Supabase suma auth y storage sin dejar de ser Postgres estándar.

**pgvector** \- Similitud de contenido. Es la recomendación por estilo que promete tu documento, sin base vectorial aparte.

tsvector \- Búsqueda de texto. Cubre descubrimiento por categoría sin Elasticsearch.

**Supavisor (6543 API / 5432 migraciones)** \- Pool de conexiones. Postgres tiene límite de conexiones; las migraciones necesitan la directa.

**Proyecto dev y proyecto prod** \- Una migración a medias en la base de la demo no tiene vuelta atrás.

## Autenticación

**Supabase Auth: Google, Apple, correo/contraseña** \- Tres proveedores sin construir ninguno. Apple es obligatorio en iOS si ofrecés Google.

**Autorización en FastAPI, sin RLS** \- Supabase dice quién es; tu API decide qué puede hacer. Repartir permisos entre RLS y código es cómo se contradicen, y acá se mueve dinero.

## Storage

**Supabase Storage** \- Mismo proveedor, mismo auth, una sola factura.

**Signed upload URLs** \- El archivo va del teléfono a Storage directo. Si pasa por tu API, bloqueás un worker por subida y pagás el ancho de banda dos veces.

## DevOps

**Docker** \- Un Dockerfile, dos comandos: API y worker. Brian levanta el backend sin instalar Python.

**Railway \-** Hosting. Se despliega con git push en vez de administrar una VM.

**GitHub Actions** \- CI/CD: tests → build → alembic upgrade head → deploy.

**Ruff** \- Formato y linting de Python. Reemplaza Black, isort y Flake8 en una herramienta.

**pytest** \- Tests. El escrow y la verificación del JWT son lo que si falla, falla caro.

**pre-commit** \- Corre Ruff antes de cada commit. Evita que los diffs sean ruido de formato.

**Sentry** \- Errores en producción con stack trace. Si no, te enterás porque alguien te avisa.

### Frontend / Mobile propuesto

**React Native (Expo)** — ya definido como mobile-first; Expo evita pelear con Xcode/Android Studio para correr la demo

**Expo Router** — navegación por archivos, encaja con la estructura de tabs que ya definieron (Inicio/Explorar/Crear/Mensajes/Perfil)

**TypeScript** — mismo nivel de tipado que Pydantic del lado backend, atrapa errores antes de correr

**Supabase JS Client** — mismo proveedor que auth/storage del backend, un solo SDK para login y subida directa por signed URL

**TanStack Query** — cachea y sincroniza las llamadas a FastAPI sin reinventar loading/error states a mano

**NativeWind** — Tailwind para RN, estilos rápidos y consistentes sin hojas de estilo sueltas

**Zustand** — estado de sesión/auth global, más liviano que Redux para lo que necesitan

**React Hook Form \+ Zod** — validación de formularios (solicitud de comisión, registro) espejando las validaciones de Pydantic del backend

**FlashList** — lista del feed con scroll performante, crítico si van a mostrar imagen/audio/video en cascada

**Expo Notifications** — ya lo tenían contemplado, entra directo acá

Arquitectura: monorepo modular

Un repo, dos módulos: /app (React Native \+ Expo, Brian) y /backend (FastAPI, Esteban)

Backend separado en dos servicios: API y worker, para que la IA y el escrow no bloqueen la app

Infraestructura

Supabase: PostgreSQL \+ Auth (Google, Apple, correo) \+ Storage, un solo proveedor

Pagos: ONVO Pay o Tilopay (en evaluación, sandbox), pasarela costarricense sin depender de Stripe

Despliegue: Docker \+ Railway \+ GitHub Actions, cada módulo en su contenedor con deploy automático al hacer push