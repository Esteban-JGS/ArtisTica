import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Image, Pressable, ScrollView, Text, View } from 'react-native';

import { Avatar } from '@/components/avatar';

const POSTS = [
  {
    id: '1',
    name: 'Luna Atelier',
    role: 'Ilustradora',
    initial: 'L',
    color: 'terracota' as const,
    time: 'hace 2 h',
    place: 'Buenos Aires',
    image: 'https://picsum.photos/seed/luna-atelier/800/900',
    caption: 'Fragmentos de luz para días que necesitan un poco más de color.',
    likes: '1.3k',
    comments: 24,
    shares: 8,
    acceptsCommissions: true,
  },
  {
    id: '2',
    name: 'Mateo Ríos',
    role: 'Pintor',
    initial: 'M',
    color: 'verde' as const,
    time: 'hace 5 h',
    place: 'Rosario',
    image: 'https://picsum.photos/seed/mateo-rios/800/900',
    caption: 'Explorando texturas nuevas esta semana.',
    likes: '842',
    comments: 12,
    shares: 3,
    acceptsCommissions: false,
  },
];

export default function InicioScreen() {
  const [tab, setTab] = useState<'seguidos' | 'para-ti'>('seguidos');

  return (
    <View className="flex-1 bg-sand-100">
      <View className="flex-row items-center justify-between border-b border-sand-300 px-5 pb-3 pt-14">
        <Text className="font-serif text-3xl italic text-ink">Artistica</Text>
        <Pressable className="h-10 w-10 items-center justify-center rounded-full bg-sand-50">
          <Ionicons name="notifications-outline" size={20} color="#201d1a" />
        </Pressable>
      </View>

      <View className="flex-row gap-6 border-b border-sand-300 px-5 pt-3">
        <Pressable onPress={() => setTab('seguidos')} className="pb-3">
          <Text
            className={
              tab === 'seguidos'
                ? 'border-b-2 border-ink pb-3 text-sm font-semibold text-ink'
                : 'text-sm font-medium text-stone-800'
            }>
            Seguidos
          </Text>
        </Pressable>
        <Pressable onPress={() => setTab('para-ti')} className="pb-3">
          <Text
            className={
              tab === 'para-ti'
                ? 'border-b-2 border-ink pb-3 text-sm font-semibold text-ink'
                : 'text-sm font-medium text-stone-800'
            }>
            Para ti
          </Text>
        </Pressable>
      </View>

      <ScrollView contentContainerClassName="gap-4 p-5" showsVerticalScrollIndicator={false}>
        {POSTS.map((post) => (
          <View key={post.id} className="gap-3 rounded-3xl bg-sand-50 p-4">
            <View className="flex-row items-center gap-3">
              <Avatar initial={post.initial} color={post.color} />
              <View className="flex-1">
                <View className="flex-row items-center gap-2">
                  <Text className="font-semibold text-ink">{post.name}</Text>
                  <View className="rounded-full bg-sand-200 px-2 py-0.5">
                    <Text className="text-xs text-stone-800">{post.role}</Text>
                  </View>
                </View>
                <Text className="text-xs text-stone-700">
                  {post.time} · {post.place}
                </Text>
              </View>
              <Ionicons name="ellipsis-horizontal" size={18} color="#8b8279" />
            </View>

            <View className="overflow-hidden rounded-2xl">
              <Image source={{ uri: post.image }} className="aspect-[4/5] w-full" />
              {post.acceptsCommissions && (
                <View className="absolute bottom-3 left-3 rounded-full bg-ink/70 px-3 py-1.5">
                  <Text className="text-xs font-medium text-sand-50">Acepta comisiones</Text>
                </View>
              )}
            </View>

            <View className="flex-row items-center gap-5">
              <View className="flex-row items-center gap-1.5">
                <Ionicons name="heart-outline" size={20} color="#c2653b" />
                <Text className="text-sm text-stone-800">{post.likes}</Text>
              </View>
              <View className="flex-row items-center gap-1.5">
                <Ionicons name="chatbubble-outline" size={19} color="#8b8279" />
                <Text className="text-sm text-stone-800">{post.comments}</Text>
              </View>
              <View className="flex-row items-center gap-1.5">
                <Ionicons name="paper-plane-outline" size={19} color="#8b8279" />
                <Text className="text-sm text-stone-800">{post.shares}</Text>
              </View>
              <View className="flex-1 items-end">
                <Ionicons name="bookmark-outline" size={19} color="#8b8279" />
              </View>
            </View>

            <Text className="text-sm text-ink">{post.caption}</Text>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}
