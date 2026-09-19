import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, ScrollView, Text, View } from 'react-native';

import { Avatar } from '@/components/avatar';

const FLOAT_SHADOW = {
  shadowColor: '#3d362f',
  shadowOpacity: 0.12,
  shadowRadius: 10,
  shadowOffset: { width: 0, height: 4 },
  elevation: 5,
};

// Space reserved at the top of the scrollable content so it starts right
// below the floating title card/bell and the floating tab pill.
const FLOATING_HEADER_HEIGHT = 168;

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
      <ScrollView
        contentContainerStyle={{ paddingTop: FLOATING_HEADER_HEIGHT }}
        contentContainerClassName="gap-4 px-5 pb-5"
        showsVerticalScrollIndicator={false}>
        <Pressable
          onPress={() => router.push('/create')}
          className="flex-row items-center gap-3 rounded-3xl bg-sand-50 p-4">
          <View className="h-12 w-12 items-center justify-center rounded-full bg-accent/10">
            <Ionicons name="add" size={24} color="#c2653b" />
          </View>
          <Text className="flex-1 text-sm font-medium text-stone-700">
            ¿Qué querés compartir hoy?
          </Text>
        </Pressable>

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

      <View pointerEvents="box-none" className="absolute inset-x-0 top-0 pt-14">
        <View className="flex-row items-center justify-between px-5 pb-3">
          <View
            className="flex-row items-center gap-2 rounded-2xl bg-sand-50 px-4 py-2.5"
            style={FLOAT_SHADOW}>
            <Image
              source={require('@/assets/images/logo-mark.png')}
              style={{ width: 22, height: 22 }}
              resizeMode="contain"
            />
            <Text className="font-serif text-2xl italic text-ink">Artística</Text>
          </View>
          <Pressable
            className="h-11 w-11 items-center justify-center rounded-full bg-sand-50"
            style={FLOAT_SHADOW}>
            <Ionicons name="notifications-outline" size={20} color="#201d1a" />
          </Pressable>
        </View>

        <View
          className="mx-5 flex-row rounded-full bg-sand-200 p-1"
          style={FLOAT_SHADOW}>
          <Pressable
            onPress={() => setTab('seguidos')}
            className={tab === 'seguidos' ? 'flex-1 rounded-full bg-sand-50 py-2' : 'flex-1 py-2'}>
            <Text
              className={
                tab === 'seguidos'
                  ? 'text-center text-sm font-semibold text-ink'
                  : 'text-center text-sm text-stone-800'
              }>
              Seguidos
            </Text>
          </Pressable>
          <Pressable
            onPress={() => setTab('para-ti')}
            className={tab === 'para-ti' ? 'flex-1 rounded-full bg-sand-50 py-2' : 'flex-1 py-2'}>
            <Text
              className={
                tab === 'para-ti'
                  ? 'text-center text-sm font-semibold text-ink'
                  : 'text-center text-sm text-stone-800'
              }>
              Para ti
            </Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}
