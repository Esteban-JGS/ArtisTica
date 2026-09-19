import { Ionicons } from '@expo/vector-icons';
import { FlashList } from '@shopify/flash-list';
import { useState } from 'react';
import { Image, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { RusticTexture } from '@/components/paper-texture';

const CATEGORIES = ['Todos', 'Músicos', 'Dibujantes', 'Pintores', 'Artesanos', 'Escultores'];

const ARTWORKS = Array.from({ length: 12 }, (_, i) => ({
  id: String(i),
  image: `https://picsum.photos/seed/explore-${i}/500/500`,
}));

export default function ExplorarScreen() {
  const [category, setCategory] = useState('Todos');

  return (
    <View className="flex-1 bg-sand-100">
      <RusticTexture />
      <View className="gap-3 px-5 pb-3 pt-14">
        <View className="flex-row items-center gap-2 rounded-full bg-sand-50 px-4 py-3">
          <Ionicons name="search" size={18} color="#8b8279" />
          <TextInput
            placeholder="Buscar artistas, obras…"
            placeholderTextColor="#8b8279"
            className="flex-1 text-sm text-ink"
          />
          <Ionicons name="options-outline" size={18} color="#8b8279" />
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
        data={ARTWORKS}
        numColumns={2}
        keyExtractor={(item) => item.id}
        contentContainerClassName="px-4 pb-4"
        renderItem={({ item }) => (
          <View className="m-1 flex-1 overflow-hidden rounded-2xl">
            <Image source={{ uri: item.image }} className="aspect-square w-full" />
          </View>
        )}
      />
    </View>
  );
}
