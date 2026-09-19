import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, Text, View } from 'react-native';

import { Avatar } from '@/components/avatar';
import { PaperTexture, RusticTexture } from '@/components/paper-texture';
import Animated, {
  runOnJS,
  useAnimatedScrollHandler,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  type SharedValue,
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

// Posts read as notes pinned to the corkboard: a little crooked, each
// one taped down at a slightly different angle.
const CARD_ROTATIONS = [-1.6, 1.3, -1, 1.8, -1.4];

const NOTE_SHADOW = {
  shadowColor: '#3d362f',
  shadowOpacity: 0.2,
  shadowRadius: 10,
  shadowOffset: { width: 0, height: 6 },
  elevation: 6,
};

// The notes are only "taped" at the top, so a quick scroll should make
// them tip forward/back in depth (rotateX), like the loose bottom edge
// lags behind the top for a beat, and settle flat once you stop.
const TILT_SPRING = { damping: 9, stiffness: 140, mass: 0.4 };
const TILT_MAX_DEG = 6;
const TILT_FACTOR = 1.4;

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
        opacity: 0.8,
        borderRadius: 2,
        transform: [{ rotate: `${rotation}deg` }],
        shadowColor: '#000',
        shadowOpacity: 0.15,
        shadowRadius: 3,
        shadowOffset: { width: 0, height: 2 },
      }}
    />
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
];

type Post = (typeof POSTS)[number];

function NoteCard({
  post,
  rotation,
  noteTilt,
}: {
  post: Post;
  rotation: number;
  noteTilt: SharedValue<number>;
}) {
  const animatedStyle = useAnimatedStyle(() => ({
    transform: [
      { perspective: 700 },
      { rotateX: `${noteTilt.value}deg` },
      { rotate: `${rotation}deg` },
    ],
  }));

  return (
    <Animated.View style={[animatedStyle, NOTE_SHADOW]} className="rounded-xl">
      <WashiTape color={ROLE_BADGE_COLORS[post.color].fg} rotation={rotation * -2.4} />
      <View className="gap-3 overflow-hidden rounded-xl bg-sand-50 p-4">
        <PaperTexture width={420} height={900} speckOpacity={0.5} />
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
    </Animated.View>
  );
}

export default function InicioScreen() {
  const [tab, setTab] = useState<'seguidos' | 'para-ti'>('seguidos');
  const [isCollapsed, setIsCollapsed] = useState(false);
  const scrollY = useSharedValue(0);
  const wasCollapsed = useSharedValue(false);
  const previousScrollY = useSharedValue(0);
  const noteTilt = useSharedValue(0);

  const scrollHandler = useAnimatedScrollHandler({
    onScroll: (event) => {
      const y = event.contentOffset.y;
      scrollY.value = y;

      const delta = y - previousScrollY.value;
      previousScrollY.value = y;
      const target = Math.min(Math.max(delta * TILT_FACTOR, -TILT_MAX_DEG), TILT_MAX_DEG);
      noteTilt.value = withSpring(target, TILT_SPRING);

      const shouldCollapse = y > COLLAPSE_DISTANCE;
      if (shouldCollapse !== wasCollapsed.value) {
        wasCollapsed.value = shouldCollapse;
        runOnJS(setIsCollapsed)(shouldCollapse);
      }
    },
    onEndDrag: () => {
      noteTilt.value = withSpring(0, TILT_SPRING);
    },
    onMomentumEnd: () => {
      noteTilt.value = withSpring(0, TILT_SPRING);
    },
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
      <RusticTexture />
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

        {POSTS.map((post, index) => (
          <NoteCard
            key={post.id}
            post={post}
            rotation={CARD_ROTATIONS[index % CARD_ROTATIONS.length]}
            noteTilt={noteTilt}
          />
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
