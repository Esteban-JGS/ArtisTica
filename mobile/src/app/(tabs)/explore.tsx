import { Ionicons } from '@expo/vector-icons';
import { FlashList } from '@shopify/flash-list';
import { useMemo, useState } from 'react';
import { Image, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { AppBackground } from '@/components/app-background';
import { colors } from '@/theme';

const CATEGORIES = ['Todos', 'Músicos', 'Dibujantes', 'Pintores', 'Artesanos', 'Escultores'];

const ARTWORKS = [
  { id: '0', artist: 'Luna Atelier', category: 'Dibujantes' },
  { id: '1', artist: 'Mateo Ríos', category: 'Pintores' },
  { id: '2', artist: 'Sofi Cerámica', category: 'Artesanos' },
  { id: '3', artist: 'Taller Norte', category: 'Artesanos' },
  { id: '4', artist: 'Vale Grabados', category: 'Dibujantes' },
  { id: '5', artist: 'Nico Escultor', category: 'Escultores' },
  { id: '6', artist: 'Cami Lentes', category: 'Pintores' },
  { id: '7', artist: 'Diego Tinta', category: 'Dibujantes' },
  { id: '8', artist: 'Pau Murales', category: 'Pintores' },
  { id: '9', artist: 'Rita Telar', category: 'Artesanos' },
  { id: '10', artist: 'Fabián Sarchí', category: 'Músicos' },
  { id: '11', artist: 'Ana Bordados', category: 'Artesanos' },
].map((item) => ({ ...item, image: `https://picsum.photos/seed/explore-${item.id}/500/500` }));

export default function ExplorarScreen() {
  const [category, setCategory] = useState('Todos');
  const [query, setQuery] = useState('');

  const artworks = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return ARTWORKS.filter((item) => {
      const matchesCategory = category === 'Todos' || item.category === category;
      const matchesQuery = normalizedQuery === '' || item.artist.toLowerCase().includes(normalizedQuery);
      return matchesCategory && matchesQuery;
    });
  }, [category, query]);

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
          <Ionicons name="options-outline" size={18} color={colors.stone[700]} />
        </View>

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
        contentContainerClassName="px-4 pb-4"
        ListEmptyComponent={
          <View className="items-center py-16">
            <Text className="text-sm text-stone-700">No encontramos nada con esos filtros.</Text>
          </View>
        }
        renderItem={({ item }) => (
          <View className="m-1 flex-1 overflow-hidden rounded-2xl">
            <Image source={{ uri: item.image }} className="aspect-square w-full" />
          </View>
        )}
      />
    </View>
  );
}
