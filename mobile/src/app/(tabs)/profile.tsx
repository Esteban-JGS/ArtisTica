import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Image, Pressable, ScrollView, Share, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppBackground } from '@/components/app-background';
import { Avatar } from '@/components/avatar';
import { usePostsStore } from '@/stores/posts-store';
import { useProfileStore } from '@/stores/profile-store';
import { colors, NOTE_SHADOW, roleColors } from '@/theme';

const FEATURED_COUNT = 3;
const PORTFOLIO_COUNT = 12;

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
  const profile = useProfileStore((state) => state.profile);
  const becomeArtist = useProfileStore((state) => state.becomeArtist);
  const allPosts = usePostsStore((state) => state.posts);
  const { width: windowWidth } = useWindowDimensions();
  // aspect-square con ancho en porcentaje no resuelve la altura dentro de
  // un flex-wrap en este motor de layout: las imagenes quedan en 0px de
  // alto y desaparecen. Se calcula un tamano fijo en su lugar.
  const gridItemSize = (windowWidth - 40 - 16) / 3;
  const ownColor = roleColors[profile.color];

  // Solo la cuenta con historial rellena la galeria con obras anteriores
  // a la app; una cuenta nueva muestra unicamente lo que publico.
  const ownPosts = allPosts.filter((post) => post.name === profile.name);
  const paddingNeeded = profile.stats ? Math.max(0, PORTFOLIO_COUNT - ownPosts.length) : 0;
  const portfolio = [
    ...ownPosts.map((post) => ({ id: post.id, image: post.image, caption: post.caption })),
    ...Array.from({ length: paddingNeeded }, (_, i) => ({
      id: `filler-${i}`,
      image: `https://picsum.photos/seed/${profile.handle}-portfolio-${i}/500/500`,
      caption: undefined as string | undefined,
    })),
  ];
  const featured = portfolio.slice(0, FEATURED_COUNT);
  const rest = portfolio.slice(FEATURED_COUNT);

  const openObra = (item: { image: string; caption?: string }) =>
    router.push({
      pathname: '/ver-obra',
      params: { image: item.image, caption: item.caption, authorName: profile.name },
    });

  const shareProfile = () =>
    Share.share({ message: `Mirá el perfil de ${profile.name} (@${profile.handle}) en Artística` });

  const openAccountMenu = () =>
    Alert.alert('Tu cuenta', `@${profile.handle}`, [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Cerrar sesión', style: 'destructive', onPress: () => router.replace('/') },
    ]);

  const activateArtist = () => {
    becomeArtist();
    router.push('/editar-perfil');
  };

  const meta = profile.stats
    ? `${profile.place} · Responde en ${profile.stats.responseDays}d · ${profile.stats.delivered} entregadas · ${profile.stats.followers} seguidores`
    : `${profile.place} · Nuevo en Artística`;

  return (
    <View className="flex-1 bg-sand-100">
      <AppBackground />
      <SafeAreaView edges={['top']} className="flex-1">
        <View className="flex-row items-center justify-between px-5 py-3">
          <Text className="text-base font-semibold text-ink">@{profile.handle}</Text>
          <Pressable
            onPress={openAccountMenu}
            accessibilityRole="button"
            accessibilityLabel="Ajustes de la cuenta"
            hitSlop={8}>
            <Ionicons name="settings-outline" size={22} color={colors.ink.DEFAULT} />
          </Pressable>
        </View>
        <ScrollView className="flex-1" showsVerticalScrollIndicator={false} contentContainerClassName="px-5 pb-8">
          {/* Foto de perfil pineada a la par de tus propias obras, no sola
              arriba de una caja de stats. */}
          <View className="flex-row justify-center pt-4" style={{ paddingLeft: featured.length > 0 ? 36 : 0 }}>
            <View style={[NOTE_SHADOW, { width: 104 }]} className="rounded-xl">
              <Pin color={ownColor.fg} />
              <View
                className="items-center justify-center overflow-hidden rounded-xl bg-sand-50"
                style={{ width: 104, height: 120 }}>
                {profile.photo ? (
                  <View
                    className="h-16 w-16 items-center justify-center overflow-hidden rounded-full"
                    style={{ borderWidth: 2, borderColor: ownColor.base }}>
                    <Image source={{ uri: profile.photo }} className="h-full w-full" />
                  </View>
                ) : (
                  <Avatar initial={profile.initial} color={profile.color} size={64} />
                )}
              </View>
            </View>

            {featured.map((item, index) => (
              <Pressable
                key={item.id}
                onPress={() => openObra(item)}
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
              </Pressable>
            ))}
          </View>

          <View className="mt-5 items-center gap-1.5">
            <View className="flex-row items-center gap-1.5">
              <Text className="font-serif text-2xl italic text-ink">{profile.name}</Text>
              {profile.verified && <Ionicons name="checkmark-circle" size={16} color={colors.accent.DEFAULT} />}
            </View>
            {profile.isArtist && profile.role !== '' && (
              <View className="rounded-full px-2 py-0.5" style={{ backgroundColor: ownColor.bg }}>
                <Text className="text-xs font-medium" style={{ color: ownColor.fg }}>
                  {profile.role}
                </Text>
              </View>
            )}
            {profile.bio !== '' && <Text className="mt-1 text-center text-sm text-stone-800">{profile.bio}</Text>}
            <Text className="mt-1 text-center text-xs text-stone-700">{meta}</Text>
            <View className="mt-2 flex-row gap-2">
              <Pressable onPress={() => router.push('/editar-perfil')} className="rounded-full bg-accent px-6 py-2">
                <Text className="text-sm font-semibold text-sand-50">Editar perfil</Text>
              </Pressable>
              <Pressable onPress={shareProfile} className="rounded-full bg-sand-50 px-6 py-2">
                <Text className="text-sm font-semibold text-ink">Compartir perfil</Text>
              </Pressable>
            </View>
          </View>

          {profile.isArtist ? (
            <View className="mt-6" style={[NOTE_SHADOW, { alignSelf: 'stretch' }]}>
              <Pin color={ownColor.fg} />
              <View className="gap-3 rounded-xl bg-sand-50 p-4">
                <View className="flex-row items-center justify-between">
                  <Text className="text-sm font-semibold text-ink">Ficha de comisión</Text>
                  <View
                    className="rounded-full px-2.5 py-1"
                    style={{
                      backgroundColor: profile.commissionsOpen ? 'rgba(63,107,99,0.16)' : 'rgba(139,130,121,0.16)',
                    }}>
                    <Text
                      className="text-[11px] font-semibold uppercase"
                      style={{ color: profile.commissionsOpen ? colors.sage : colors.stone[900] }}>
                      {profile.commissionsOpen ? 'Abierto' : 'Cerrado'}
                    </Text>
                  </View>
                </View>
                <Text className="text-sm text-stone-800">
                  Desde ₡{profile.priceLow}k hasta ₡{profile.priceHigh}k, según la pieza.
                </Text>
                <Text className="text-xs text-stone-700">
                  {profile.commissionsOpen
                    ? `Tomando pedidos hasta ${profile.openUntil}.`
                    : 'Por ahora no estás tomando pedidos nuevos. Abrí tu ficha desde Editar perfil.'}
                </Text>
                <Text className="text-xs italic text-stone-600">Así la ven los clientes en tu perfil.</Text>
              </View>
            </View>
          ) : (
            <View className="mt-6" style={[NOTE_SHADOW, { alignSelf: 'stretch' }]}>
              <Pin color={ownColor.fg} />
              <View className="gap-3 rounded-xl bg-sand-50 p-4">
                <Text className="text-sm font-semibold text-ink">¿Hacés arte?</Text>
                <Text className="text-sm text-stone-800">
                  Activá tu perfil de artista para publicar tus obras y recibir encargos con el pago protegido.
                  No tiene costo.
                </Text>
                <Pressable onPress={activateArtist} className="items-center rounded-full bg-accent py-3">
                  <Text className="text-sm font-semibold text-sand-50">Activar perfil de artista</Text>
                </Pressable>
              </View>
            </View>
          )}

          {profile.isArtist && (
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
          )}

          {profile.isArtist && tab === 'portafolio' ? (
            portfolio.length === 0 ? (
              <View className="items-center gap-3 py-10">
                <Ionicons name="images-outline" size={28} color={colors.stone[700]} />
                <Text className="text-center text-sm text-stone-700">
                  Tu portafolio está vacío. Publicá tu primera obra para que te encuentren.
                </Text>
                <Pressable onPress={() => router.push('/create')} className="rounded-full bg-accent px-5 py-2">
                  <Text className="text-sm font-semibold text-sand-50">Publicar una obra</Text>
                </Pressable>
              </View>
            ) : (
              <View className="flex-row flex-wrap gap-2 py-4">
                {rest.map((item) => (
                  <Pressable key={item.id} onPress={() => openObra(item)}>
                    <Image
                      source={{ uri: item.image }}
                      className="rounded-xl"
                      style={{ width: gridItemSize, height: gridItemSize }}
                    />
                  </Pressable>
                ))}
              </View>
            )
          ) : (
            profile.about !== '' && (
              <View className="py-4">
                <Text className="text-sm text-stone-800">{profile.about}</Text>
              </View>
            )
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
