import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Image, Pressable, ScrollView, Text, View } from 'react-native';

import { AppBackground } from '@/components/app-background';
import { BACKGROUND_OPTIONS, backgroundSource, useBackgroundStore } from '@/stores/background-store';
import { colors } from '@/theme';

const PORTFOLIO = Array.from({ length: 6 }, (_, i) => ({
  id: String(i),
  image: `https://picsum.photos/seed/portfolio-${i}/500/500`,
}));

export default function PerfilScreen() {
  const [tab, setTab] = useState<'portafolio' | 'sobre-mi'>('portafolio');
  const [isFollowing, setIsFollowing] = useState(false);
  const backgroundId = useBackgroundStore((state) => state.backgroundId);
  const setBackgroundId = useBackgroundStore((state) => state.setBackgroundId);

  return (
    <View className="flex-1 bg-sand-100">
      <AppBackground />
      <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
      <View className="h-56 bg-sage">
        <Image
          source={{ uri: 'https://picsum.photos/seed/profile-cover/800/500' }}
          className="h-full w-full"
        />
      </View>

      <View className="-mt-10 px-5">
        <View className="h-20 w-20 items-center justify-center rounded-full border-4 border-sand-100 bg-accent">
          <Text className="font-serif text-3xl text-sand-50">L</Text>
        </View>

        <View className="mt-3 flex-row items-center gap-1.5">
          <Text className="font-serif text-3xl italic text-ink">Luna Atelier</Text>
          <Ionicons name="checkmark-circle" size={20} color={colors.accent.DEFAULT} />
        </View>
        <Text className="mt-1 text-sm font-medium text-accent-dark">Ilustradora digital</Text>
        <Text className="mt-2 text-sm text-stone-800">
          Creo mundos suaves para quienes todavía creen en la magia cotidiana. Comisiones abiertas
          hasta noviembre.
        </Text>

        <View className="mt-4 flex-row justify-between rounded-2xl bg-sand-50 px-4 py-3">
          <View className="items-center">
            <Text className="text-base font-semibold text-ink">148</Text>
            <Text className="text-xs text-stone-700">OBRAS</Text>
          </View>
          <View className="items-center">
            <Text className="text-base font-semibold text-ink">12.4k</Text>
            <Text className="text-xs text-stone-700">SEGUIDORES</Text>
          </View>
          <View className="items-center">
            <Text className="text-base font-semibold text-ink">386</Text>
            <Text className="text-xs text-stone-700">SIGUIENDO</Text>
          </View>
        </View>

        <View className="mt-4 flex-row gap-3">
          <Pressable
            onPress={() => setIsFollowing((value) => !value)}
            className={
              isFollowing
                ? 'flex-1 items-center rounded-full bg-sand-50 py-3'
                : 'flex-1 items-center rounded-full bg-accent py-3'
            }>
            <Text className={isFollowing ? 'font-semibold text-ink' : 'font-semibold text-sand-50'}>
              {isFollowing ? 'Siguiendo' : 'Seguir'}
            </Text>
          </Pressable>
          <Pressable className="flex-1 items-center rounded-full bg-sand-50 py-3">
            <Text className="font-semibold text-ink">Solicitar comisión</Text>
          </Pressable>
        </View>

        <View className="mt-6 gap-3 rounded-2xl bg-sand-50 p-4">
          <Text className="text-sm font-semibold text-ink">Personalización</Text>
          <Text className="text-xs text-stone-700">Elegí el fondo de la app</Text>
          <View className="flex-row gap-3">
            {BACKGROUND_OPTIONS.map((option) => {
              const isSelected = option.id === backgroundId;
              return (
                <Pressable
                  key={option.id}
                  onPress={() => setBackgroundId(option.id)}
                  className="flex-1 items-center gap-1.5">
                  <View
                    className={
                      isSelected
                        ? 'h-16 w-full overflow-hidden rounded-xl border-2 border-accent'
                        : 'h-16 w-full overflow-hidden rounded-xl border border-sand-300'
                    }>
                    <Image source={backgroundSource(option.id, 200)} className="h-full w-full" />
                    {isSelected && (
                      <View className="absolute inset-0 items-center justify-center bg-ink/20">
                        <Ionicons name="checkmark-circle" size={20} color={colors.sand[50]} />
                      </View>
                    )}
                  </View>
                  <Text
                    className={
                      isSelected ? 'text-xs font-semibold text-ink' : 'text-xs text-stone-700'
                    }>
                    {option.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <View className="mt-6 flex-row gap-6 border-b border-sand-300">
          <Pressable onPress={() => setTab('portafolio')} className="pb-3">
            <Text
              className={
                tab === 'portafolio'
                  ? 'border-b-2 border-ink pb-3 text-sm font-semibold text-ink'
                  : 'text-sm text-stone-700'
              }>
              Portafolio
            </Text>
          </Pressable>
          <Pressable onPress={() => setTab('sobre-mi')} className="pb-3">
            <Text
              className={
                tab === 'sobre-mi'
                  ? 'border-b-2 border-ink pb-3 text-sm font-semibold text-ink'
                  : 'text-sm text-stone-700'
              }>
              Sobre mí
            </Text>
          </Pressable>
        </View>

        {tab === 'portafolio' ? (
          <View className="flex-row flex-wrap gap-2 py-4">
            {PORTFOLIO.map((item) => (
              <Image
                key={item.id}
                source={{ uri: item.image }}
                className="aspect-square rounded-xl"
                style={{ width: '31.5%' }}
              />
            ))}
          </View>
        ) : (
          <View className="py-4">
            <Text className="text-sm text-stone-800">
              Ilustradora digital especializada en escenas íntimas y paletas suaves. Trabajo por
              comisión desde 2019.
            </Text>
          </View>
        )}
      </View>
      </ScrollView>
    </View>
  );
}
