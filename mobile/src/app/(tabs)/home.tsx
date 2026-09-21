import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Image, Pressable, Text, View } from 'react-native';

import { AppBackground } from '@/components/app-background';
import { Avatar } from '@/components/avatar';
import Animated, {
  Easing,
  interpolate,
  runOnJS,
  useAnimatedScrollHandler,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

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

// How far you need to scroll before the text pill collapses into the
// small icon pair under "Artística".
const COLLAPSE_DISTANCE = 40;
const MINI_TOGGLE_HEIGHT = 30;

const ROLE_BADGE_COLORS: Record<string, { bg: string; fg: string }> = {
  terracota: { bg: 'rgba(194,101,59,0.14)', fg: '#a1512d' },
  verde: { bg: 'rgba(63,107,99,0.16)', fg: '#3f6b63' },
  mostaza: { bg: 'rgba(217,154,63,0.2)', fg: '#93641f' },
  taupe: { bg: 'rgba(139,130,121,0.16)', fg: '#5c534b' },
};

const NOTE_SHADOW = {
  shadowColor: '#3d362f',
  shadowOpacity: 0.2,
  shadowRadius: 10,
  shadowOffset: { width: 0, height: 6 },
  elevation: 6,
};

// Posts read as notes pinned to a corkboard: each one taped down at its
// own random tilt instead of a fixed left/right pattern.
const NOTE_MAX_ROTATION_DEG = 3;
const TAPE_MAX_ROTATION_DEG = 9;

function randomInRange(max: number) {
  return (Math.random() * 2 - 1) * max;
}

// Rolled once when the card mounts (not seeded by id, so it isn't stuck
// repeating a near-identical angle for consecutive posts) and memoized
// so it doesn't reshuffle on re-renders like scroll updates.
function useNoteTilt() {
  return useMemo(
    () => ({
      note: randomInRange(NOTE_MAX_ROTATION_DEG),
      tape: randomInRange(TAPE_MAX_ROTATION_DEG),
    }),
    [],
  );
}

function WashiTape({ color, rotation }: { color: string; rotation: number }) {
  return (
    <View
      pointerEvents="none"
      style={{
        position: 'absolute',
        top: -12,
        left: '50%',
        marginLeft: -36,
        width: 72,
        height: 24,
        backgroundColor: color,
        opacity: 0.85,
        borderRadius: 2,
        zIndex: 10,
        elevation: 10,
        transform: [{ rotate: `${rotation}deg` }],
        shadowColor: '#000',
        shadowOpacity: 0.15,
        shadowRadius: 3,
        shadowOffset: { width: 0, height: 2 },
      }}
    />
  );
}

// A small fan of stars that pop up and out when you tap "me gusta" —
// each one on its own delay/angle so the burst reads as organic
// instead of a single sprite exploding outward.
const STAR_BURST_CONFIG = [
  { angle: -90, delay: 0 },
  { angle: -65, delay: 40 },
  { angle: -115, delay: 20 },
  { angle: -75, delay: 80 },
  { angle: -105, delay: 60 },
];
const STAR_BURST_DISTANCE = 26;

function BurstStar({ angle, delay, trigger }: { angle: number; delay: number; trigger: number }) {
  const progress = useSharedValue(0);

  useEffect(() => {
    if (trigger === 0) return;
    progress.value = 0;
    progress.value = withDelay(delay, withTiming(1, { duration: 550, easing: Easing.out(Easing.cubic) }));
  }, [trigger, delay, progress]);

  const style = useAnimatedStyle(() => {
    const radians = (angle * Math.PI) / 180;
    const distance = progress.value * STAR_BURST_DISTANCE;
    return {
      opacity: interpolate(progress.value, [0, 0.15, 0.75, 1], [0, 1, 1, 0]),
      transform: [
        { translateX: Math.cos(radians) * distance },
        { translateY: Math.sin(radians) * distance },
        { scale: interpolate(progress.value, [0, 0.25, 1], [0.3, 1, 0.5]) },
      ],
    };
  });

  return (
    <Animated.View pointerEvents="none" style={[{ position: 'absolute', left: 0, top: 0 }, style]}>
      <Ionicons name="star" size={11} color="#d99a3f" />
    </Animated.View>
  );
}

function LikeBurst({ trigger }: { trigger: number }) {
  return (
    <View pointerEvents="none" style={{ position: 'absolute', left: 22, top: 22 }}>
      {STAR_BURST_CONFIG.map((particle, index) => (
        <BurstStar key={index} angle={particle.angle} delay={particle.delay} trigger={trigger} />
      ))}
    </View>
  );
}

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
  {
    id: '3',
    name: 'Sofi Cerámica',
    role: 'Ceramista',
    initial: 'S',
    color: 'mostaza' as const,
    time: 'hace 8 h',
    place: 'Córdoba',
    image: 'https://picsum.photos/seed/sofi-ceramica/800/900',
    caption: 'Nueva tanda saliendo del horno, todavía tibia.',
    likes: '2.1k',
    comments: 47,
    shares: 15,
    acceptsCommissions: true,
  },
  {
    id: '4',
    name: 'Taller Norte',
    role: 'Artesanos',
    initial: 'T',
    color: 'taupe' as const,
    time: 'hace 12 h',
    place: 'Mendoza',
    image: 'https://picsum.photos/seed/taller-norte/800/900',
    caption: 'Trabajando el cuero para el pedido de esta semana.',
    likes: '390',
    comments: 6,
    shares: 2,
    acceptsCommissions: false,
  },
  {
    id: '5',
    name: 'Vale Grabados',
    role: 'Grabadora',
    initial: 'V',
    color: 'terracota' as const,
    time: 'hace 1 d',
    place: 'La Plata',
    image: 'https://picsum.photos/seed/vale-grabados/800/900',
    caption: 'Primera tirada de la serie nueva, tinta todavía fresca.',
    likes: '1.7k',
    comments: 31,
    shares: 9,
    acceptsCommissions: true,
  },
  {
    id: '6',
    name: 'Nico Escultor',
    role: 'Escultor',
    initial: 'N',
    color: 'verde' as const,
    time: 'hace 1 d',
    place: 'Buenos Aires',
    image: 'https://picsum.photos/seed/nico-escultor/800/900',
    caption: 'Piedra bruta convirtiéndose en algo con forma, de a poco.',
    likes: '654',
    comments: 18,
    shares: 4,
    acceptsCommissions: false,
  },
];

type Post = (typeof POSTS)[number];

function PostCard({ post }: { post: Post }) {
  const tilt = useNoteTilt();
  const [liked, setLiked] = useState(false);
  const [burstTrigger, setBurstTrigger] = useState(0);
  const starScale = useSharedValue(1);

  const handleLikePress = () => {
    setLiked((wasLiked) => {
      const nowLiked = !wasLiked;
      if (nowLiked) {
        setBurstTrigger((count) => count + 1);
        starScale.value = withSequence(
          withTiming(1.35, { duration: 120, easing: Easing.out(Easing.quad) }),
          withTiming(1, { duration: 180, easing: Easing.out(Easing.quad) }),
        );
      }
      return nowLiked;
    });
  };

  const starStyle = useAnimatedStyle(() => ({
    transform: [{ scale: starScale.value }],
  }));

  return (
    <View
      style={[{ transform: [{ rotate: `${tilt.note}deg` }] }, NOTE_SHADOW]}
      className="rounded-xl">
      <WashiTape color={ROLE_BADGE_COLORS[post.color].fg} rotation={tilt.tape} />
      <View className="gap-3 rounded-xl bg-sand-50 p-4">
        <View className="flex-row items-center gap-3">
          <Avatar initial={post.initial} color={post.color} />
          <View className="flex-1">
            <View className="flex-row items-center gap-2">
              <Text className="font-semibold text-ink">{post.name}</Text>
              <View
                className="rounded-full px-2 py-0.5"
                style={{ backgroundColor: ROLE_BADGE_COLORS[post.color].bg }}>
                <Text
                  className="text-xs font-medium"
                  style={{ color: ROLE_BADGE_COLORS[post.color].fg }}>
                  {post.role}
                </Text>
              </View>
            </View>
            <Text className="text-xs text-stone-700">
              {post.time} · {post.place}
            </Text>
          </View>
          <Ionicons name="ellipsis-horizontal" size={18} color="#8b8279" />
        </View>

        <View className="relative mb-4">
          <View className="overflow-hidden rounded-2xl">
            <Image source={{ uri: post.image }} className="aspect-[4/5] w-full" />
            {post.acceptsCommissions && (
              <View
                accessible
                accessibilityLabel="Acepta comisiones"
                className="absolute right-3 top-3 h-7 w-7 items-center justify-center rounded-full bg-gold"
                style={FLOAT_SHADOW}>
                <Ionicons name="cash-outline" size={15} color="#201d1a" />
              </View>
            )}
          </View>

          <View pointerEvents="box-none" className="absolute inset-x-0 items-center" style={{ bottom: -20 }}>
            <View
              className="flex-row items-center gap-1 rounded-full bg-ink/85 px-2 py-1.5"
              style={FLOAT_SHADOW}>
              <View className="relative">
                <Pressable
                  onPress={handleLikePress}
                  accessibilityRole="button"
                  accessibilityLabel={`Me gusta, ${post.likes}`}
                  className="h-11 flex-row items-center justify-center gap-1.5 px-3">
                  <Animated.View style={starStyle}>
                    <Ionicons name={liked ? 'star' : 'star-outline'} size={20} color="#d99a3f" />
                  </Animated.View>
                  <Text className="text-xs text-sand-100">{post.likes}</Text>
                </Pressable>
                <LikeBurst trigger={burstTrigger} />
              </View>

              <View className="h-4 w-px bg-sand-50/25" />

              <Pressable
                onPress={() =>
                  router.push({
                    pathname: '/comments',
                    params: { authorName: post.name, commentsCount: String(post.comments) },
                  })
                }
                accessibilityRole="button"
                accessibilityLabel={`Comentarios, ${post.comments}`}
                className="h-11 flex-row items-center justify-center gap-1.5 px-3">
                <Ionicons name="chatbubble-outline" size={19} color="#fdf8f3" />
                <Text className="text-xs text-sand-100">{post.comments}</Text>
              </Pressable>

              <View className="h-4 w-px bg-sand-50/25" />

              <Pressable
                onPress={() =>
                  router.push({ pathname: '/share', params: { authorName: post.name } })
                }
                accessibilityRole="button"
                accessibilityLabel={`Compartir, ${post.shares}`}
                className="h-11 flex-row items-center justify-center gap-1.5 px-3">
                <Ionicons name="paper-plane-outline" size={19} color="#fdf8f3" />
                <Text className="text-xs text-sand-100">{post.shares}</Text>
              </Pressable>

              <View className="h-4 w-px bg-sand-50/25" />

              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Etiquetar"
                className="h-11 w-11 items-center justify-center">
                <Ionicons name="pricetag-outline" size={19} color="#fdf8f3" />
              </Pressable>
            </View>
          </View>
        </View>

        <Text className="font-serif text-lg italic text-ink">
          <Text style={{ color: ROLE_BADGE_COLORS[post.color].fg }}>— </Text>
          {post.caption}
        </Text>
      </View>
    </View>
  );
}

export default function InicioScreen() {
  const [tab, setTab] = useState<'seguidos' | 'para-ti'>('seguidos');
  const [isCollapsed, setIsCollapsed] = useState(false);
  const scrollY = useSharedValue(0);
  const wasCollapsed = useSharedValue(false);

  const scrollHandler = useAnimatedScrollHandler((event) => {
    const y = event.contentOffset.y;
    scrollY.value = y;

    const shouldCollapse = y > COLLAPSE_DISTANCE;
    if (shouldCollapse !== wasCollapsed.value) {
      wasCollapsed.value = shouldCollapse;
      runOnJS(setIsCollapsed)(shouldCollapse);
    }
  });

  const pillStyle = useAnimatedStyle(() => {
    const progress = Math.min(Math.max(scrollY.value / COLLAPSE_DISTANCE, 0), 1);
    return {
      opacity: 1 - progress,
      transform: [{ translateY: progress * -8 }, { scale: 1 - progress * 0.08 }],
    };
  });

  const miniToggleStyle = useAnimatedStyle(() => {
    const progress = Math.min(Math.max(scrollY.value / COLLAPSE_DISTANCE, 0), 1);
    return {
      opacity: progress,
      height: progress * MINI_TOGGLE_HEIGHT,
      marginTop: progress * 6,
      transform: [{ translateY: (1 - progress) * -6 }],
    };
  });

  return (
    <View className="flex-1 bg-sand-100">
      <AppBackground />
      <Animated.ScrollView
        onScroll={scrollHandler}
        scrollEventThrottle={16}
        contentContainerStyle={{ paddingTop: FLOATING_HEADER_HEIGHT }}
        contentContainerClassName="gap-8 px-5 pb-5"
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
          <PostCard key={post.id} post={post} />
        ))}
      </Animated.ScrollView>

      <View pointerEvents="box-none" className="absolute inset-x-0 top-0 pt-14">
        <View className="flex-row items-center justify-between px-5 pb-3">
          <View
            className="rounded-2xl bg-sand-50 px-4 py-2.5"
            style={FLOAT_SHADOW}>
            <View className="flex-row items-center gap-2">
              <Image
                source={require('@/assets/images/logo-mark.png')}
                style={{ width: 22, height: 22 }}
                resizeMode="contain"
              />
              <Text className="font-serif text-2xl italic text-ink">Artística</Text>
            </View>

            <Animated.View
              pointerEvents={isCollapsed ? 'auto' : 'none'}
              style={[{ flexDirection: 'row', gap: 8, overflow: 'hidden' }, miniToggleStyle]}>
              <Pressable
                onPress={() => setTab('seguidos')}
                className={
                  tab === 'seguidos'
                    ? 'h-7 w-7 items-center justify-center rounded-full bg-accent/15'
                    : 'h-7 w-7 items-center justify-center rounded-full bg-sand-200'
                }>
                <Ionicons
                  name="people"
                  size={15}
                  color={tab === 'seguidos' ? '#c2653b' : '#8b8279'}
                />
              </Pressable>
              <Pressable
                onPress={() => setTab('para-ti')}
                className={
                  tab === 'para-ti'
                    ? 'h-7 w-7 items-center justify-center rounded-full bg-accent/15'
                    : 'h-7 w-7 items-center justify-center rounded-full bg-sand-200'
                }>
                <Ionicons
                  name="sparkles"
                  size={15}
                  color={tab === 'para-ti' ? '#c2653b' : '#8b8279'}
                />
              </Pressable>
            </Animated.View>
          </View>
          <Pressable
            className="h-11 w-11 items-center justify-center rounded-full bg-sand-50"
            style={FLOAT_SHADOW}>
            <Ionicons name="notifications-outline" size={20} color="#201d1a" />
          </Pressable>
        </View>

        <Animated.View
          pointerEvents={isCollapsed ? 'none' : 'auto'}
          className="mx-5 flex-row rounded-full bg-sand-200 p-1"
          style={[FLOAT_SHADOW, pillStyle]}>
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
        </Animated.View>
      </View>
    </View>
  );
}
