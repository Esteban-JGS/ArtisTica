import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Image, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppBackground } from '@/components/app-background';
import { usePostsStore } from '@/stores/posts-store';
import { colors, NOTE_SHADOW, roleColors } from '@/theme';

const FEATURED_COUNT = 3;
const PORTFOLIO_COUNT = 6;
const OPEN_UNTIL_MONTHS = ['enero', 'marzo', 'mayo', 'julio', 'setiembre', 'noviembre'];

// Nota pineada al corcho, igual que las publicaciones del feed (ver Pin
// en home.tsx): se duplica a proposito en vez de compartir un componente,
// siguiendo como ya esta hecho el resto de hojas de esta pantalla. El
// contenedor que la usa SIEMPRE tiene que declarar el mismo ancho que la
// tarjeta interna (ver uso abajo): el "50%" del pin se calcula contra
// ese ancho, y si el padre lo deja ambiguo (p. ej. un "items-center" sin
// ancho propio) el pin termina flotando fuera de la tarjeta.
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

// Deriva numeros creibles y estables a partir del nombre, para que cada
// artista mock se vea distinto sin necesitar backend todavia. Cuando
// exista, esto se reemplaza por los datos reales del artista.
function hashSeed(input: string) {
  let hash = 0;
  for (let index = 0; index < input.length; index += 1) {
    hash = (hash * 31 + input.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function mockCommissionStats(seed: string) {
  const hash = hashSeed(seed);
  const responseDays = (hash % 3) + 1;
  const delivered = 18 + (hash % 70);
  const followers = 400 + (hash % 42) * 57;
  const priceLow = 20 + (hash % 8) * 5;
  const priceHigh = priceLow + 40 + (hash % 6) * 15;
  const openUntil = OPEN_UNTIL_MONTHS[hash % OPEN_UNTIL_MONTHS.length];
  const isOpen = hash % 5 !== 0;
  return {
    responseDays,
    delivered,
    followers: followers >= 1000 ? `${(followers / 1000).toFixed(1)}k` : String(followers),
    priceLow,
    priceHigh,
    openUntil,
    isOpen,
  };
}

export default function PerfilArtistaScreen() {
  const { id, name, role, initial, color } = useLocalSearchParams<{
    id: string;
    name?: string;
    role?: string;
    initial?: string;
    color?: string;
  }>();
  const [isFollowing, setIsFollowing] = useState(false);
  const allPosts = usePostsStore((state) => state.posts);

  const roleColor = color && color in roleColors ? roleColors[color as keyof typeof roleColors] : roleColors.terracota;
  const displayName = name ?? id;
  const stats = useMemo(() => mockCommissionStats(id), [id]);

  const artistPosts = allPosts.filter((post) => post.name === displayName);
  const paddingNeeded = Math.max(0, PORTFOLIO_COUNT - artistPosts.length);
  const seed = encodeURIComponent(id);
  const portfolio = [
    ...artistPosts.map((post) => ({ id: post.id, image: post.image })),
    ...Array.from({ length: paddingNeeded }, (_, i) => ({
      id: `filler-${i}`,
      image: `https://picsum.photos/seed/${seed}-fill-${i}/500/500`,
    })),
  ];
  const featured = portfolio.slice(0, FEATURED_COUNT);
  const rest = portfolio.slice(FEATURED_COUNT);

  return (
    <View className="flex-1 bg-sand-100">
      <AppBackground />
      <SafeAreaView edges={['top']} className="flex-1">
        <View className="flex-row items-center justify-between px-5 py-3">
          <Pressable onPress={() => router.back()} hitSlop={8}>
            <Ionicons name="chevron-back" size={24} color={colors.ink.DEFAULT} />
          </Pressable>
          <Text className="text-base font-semibold text-ink">{displayName}</Text>
          <View style={{ width: 24 }} />
        </View>

        <ScrollView className="flex-1" showsVerticalScrollIndicator={false} contentContainerClassName="px-5 pb-8">
          {/* Foto de perfil pineada a la par de unas obras, no sola arriba
              de una caja de stats: asi el perfil abre mostrando quien
              sos y que haces en el mismo gesto, no en dos bloques separados. */}
          <View className="flex-row justify-center pt-4" style={{ paddingLeft: 36 }}>
            <View style={[NOTE_SHADOW, { width: 104 }]} className="rounded-xl">
              <Pin color={roleColor.fg} />
              <View
                className="items-center justify-center rounded-xl bg-sand-50"
                style={{ width: 104, height: 120 }}>
                <View
                  className="h-14 w-14 items-center justify-center rounded-full"
                  style={{ backgroundColor: roleColor.base }}>
                  <Text className="font-serif text-2xl text-sand-50">{initial ?? displayName?.[0]}</Text>
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
            <Text className="font-serif text-2xl italic text-ink">{displayName}</Text>
            {role && (
              <View className="rounded-full px-2 py-0.5" style={{ backgroundColor: roleColor.bg }}>
                <Text className="text-xs font-medium" style={{ color: roleColor.fg }}>
                  {role}
                </Text>
              </View>
            )}
            <Text className="mt-1 text-xs text-stone-700">
              Responde en {stats.responseDays}d · {stats.delivered} entregadas · {stats.followers} seguidores
            </Text>
            <Pressable
              onPress={() => setIsFollowing((value) => !value)}
              className={isFollowing ? 'mt-2 rounded-full bg-sand-50 px-6 py-2' : 'mt-2 rounded-full bg-accent px-6 py-2'}>
              <Text className={isFollowing ? 'text-sm font-semibold text-ink' : 'text-sm font-semibold text-sand-50'}>
                {isFollowing ? 'Siguiendo' : 'Seguir'}
              </Text>
            </Pressable>
          </View>

          <View className="mt-6" style={[NOTE_SHADOW, { alignSelf: 'stretch' }]}>
            <Pin color={roleColor.fg} />
            <View className="gap-3 rounded-xl bg-sand-50 p-4">
              <View className="flex-row items-center justify-between">
                <Text className="text-sm font-semibold text-ink">Ficha de comisión</Text>
                <View
                  className="rounded-full px-2.5 py-1"
                  style={{ backgroundColor: stats.isOpen ? 'rgba(63,107,99,0.16)' : 'rgba(139,130,121,0.16)' }}>
                  <Text
                    className="text-[11px] font-semibold uppercase"
                    style={{ color: stats.isOpen ? colors.sage : colors.stone[900] }}>
                    {stats.isOpen ? 'Abierto' : 'Cerrado'}
                  </Text>
                </View>
              </View>
              <Text className="text-sm text-stone-800">
                Desde ₡{stats.priceLow}k hasta ₡{stats.priceHigh}k, según la pieza.
              </Text>
              <Text className="text-xs text-stone-700">
                {stats.isOpen ? `Tomando pedidos hasta ${stats.openUntil}.` : 'Por ahora no está tomando pedidos nuevos.'}
              </Text>
              <Pressable
                onPress={() =>
                  router.push({ pathname: '/solicitar-comision', params: { artistName: displayName } })
                }
                disabled={!stats.isOpen}
                className={stats.isOpen ? 'items-center rounded-full bg-accent py-3' : 'items-center rounded-full bg-accent/40 py-3'}>
                <Text className="text-sm font-semibold text-sand-50">Solicitar comisión</Text>
              </Pressable>
            </View>
          </View>

          <View className="mt-6 flex-row flex-wrap gap-2">
            {rest.map((item) => (
              <Image key={item.id} source={{ uri: item.image }} className="aspect-square rounded-xl" style={{ width: '31.5%' }} />
            ))}
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
