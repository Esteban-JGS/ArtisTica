import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Image, Pressable, ScrollView, Text, View } from 'react-native';

import { AppBackground } from '@/components/app-background';
import { usePostsStore } from '@/stores/posts-store';
import { BACKGROUND_OPTIONS, backgroundSource, useBackgroundStore } from '@/stores/background-store';
import { colors, NOTE_SHADOW, roleColors } from '@/theme';

const FEATURED_COUNT = 3;
const PORTFOLIO_COUNT = 6;
const OWN_NAME = 'Luna Atelier';
const OWN_COLOR = roleColors.terracota;

// Nota pineada al corcho, igual que las publicaciones del feed (ver Pin
// en home.tsx): se duplica a proposito en vez de compartir un componente,
// como ya esta hecho en el resto de pantallas de perfil y las hojas.
function Pin({ color }: { color: string }) {
  return (
    <View
      pointerEvents="none"
      style={{
        position: 'absolute',
        top: -9,
        left: '50%',
        marginLeft: -9,
        zIndex: 10,
        elevation: 10,
        height: 18,
        width: 18,
        borderRadius: 9,
        backgroundColor: color,
        shadowColor: '#000',
        shadowOpacity: 0.3,
        shadowRadius: 3,
        shadowOffset: { width: 0, height: 2 },
      }}>
      <View
        style={{
          position: 'absolute',
          top: 3,
          left: 4,
          height: 5,
          width: 5,
          borderRadius: 2.5,
          backgroundColor: 'rgba(255,255,255,0.45)',
        }}
      />
    </View>
  );
}

export default function PerfilScreen() {
  const [tab, setTab] = useState<'portafolio' | 'sobre-mi'>('portafolio');
  const backgroundId = useBackgroundStore((state) => state.backgroundId);
  const setBackgroundId = useBackgroundStore((state) => state.setBackgroundId);
  const allPosts = usePostsStore((state) => state.posts);

  const ownPosts = allPosts.filter((post) => post.name === OWN_NAME);
  const paddingNeeded = Math.max(0, PORTFOLIO_COUNT - ownPosts.length);
  const portfolio = [
    ...ownPosts.map((post) => ({ id: post.id, image: post.image })),
    ...Array.from({ length: paddingNeeded }, (_, i) => ({
      id: `filler-${i}`,
      image: `https://picsum.photos/seed/luna-atelier-portfolio-${i}/500/500`,
    })),
  ];
  const featured = portfolio.slice(0, FEATURED_COUNT);
  const rest = portfolio.slice(FEATURED_COUNT);

  return (
    <View className="flex-1 bg-sand-100">
      <AppBackground />
      <ScrollView className="flex-1" showsVerticalScrollIndicator={false} contentContainerClassName="px-5 pb-8 pt-16">
        {/* Foto de perfil pineada a la par de tus propias obras, no sola
            arriba de una caja de stats. */}
        <View className="flex-row justify-center" style={{ paddingLeft: 36 }}>
          <View style={[NOTE_SHADOW, { width: 104 }]} className="rounded-xl">
            <Pin color={OWN_COLOR.fg} />
            <View
              className="items-center justify-center rounded-xl bg-sand-50"
              style={{ width: 104, height: 120 }}>
              <View
                className="h-14 w-14 items-center justify-center rounded-full"
                style={{ backgroundColor: OWN_COLOR.base }}>
                <Text className="font-serif text-2xl text-sand-50">L</Text>
              </View>
            </View>
          </View>

          {featured.map((item, index) => (
            <View
              key={item.id}
              style={[
                NOTE_SHADOW,
                {
                  width: 92,
                  height: 92,
                  marginLeft: -22,
                  marginTop: index % 2 === 0 ? 16 : 26,
                  transform: [{ rotate: `${index % 2 === 0 ? -6 : 5}deg` }],
                  zIndex: FEATURED_COUNT - index,
                },
              ]}
              className="overflow-hidden rounded-xl bg-sand-50">
              <Image source={{ uri: item.image }} className="h-full w-full" />
            </View>
          ))}
        </View>

        <View className="mt-5 items-center gap-1.5">
          <View className="flex-row items-center gap-1.5">
            <Text className="font-serif text-2xl italic text-ink">{OWN_NAME}</Text>
            <Ionicons name="checkmark-circle" size={16} color={colors.accent.DEFAULT} />
          </View>
          <View className="rounded-full px-2 py-0.5" style={{ backgroundColor: OWN_COLOR.bg }}>
            <Text className="text-xs font-medium" style={{ color: OWN_COLOR.fg }}>
              Ilustradora digital
            </Text>
          </View>
          <Text className="mt-1 text-center text-sm text-stone-800">
            Creo mundos suaves para quienes todavía creen en la magia cotidiana.
          </Text>
          <Text className="mt-1 text-xs text-stone-700">
            Responde en 1d · 48 entregadas · 12.4k seguidores
          </Text>
        </View>

        <View className="mt-6" style={[NOTE_SHADOW, { alignSelf: 'stretch' }]}>
          <Pin color={OWN_COLOR.fg} />
          <View className="gap-3 rounded-xl bg-sand-50 p-4">
            <View className="flex-row items-center justify-between">
              <Text className="text-sm font-semibold text-ink">Tu ficha de comisión</Text>
              <View className="rounded-full px-2.5 py-1" style={{ backgroundColor: 'rgba(63,107,99,0.16)' }}>
                <Text className="text-[11px] font-semibold uppercase" style={{ color: colors.sage }}>
                  Abierto
                </Text>
              </View>
            </View>
            <Text className="text-sm text-stone-800">Desde ₡40k hasta ₡120k, según la pieza.</Text>
            <Text className="text-xs text-stone-700">Tomando pedidos hasta noviembre.</Text>
            <Text className="text-xs italic text-stone-600">Así la ven los clientes en tu perfil.</Text>
          </View>
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
            {rest.map((item) => (
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
      </ScrollView>
    </View>
  );
}
