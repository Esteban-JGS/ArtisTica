import type { Ionicons } from '@expo/vector-icons';
import { create } from 'zustand';

import type { roleColors } from '@/theme';

export type Party = { name: string; initial: string; color: keyof typeof roleColors };

// Los hitos del encargo del Documento Maestro (2.3). El backend separa
// anticipo_pagado de en_proceso y vista previa de saldo_pagado; aca se
// juntan porque la persona los vive como un solo paso.
export type CommissionStatus = 'consulta' | 'cotizado' | 'en_proceso' | 'vista_previa' | 'completado' | 'rechazado';

export type Quote = {
  description: string;
  price: number;
  revisions: number;
  deliveryDate: string;
  depositPercent: number;
};

export type Commission = {
  id: string;
  myRole: 'cliente' | 'artista';
  counterpart: Party;
  title: string;
  idea: string;
  referenceImage?: string;
  status: CommissionStatus;
  quote?: Quote;
  previewImage?: string;
  rating?: number;
  history: { status: CommissionStatus; at: number }[];
  conversationId: string;
  updatedAt: number;
};

export type Message = { id: string; from: 'me' | 'them' | 'system'; text: string; at: number; image?: string };

export type Conversation = {
  id: string;
  counterpart: Party;
  // Sin consulta solo entre artistas: el cliente siempre escribe desde una (Maestro 2.6)
  commissionId?: string;
  messages: Message[];
  unread: number;
  updatedAt: number;
};

export type NotificationTarget =
  | { kind: 'commission'; id: string }
  | { kind: 'artist'; party: Party }
  | { kind: 'profile' }
  | { kind: 'comments' };

export type AppNotification = {
  id: string;
  who: Party;
  icon: keyof typeof Ionicons.glyphMap;
  text: string;
  at: number;
  read: boolean;
  target: NotificationTarget;
};

// Rango del anticipo y tarifa del plan Taller, como en backend/src/core/config.py
export const DEPOSIT_OPTIONS = [30, 40, 50];
export const SERVICE_FEE_PERCENT = 8;
export const MIN_PRICE = 2500;

// Lo que tarda la otra persona en responder en la demo
const REPLY_DELAY_MS = 4000;

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function formatColones(amount: number) {
  return `₡${Math.round(amount)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, '.')}`;
}

export function depositOf(quote: Quote) {
  return Math.round((quote.price * quote.depositPercent) / 100);
}

export function balanceOf(quote: Quote) {
  return quote.price - depositOf(quote);
}

export function artistNetOf(quote: Quote) {
  return Math.round(quote.price * (1 - SERVICE_FEE_PERCENT / 100));
}

const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'set', 'oct', 'nov', 'dic'];

export function relativeTime(at: number) {
  const elapsed = Date.now() - at;
  if (elapsed < MINUTE) return 'ahora';
  if (elapsed < HOUR) return `hace ${Math.floor(elapsed / MINUTE)} min`;
  if (elapsed < DAY) return `hace ${Math.floor(elapsed / HOUR)} h`;
  if (elapsed < 2 * DAY) return 'ayer';
  if (elapsed < 7 * DAY) return `hace ${Math.floor(elapsed / DAY)} d`;
  const date = new Date(at);
  return `${date.getDate()} ${MONTHS[date.getMonth()]}`;
}

export function clockTime(at: number) {
  const date = new Date(at);
  return `${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
}

export function deliveryDateIn(days: number) {
  const LONG_MONTHS = [
    'enero',
    'febrero',
    'marzo',
    'abril',
    'mayo',
    'junio',
    'julio',
    'agosto',
    'setiembre',
    'octubre',
    'noviembre',
    'diciembre',
  ];
  const date = new Date(Date.now() + days * DAY);
  return `${date.getDate()} de ${LONG_MONTHS[date.getMonth()]}`;
}

let sequence = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now()}-${(sequence += 1)}`;

const SOFI: Party = { name: 'Sofi Cerámica', initial: 'S', color: 'mostaza' };
const MATEO: Party = { name: 'Mateo Ríos', initial: 'M', color: 'verde' };
const TALLER: Party = { name: 'Taller Norte', initial: 'T', color: 'taupe' };
const CARO: Party = { name: 'Caro Méndez', initial: 'C', color: 'verde' };
const PAU: Party = { name: 'Pau Murales', initial: 'P', color: 'terracota' };

function buildDemo() {
  const now = Date.now();
  const ago = (ms: number) => now - ms;

  const commissions: Commission[] = [
    {
      id: 'c-caro',
      myRole: 'artista',
      counterpart: CARO,
      title: 'Retrato de mi perrita Canela',
      idea: 'Hola Luna, me encantaría un retrato de mi perrita en tu estilo, tamaño A4 para enmarcar. Te adjunto una foto de ella.',
      referenceImage: 'https://picsum.photos/seed/canela-perrita/600/600',
      status: 'consulta',
      history: [{ status: 'consulta', at: ago(40 * MINUTE) }],
      conversationId: 'm-caro',
      updatedAt: ago(40 * MINUTE),
    },
    {
      id: 'c-sofi',
      myRole: 'cliente',
      counterpart: SOFI,
      title: 'Set de tazas para mi mamá',
      idea: 'Quiero un set de cuatro tazas esmaltadas en tonos verdes, como las de tu última tanda, para regalarle a mi mamá en diciembre.',
      referenceImage: 'https://picsum.photos/seed/sofi-ceramica-2/800/900',
      status: 'cotizado',
      quote: {
        description: 'Set de 4 tazas de gres esmaltadas a mano en verde musgo, 350 ml cada una, con empaque para regalo.',
        price: 48000,
        revisions: 1,
        deliveryDate: deliveryDateIn(30),
        depositPercent: 50,
      },
      history: [
        { status: 'consulta', at: ago(2 * DAY) },
        { status: 'cotizado', at: ago(3 * HOUR) },
      ],
      conversationId: 'm-sofi',
      updatedAt: ago(3 * HOUR),
    },
    {
      id: 'c-mateo',
      myRole: 'cliente',
      counterpart: MATEO,
      title: 'Paisaje del Irazú para la sala',
      idea: 'Me gustaría un óleo del Irazú al atardecer, en tonos cálidos, para la pared grande de la sala.',
      referenceImage: 'https://picsum.photos/seed/mateo-rios-2/800/900',
      status: 'vista_previa',
      quote: {
        description: 'Óleo sobre lienzo de 60 × 40 cm, paisaje del Irazú al atardecer, con barniz final.',
        price: 120000,
        revisions: 2,
        deliveryDate: deliveryDateIn(10),
        depositPercent: 40,
      },
      previewImage: 'https://picsum.photos/seed/irazu-vista-previa/800/600',
      history: [
        { status: 'consulta', at: ago(21 * DAY) },
        { status: 'cotizado', at: ago(20 * DAY) },
        { status: 'en_proceso', at: ago(19 * DAY) },
        { status: 'vista_previa', at: ago(5 * HOUR) },
      ],
      conversationId: 'm-mateo',
      updatedAt: ago(5 * HOUR),
    },
    {
      id: 'c-taller',
      myRole: 'cliente',
      counterpart: TALLER,
      title: 'Billetera de cuero grabada',
      idea: 'Una billetera de cuero natural con mis iniciales grabadas a mano.',
      status: 'completado',
      quote: {
        description: 'Billetera de cuero curtido natural, cosida a mano, con iniciales grabadas.',
        price: 28000,
        revisions: 1,
        deliveryDate: '12 de setiembre',
        depositPercent: 50,
      },
      previewImage: 'https://picsum.photos/seed/billetera-cuero/800/600',
      rating: 5,
      history: [
        { status: 'consulta', at: ago(40 * DAY) },
        { status: 'cotizado', at: ago(39 * DAY) },
        { status: 'en_proceso', at: ago(38 * DAY) },
        { status: 'vista_previa', at: ago(30 * DAY) },
        { status: 'completado', at: ago(29 * DAY) },
      ],
      conversationId: 'm-taller',
      updatedAt: ago(29 * DAY),
    },
  ];

  const conversations: Conversation[] = [
    {
      id: 'm-caro',
      counterpart: CARO,
      commissionId: 'c-caro',
      unread: 1,
      updatedAt: ago(40 * MINUTE),
      messages: [
        {
          id: 'm-caro-1',
          from: 'them',
          text: commissions[0].idea,
          image: commissions[0].referenceImage,
          at: ago(40 * MINUTE),
        },
        {
          id: 'm-caro-2',
          from: 'system',
          text: 'Nueva consulta. Respondé con una cotización cuando estés lista.',
          at: ago(40 * MINUTE),
        },
      ],
    },
    {
      id: 'm-pau',
      counterpart: PAU,
      unread: 1,
      updatedAt: ago(2 * HOUR),
      messages: [
        {
          id: 'm-pau-1',
          from: 'them',
          text: 'Luna, ¿te sumás al mural colectivo de Turrialba en diciembre? Estamos buscando ilustradoras para la parte de la fauna.',
          at: ago(2 * HOUR),
        },
      ],
    },
    {
      id: 'm-sofi',
      counterpart: SOFI,
      commissionId: 'c-sofi',
      unread: 1,
      updatedAt: ago(3 * HOUR),
      messages: [
        { id: 'm-sofi-1', from: 'me', text: commissions[1].idea, image: commissions[1].referenceImage, at: ago(2 * DAY) },
        {
          id: 'm-sofi-2',
          from: 'them',
          text: '¡Hola Luna! Qué lindo regalo. ¿Las querés todas iguales o cada una con su variación?',
          at: ago(1 * DAY + 2 * HOUR),
        },
        { id: 'm-sofi-3', from: 'me', text: 'Cada una distinta, pero en la misma gama de verdes.', at: ago(1 * DAY) },
        { id: 'm-sofi-4', from: 'them', text: 'Perfecto, ya te mando la propuesta formal.', at: ago(3 * HOUR + 5 * MINUTE) },
        { id: 'm-sofi-5', from: 'system', text: 'Sofi Cerámica te envió una cotización por ₡48.000.', at: ago(3 * HOUR) },
      ],
    },
    {
      id: 'm-mateo',
      counterpart: MATEO,
      commissionId: 'c-mateo',
      unread: 1,
      updatedAt: ago(5 * HOUR),
      messages: [
        { id: 'm-mateo-1', from: 'me', text: commissions[2].idea, image: commissions[2].referenceImage, at: ago(21 * DAY) },
        { id: 'm-mateo-2', from: 'system', text: 'Pagaste el anticipo de ₡48.000. Mateo Ríos ya puede empezar.', at: ago(19 * DAY) },
        {
          id: 'm-mateo-3',
          from: 'them',
          text: 'Acá va la vista previa con marca de agua. Si te gusta, la aprobás y te mando la foto final en alta.',
          image: commissions[2].previewImage,
          at: ago(5 * HOUR),
        },
        {
          id: 'm-mateo-4',
          from: 'system',
          text: 'Se autorizó el saldo de ₡72.000 en tu tarjeta. Se cobra solo cuando apruebes.',
          at: ago(5 * HOUR),
        },
      ],
    },
    {
      id: 'm-taller',
      counterpart: TALLER,
      commissionId: 'c-taller',
      unread: 0,
      updatedAt: ago(29 * DAY),
      messages: [
        { id: 'm-taller-1', from: 'me', text: commissions[3].idea, at: ago(40 * DAY) },
        { id: 'm-taller-2', from: 'system', text: 'Aprobaste la entrega. Se cobró el saldo de ₡14.000.', at: ago(29 * DAY) },
        { id: 'm-taller-3', from: 'them', text: 'Gracias por la reseña, fue un placer.', at: ago(29 * DAY) },
      ],
    },
  ];

  const notifications: AppNotification[] = [
    {
      id: 'n-1',
      who: CARO,
      icon: 'mail',
      text: 'te envió una consulta.',
      at: ago(40 * MINUTE),
      read: false,
      target: { kind: 'commission', id: 'c-caro' },
    },
    {
      id: 'n-2',
      who: { name: 'Fede Arte', initial: 'F', color: 'mostaza' },
      icon: 'chatbubble',
      text: 'comentó: "Me encantaría ver el proceso completo"',
      at: ago(45 * MINUTE),
      read: false,
      target: { kind: 'comments' },
    },
    {
      id: 'n-3',
      who: { name: 'Ana Bordados', initial: 'A', color: 'taupe' },
      icon: 'person-add',
      text: 'empezó a seguirte.',
      at: ago(2 * HOUR),
      read: false,
      target: { kind: 'artist', party: { name: 'Ana Bordados', initial: 'A', color: 'taupe' } },
    },
    {
      id: 'n-4',
      who: SOFI,
      icon: 'document-text',
      text: 'te envió una cotización.',
      at: ago(3 * HOUR),
      read: true,
      target: { kind: 'commission', id: 'c-sofi' },
    },
    {
      id: 'n-5',
      who: MATEO,
      icon: 'images',
      text: 'entregó la vista previa de tu encargo.',
      at: ago(5 * HOUR),
      read: true,
      target: { kind: 'commission', id: 'c-mateo' },
    },
    {
      id: 'n-6',
      who: { name: 'Vale Grabados', initial: 'V', color: 'terracota' },
      icon: 'star',
      text: 'le dio me gusta a tu publicación.',
      at: ago(1 * DAY + 3 * HOUR),
      read: true,
      target: { kind: 'profile' },
    },
  ];

  return { commissions, conversations, notifications };
}

type CommissionsState = {
  commissions: Commission[];
  conversations: Conversation[];
  notifications: AppNotification[];
  loadDemo: () => void;
  clearAccount: () => void;
  createConsulta: (data: { artist: Party; idea: string; referenceImage?: string }) => string;
  sendMessage: (conversationId: string, text: string) => void;
  sendQuote: (commissionId: string, quote: Quote) => void;
  payDeposit: (commissionId: string, method: string) => void;
  rejectQuote: (commissionId: string) => void;
  deliverPreview: (commissionId: string, image: string) => void;
  approvePreview: (commissionId: string) => void;
  rate: (commissionId: string, stars: number) => void;
  markConversationRead: (conversationId: string) => void;
  markNotificationRead: (notificationId: string) => void;
};

// Mock de sesion como posts-store: se resetea al recargar la app. Cuando
// exista el backend, cada accion es una transicion del pedido en la API y
// las respuestas de la otra persona llegan por notificacion, no por timer.
export const useCommissionsStore = create<CommissionsState>((set, get) => {
  const findCommission = (id: string) => get().commissions.find((item) => item.id === id);

  const patchCommission = (id: string, changes: Partial<Commission>) =>
    set((state) => ({
      commissions: state.commissions.map((item) => {
        if (item.id !== id) return item;
        const status = changes.status ?? item.status;
        const history =
          changes.status && changes.status !== item.status
            ? [...item.history, { status: changes.status, at: Date.now() }]
            : item.history;
        return { ...item, ...changes, status, history, updatedAt: Date.now() };
      }),
    }));

  const addMessage = (conversationId: string, message: Omit<Message, 'id' | 'at'>) =>
    set((state) => ({
      conversations: state.conversations.map((item) =>
        item.id === conversationId
          ? {
              ...item,
              messages: [...item.messages, { ...message, id: nextId('msg'), at: Date.now() }],
              unread: message.from === 'them' ? item.unread + 1 : item.unread,
              updatedAt: Date.now(),
            }
          : item,
      ),
    }));

  const notify = (notification: Omit<AppNotification, 'id' | 'at' | 'read'>) =>
    set((state) => ({
      notifications: [{ ...notification, id: nextId('n'), at: Date.now(), read: false }, ...state.notifications],
    }));

  // La respuesta simulada solo corre si el pedido sigue donde lo dejamos
  const later = (commissionId: string, expected: CommissionStatus, run: (commission: Commission) => void) =>
    setTimeout(() => {
      const commission = findCommission(commissionId);
      if (commission?.status === expected) run(commission);
    }, REPLY_DELAY_MS);

  return {
    ...buildDemo(),

    loadDemo: () => set(buildDemo()),
    clearAccount: () => set({ commissions: [], conversations: [], notifications: [] }),

    createConsulta: ({ artist, idea, referenceImage }) => {
      const id = nextId('c');
      const conversationId = nextId('m');
      const now = Date.now();
      const title = idea.length > 42 ? `${idea.slice(0, 42).trimEnd()}…` : idea;
      set((state) => ({
        commissions: [
          {
            id,
            myRole: 'cliente',
            counterpart: artist,
            title,
            idea,
            referenceImage,
            status: 'consulta',
            history: [{ status: 'consulta', at: now }],
            conversationId,
            updatedAt: now,
          },
          ...state.commissions,
        ],
        conversations: [
          {
            id: conversationId,
            counterpart: artist,
            commissionId: id,
            unread: 0,
            updatedAt: now,
            messages: [
              { id: nextId('msg'), from: 'me', text: idea, image: referenceImage, at: now },
              {
                id: nextId('msg'),
                from: 'system',
                text: `Consulta enviada a ${artist.name}. Toda la conversación queda en este chat.`,
                at: now,
              },
            ],
          },
          ...state.conversations,
        ],
      }));

      later(id, 'consulta', (commission) => {
        const quote: Quote = {
          description: 'Pieza original hecha a mano según tu idea, con una ronda de cambios incluida.',
          price: 45000,
          revisions: 1,
          deliveryDate: deliveryDateIn(21),
          depositPercent: 50,
        };
        addMessage(commission.conversationId, {
          from: 'them',
          text: '¡Hola! Me encanta la idea. Te dejo la propuesta formal, cualquier cosa la ajustamos.',
        });
        addMessage(commission.conversationId, {
          from: 'system',
          text: `${artist.name} te envió una cotización por ${formatColones(quote.price)}.`,
        });
        patchCommission(commission.id, { status: 'cotizado', quote });
        notify({ who: artist, icon: 'document-text', text: 'te envió una cotización.', target: { kind: 'commission', id } });
      });

      return id;
    },

    sendMessage: (conversationId, text) => addMessage(conversationId, { from: 'me', text }),

    sendQuote: (commissionId, quote) => {
      const commission = findCommission(commissionId);
      if (!commission) return;
      patchCommission(commissionId, { status: 'cotizado', quote });
      addMessage(commission.conversationId, {
        from: 'system',
        text: `Enviaste una cotización por ${formatColones(quote.price)}.`,
      });

      later(commissionId, 'cotizado', (current) => {
        addMessage(current.conversationId, { from: 'them', text: '¡Me encanta, acepto! Ya pagué el anticipo 🙌' });
        addMessage(current.conversationId, {
          from: 'system',
          text: `${current.counterpart.name} pagó el anticipo de ${formatColones(depositOf(quote))}. Ya podés empezar.`,
        });
        patchCommission(commissionId, { status: 'en_proceso' });
        notify({
          who: current.counterpart,
          icon: 'cash',
          text: 'aceptó tu cotización y pagó el anticipo.',
          target: { kind: 'commission', id: commissionId },
        });
      });
    },

    payDeposit: (commissionId, method) => {
      const commission = findCommission(commissionId);
      if (!commission?.quote) return;
      const quote = commission.quote;
      patchCommission(commissionId, { status: 'en_proceso' });
      addMessage(commission.conversationId, {
        from: 'system',
        text: `Pagaste el anticipo de ${formatColones(depositOf(quote))} con ${method}. ${commission.counterpart.name} ya puede empezar.`,
      });

      later(commissionId, 'en_proceso', (current) => {
        const previewImage = `https://picsum.photos/seed/${commissionId}-vista-previa/800/600`;
        addMessage(current.conversationId, {
          from: 'them',
          text: '¡Ya está la vista previa! Contame qué te parece.',
          image: previewImage,
        });
        addMessage(current.conversationId, {
          from: 'system',
          text: `Se autorizó el saldo de ${formatColones(balanceOf(quote))}. Se cobra solo cuando apruebes.`,
        });
        patchCommission(commissionId, { status: 'vista_previa', previewImage });
        notify({
          who: current.counterpart,
          icon: 'images',
          text: 'entregó la vista previa de tu encargo.',
          target: { kind: 'commission', id: commissionId },
        });
      });
    },

    rejectQuote: (commissionId) => {
      const commission = findCommission(commissionId);
      if (!commission) return;
      patchCommission(commissionId, { status: 'rechazado' });
      addMessage(commission.conversationId, { from: 'system', text: 'Rechazaste la cotización. No se cobró nada.' });
    },

    deliverPreview: (commissionId, image) => {
      const commission = findCommission(commissionId);
      if (!commission?.quote) return;
      const quote = commission.quote;
      patchCommission(commissionId, { status: 'vista_previa', previewImage: image });
      addMessage(commission.conversationId, { from: 'me', text: 'Te dejo la vista previa.', image });
      addMessage(commission.conversationId, {
        from: 'system',
        text: `Entregaste la vista previa con marca de agua. Se autorizó el saldo de ${formatColones(balanceOf(quote))}.`,
      });

      later(commissionId, 'vista_previa', (current) => {
        addMessage(current.conversationId, { from: 'them', text: '¡Quedó precioso! Ya lo aprobé, muchas gracias.' });
        addMessage(current.conversationId, {
          from: 'system',
          text: `${current.counterpart.name} aprobó la entrega. Recibís ${formatColones(artistNetOf(quote))} después de la tarifa de servicio.`,
        });
        patchCommission(commissionId, { status: 'completado' });
        notify({
          who: current.counterpart,
          icon: 'checkmark-circle',
          text: 'aprobó tu entrega. El pago quedó liberado.',
          target: { kind: 'commission', id: commissionId },
        });
      });
    },

    approvePreview: (commissionId) => {
      const commission = findCommission(commissionId);
      if (!commission?.quote) return;
      patchCommission(commissionId, { status: 'completado' });
      addMessage(commission.conversationId, {
        from: 'system',
        text: `Aprobaste la vista previa. Se cobró el saldo de ${formatColones(balanceOf(commission.quote))} y se liberó el archivo final.`,
      });
    },

    rate: (commissionId, stars) => {
      const commission = findCommission(commissionId);
      if (!commission) return;
      patchCommission(commissionId, { rating: stars });
      addMessage(commission.conversationId, {
        from: 'system',
        text: `Calificaste el encargo con ${stars} ${stars === 1 ? 'estrella' : 'estrellas'}.`,
      });
    },

    markConversationRead: (conversationId) =>
      set((state) => ({
        conversations: state.conversations.map((item) => (item.id === conversationId ? { ...item, unread: 0 } : item)),
      })),

    markNotificationRead: (notificationId) =>
      set((state) => ({
        notifications: state.notifications.map((item) => (item.id === notificationId ? { ...item, read: true } : item)),
      })),
  };
});

// Que sigue en el pedido y si le toca a la cuenta propia
export function nextStepOf(commission: Commission): { text: string; mine: boolean } {
  const other = commission.counterpart.name;
  if (commission.myRole === 'cliente') {
    switch (commission.status) {
      case 'consulta':
        return { text: `Esperando la cotización de ${other}`, mine: false };
      case 'cotizado':
        return { text: 'Te toca: revisar la cotización', mine: true };
      case 'en_proceso':
        return { text: `${other} está trabajando en tu encargo`, mine: false };
      case 'vista_previa':
        return { text: 'Te toca: aprobar la vista previa', mine: true };
      case 'completado':
        return commission.rating
          ? { text: 'Encargo completado', mine: false }
          : { text: 'Te toca: calificar el encargo', mine: true };
      case 'rechazado':
        return { text: 'Rechazaste la cotización', mine: false };
    }
  }
  switch (commission.status) {
    case 'consulta':
      return { text: 'Te toca: enviar la cotización', mine: true };
    case 'cotizado':
      return { text: `Esperando que ${other} acepte`, mine: false };
    case 'en_proceso':
      return { text: 'Te toca: entregar la vista previa', mine: true };
    case 'vista_previa':
      return { text: `Esperando la aprobación de ${other}`, mine: false };
    case 'completado':
      return { text: 'Pago liberado', mine: false };
    case 'rechazado':
      return { text: `${other} rechazó la cotización`, mine: false };
  }
}
