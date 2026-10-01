import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { AppBackground } from '@/components/app-background';
import { Avatar } from '@/components/avatar';
import { StatusBadge, type CommissionStatus } from '@/components/status-badge';
import { colors } from '@/theme';

type AvatarColor = 'terracota' | 'verde' | 'mostaza' | 'taupe';
type Tab = 'chats' | 'comisiones' | 'notificaciones';

const CHATS: {
  id: string;
  name: string;
  initial: string;
  color: AvatarColor;
  status: CommissionStatus;
  preview: string;
  time: string;
}[] = [
  {
    id: '1',
    name: 'Luna Atelier',
    initial: 'L',
    color: 'terracota',
    status: 'Negociando',
    preview: '¡Me encanta la idea! Te envío una propuesta…',
    time: 'ahora',
  },
  {
    id: '2',
    name: 'Mateo Ríos',
    initial: 'M',
    color: 'verde',
    status: 'Entregado',
    preview: 'Tu obra ya está lista para revisión.',
    time: 'ayer',
  },
  {
    id: '3',
    name: 'Sofi Cerámica',
    initial: 'S',
    color: 'mostaza',
    status: 'Pagado',
    preview: '¿Qué tamaño estabas pensando?',
    time: 'lun',
  },
  {
    id: '4',
    name: 'Taller Norte',
    initial: 'T',
    color: 'taupe',
    status: 'Liberado',
    preview: 'Gracias por la reseña, fue un placer.',
    time: '3 sep',
  },
];

const NOTIFICATIONS: {
  id: string;
  name: string;
  initial: string;
  color: AvatarColor;
  icon: keyof typeof Ionicons.glyphMap;
  text: string;
  time: string;
}[] = [
  {
    id: '1',
    name: 'Caro Diseños',
    initial: 'C',
    color: 'verde',
    icon: 'star',
    text: 'le dio me gusta a tu publicación.',
    time: 'hace 10 min',
  },
  {
    id: '2',
    name: 'Fede Arte',
    initial: 'F',
    color: 'mostaza',
    icon: 'chatbubble',
    text: 'comentó: "Me encantaría ver el proceso completo"',
    time: 'hace 45 min',
  },
  {
    id: '3',
    name: 'Ana Bordados',
    initial: 'A',
    color: 'taupe',
    icon: 'person-add',
    text: 'empezó a seguirte.',
    time: 'hace 2 h',
  },
  {
    id: '4',
    name: 'Mateo Ríos',
    initial: 'M',
    color: 'verde',
    icon: 'document-text',
    text: 'aceptó tu cotización.',
    time: 'ayer',
  },
  {
    id: '5',
    name: 'Sofi Cerámica',
    initial: 'S',
    color: 'mostaza',
    icon: 'cash',
    text: 'tu pedido cambió a Pagado.',
    time: 'lun',
  },
];

export default function MensajesScreen() {
  const { tab: tabParam } = useLocalSearchParams<{ tab?: string }>();
  const tab: Tab = tabParam === 'chats' || tabParam === 'notificaciones' ? tabParam : 'comisiones';
  const setTab = (next: Tab) => router.setParams({ tab: next });

  return (
    <View className="flex-1 bg-sand-100">
      <AppBackground />
      <View className="flex-row items-center justify-between px-5 pb-3 pt-14">
        <Text className="font-serif text-3xl italic text-ink">Mensajes</Text>
        <Pressable className="h-10 w-10 items-center justify-center rounded-full bg-sand-50">
          <Ionicons name="search" size={18} color={colors.ink.DEFAULT} />
        </Pressable>
      </View>

      <View className="mx-5 mb-3 flex-row rounded-full bg-sand-200 p-1">
        <Pressable
          onPress={() => setTab('chats')}
          className={tab === 'chats' ? 'flex-1 rounded-full bg-sand-50 py-2' : 'flex-1 py-2'}>
          <Text className={tab === 'chats' ? 'text-center text-sm font-semibold text-ink' : 'text-center text-sm text-stone-800'}>
            Chats
          </Text>
        </Pressable>
        <Pressable
          onPress={() => setTab('comisiones')}
          className={tab === 'comisiones' ? 'flex-1 rounded-full bg-sand-50 py-2' : 'flex-1 py-2'}>
          <Text className={tab === 'comisiones' ? 'text-center text-sm font-semibold text-ink' : 'text-center text-sm text-stone-800'}>
            Comisiones
          </Text>
        </Pressable>
        <Pressable
          onPress={() => setTab('notificaciones')}
          className={tab === 'notificaciones' ? 'flex-1 rounded-full bg-sand-50 py-2' : 'flex-1 py-2'}>
          <Text className={tab === 'notificaciones' ? 'text-center text-sm font-semibold text-ink' : 'text-center text-sm text-stone-800'}>
            Notis
          </Text>
        </Pressable>
      </View>

      {tab === 'notificaciones' ? (
        <ScrollView contentContainerClassName="px-5">
          {NOTIFICATIONS.map((item) => (
            <View key={item.id} className="flex-row items-center gap-3 border-b border-sand-300 py-3">
              <View className="relative">
                <Avatar initial={item.initial} color={item.color} />
                <View
                  className="absolute -bottom-1 -right-1 h-5 w-5 items-center justify-center rounded-full bg-accent"
                  style={{ borderWidth: 2, borderColor: colors.sand[100] }}>
                  <Ionicons name={item.icon} size={10} color={colors.sand[50]} />
                </View>
              </View>
              <View className="flex-1">
                <Text className="text-sm text-ink">
                  <Text className="font-semibold">{item.name}</Text> {item.text}
                </Text>
              </View>
              <Text className="text-xs text-stone-600">{item.time}</Text>
            </View>
          ))}
        </ScrollView>
      ) : (
        <ScrollView contentContainerClassName="px-5">
          {CHATS.map((chat) => (
            <Pressable key={chat.id} className="flex-row items-center gap-3 border-b border-sand-300 py-3">
              <Avatar initial={chat.initial} color={chat.color} />
              <View className="flex-1 gap-1">
                <View className="flex-row items-center gap-2">
                  <Text className="font-semibold text-ink">{chat.name}</Text>
                  <StatusBadge status={chat.status} />
                </View>
                <Text className="text-sm text-stone-700" numberOfLines={1}>
                  {chat.preview}
                </Text>
              </View>
              <Text className="text-xs text-stone-600">{chat.time}</Text>
            </Pressable>
          ))}
        </ScrollView>
      )}
    </View>
  );
}
