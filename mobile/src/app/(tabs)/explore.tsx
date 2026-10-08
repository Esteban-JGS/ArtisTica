import { Ionicons } from '@expo/vector-icons';
import { FlashList } from '@shopify/flash-list';
import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { Image, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { AppBackground } from '@/components/app-background';
import { type Post, usePostsStore } from '@/stores/posts-store';
import { colors } from '@/theme';

const CATEGORIES = ['Todos', 'Dibujantes', 'Pintores', 'Artesanos', 'Escultores', 'Fotógrafos', 'Músicos'];

// De qué categoría es cada oficio de los artistas de la demo
const ROLE_CATEGORY: Record<string, string> = {
  Ilustradora: 'Dibujantes',
  Grabadora: 'Dibujantes',
  Tatuador: 'Dibujantes',
  Pintor: 'Pintores',
  Muralista: 'Pintores',
  Ceramista: 'Artesanos',
  Artesanos: 'Artesanos',
  Tejedora: 'Artesanos',
  Luthier: 'Artesanos',
  Escultor: 'Escultores',
  Fotógrafa: 'Fotógrafos',
};

// Artistas con pocos seguidores: Explorar les reserva lugar (ver feed.py en el backend)
const NEW_TALENT = ['Rita Telar', 'Nico Escultor', 'Taller Norte'];

function categoryOf(post: Post) {
  const fromTag = CATEGORIES.find((item) => post.tags.includes(item.toLowerCase()));
  return fromTag ?? ROLE_CATEGORY[post.role];
}

function openArtwork(post: Post) {
  router.push({
    pathname: '/ver-obra',
    params: {
      image: post.image,
      caption: post.caption,
      authorName: post.name,
      authorRole: post.role,
      authorColor: post.color,
      acceptsCommissions: post.acceptsCommissions ? '1' : '0',
    },
  });
}

export default function ExplorarScreen() {
  const posts = usePostsStore((state) => state.posts);
  const [category, setCategory] = useState('Todos');
  const [query, setQuery] = useState('');
  const [onlyOpen, setOnlyOpen] = useState(false);

  const artworks = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return posts.filter((post) => {
      const matchesCategory = category === 'Todos' || categoryOf(post) === category;
      const matchesQuery =
        normalizedQuery === '' ||
        [post.name, post.caption, ...post.tags].some((text) => text.toLowerCase().includes(normalizedQuery));
      return matchesCategory && matchesQuery && (!onlyOpen || post.acceptsCommissions);
    });
  }, [category, onlyOpen, posts, query]);

  return (
    <View className="flex-1 bg-sand-100">
      <AppBackground />
      <View className="gap-3 px-5 pb-3 pt-14">
        <View className="flex-row items-center gap-2 rounded-full bg-sand-50 px-4 py-3">
          <Ionicons name="search" size={18} color={colors.stone[700]} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Buscar artistas, obras…"
            placeholderTextColor={colors.stone[700]}
            className="flex-1 text-sm text-ink"
          />
          <Pressable
            onPress={() => setOnlyOpen((value) => !value)}
            accessibilityRole="switch"
            accessibilityState={{ checked: onlyOpen }}
            accessibilityLabel="Solo abiertos a comisiones"
            hitSlop={8}
            className={onlyOpen ? 'h-7 w-7 items-center justify-center rounded-full bg-accent' : 'h-7 w-7 items-center justify-center rounded-full'}>
            <Ionicons name="options-outline" size={18} color={onlyOpen ? colors.sand[50] : colors.stone[700]} />
          </Pressable>
        </View>

        {onlyOpen && (
          <Pressable
            onPress={() => setOnlyOpen(false)}
            className="flex-row items-center gap-1.5 self-start rounded-full bg-gold/20 px-3 py-1.5">
            <Ionicons name="cash-outline" size={14} color={colors.ink.DEFAULT} />
            <Text className="text-xs font-semibold text-ink">Solo abiertos a comisiones</Text>
            <Ionicons name="close" size={14} color={colors.ink.DEFAULT} />
          </Pressable>
        )}

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="gap-2">
          {CATEGORIES.map((item) => (
            <Pressable
              key={item}
              onPress={() => setCategory(item)}
              className={
                item === category
                  ? 'rounded-full bg-accent px-4 py-2'
                  : 'rounded-full bg-sand-50 px-4 py-2'
              }>
              <Text className={item === category ? 'text-sm font-semibold text-sand-50' : 'text-sm text-ink'}>
                {item}
              </Text>
            </Pressable>
          ))}
        </ScrollView>
      </View>

      <FlashList
        data={artworks}
        numColumns={2}
        keyExtractor={(item) => item.id}
        contentContainerClassName="px-4 pb-32"
        ListEmptyComponent={
          <View className="items-center py-16">
            <Text className="text-sm text-stone-700">No encontramos nada con esos filtros.</Text>
          </View>
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => openArtwork(item)}
            accessibilityLabel={`Obra de ${item.name}`}
            className="m-1 flex-1 overflow-hidden rounded-2xl">
            <Image source={{ uri: item.image }} className="aspect-square w-full" />
            {NEW_TALENT.includes(item.name) && (
              <View className="absolute left-2 top-2 rounded-full bg-sand-50/90 px-2 py-0.5">
                <Text className="text-[10px] font-semibold text-sage">Nuevo talento</Text>
              </View>
            )}
            {item.acceptsCommissions && (
              <View className="absolute right-2 top-2 h-6 w-6 items-center justify-center rounded-full bg-gold">
                <Ionicons name="cash-outline" size={13} color={colors.ink.DEFAULT} />
              </View>
            )}
            <View className="absolute inset-x-0 bottom-0 bg-ink/45 px-2.5 py-1.5">
              <Text className="text-xs font-semibold text-sand-50" numberOfLines={1}>
                {item.name}
              </Text>
            </View>
          </Pressable>
        )}
      />
    </View>
  );
}
