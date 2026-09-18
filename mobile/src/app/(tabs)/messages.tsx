import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { Avatar } from '@/components/avatar';
import { StatusBadge, type CommissionStatus } from '@/components/status-badge';

const CHATS: {
  id: string;
  name: string;
  initial: string;
  color: 'terracota' | 'verde' | 'mostaza' | 'taupe';
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

export default function MensajesScreen() {
  const [tab, setTab] = useState<'chats' | 'comisiones'>('comisiones');

  return (
    <View className="flex-1 bg-sand-100">
      <View className="flex-row items-center justify-between px-5 pb-3 pt-14">
        <Text className="font-serif text-3xl italic text-ink">Mensajes</Text>
        <Pressable className="h-10 w-10 items-center justify-center rounded-full bg-sand-50">
          <Ionicons name="search" size={18} color="#201d1a" />
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
      </View>

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
    </View>
  );
}
