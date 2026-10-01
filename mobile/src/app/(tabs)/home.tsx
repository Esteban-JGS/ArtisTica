import { Ionicons } from '@expo/vector-icons';
import { LiquidGlassView } from '@sbaiahmed1/react-native-blur';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, Pressable, Text, View } from 'react-native';

import { AppBackground } from '@/components/app-background';
import { Avatar } from '@/components/avatar';
import { navBarVisibility } from '@/lib/nav-visibility';
import { type Post, usePostsStore } from '@/stores/posts-store';
import { colors, FLOAT_SHADOW, NOTE_SHADOW, roleColors } from '@/theme';
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

// Space reserved at the top of the scrollable content so it starts right
// below the floating title card/bell and the floating tab pill.
const FLOATING_HEADER_HEIGHT = 168;

// How far you need to scroll before the text pill collapses into the
// small icon pair under "Artística".
const COLLAPSE_DISTANCE = 40;
const MINI_TOGGLE_HEIGHT = 30;

// Posts read as notes pinned to a corkboard, held down by a single pin
// at the top instead of a tilted strip of tape.
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
      <Ionicons name="star" size={11} color={colors.gold} />
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

function openArtistProfile(post: Post) {
  router.push({
    pathname: '/artista/[id]',
    params: { id: post.name, name: post.name, role: post.role, initial: post.initial, color: post.color },
  });
}

function PostCard({ post }: { post: Post }) {
  const [liked, setLiked] = useState(false);
  const [burstTrigger, setBurstTrigger] = useState(0);
  const [captionExpanded, setCaptionExpanded] = useState(false);
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
    <View style={NOTE_SHADOW} className="rounded-xl">
      <Pin color={roleColors[post.color].fg} />
      <View className="gap-3 rounded-xl bg-sand-50 p-4">
        <View className="flex-row items-center gap-3">
          <Pressable
            onPress={() => openArtistProfile(post)}
            accessibilityRole="button"
            accessibilityLabel={`Ver perfil de ${post.name}`}
            className="flex-1 flex-row items-center gap-3">
            <Avatar initial={post.initial} color={post.color} />
            <View className="flex-1">
              <View className="flex-row items-center gap-2">
                <Text className="font-semibold text-ink">{post.name}</Text>
                <View
                  className="rounded-full px-2 py-0.5"
                  style={{ backgroundColor: roleColors[post.color].bg }}>
                  <Text
                    className="text-xs font-medium"
                    style={{ color: roleColors[post.color].fg }}>
                    {post.role}
                  </Text>
                </View>
              </View>
              <Text className="text-xs text-stone-700">
                {post.time} · {post.place}
              </Text>
            </View>
          </Pressable>
          <Pressable
            onPress={() =>
              router.push({
                pathname: '/opciones-publicacion',
                params: { postId: post.id, authorName: post.name },
              })
            }
            accessibilityRole="button"
            accessibilityLabel="Opciones de la publicación"
            hitSlop={8}>
            <Ionicons name="ellipsis-horizontal" size={18} color={colors.stone[700]} />
          </Pressable>
        </View>

        <View className="relative mb-4">
          <View className="overflow-hidden rounded-2xl">
            <Image source={{ uri: post.image }} className="aspect-[4/5] w-full" />
            {post.acceptsCommissions && (
              <Pressable
                onPress={() =>
                  router.push({
                    pathname: '/solicitar-comision',
                    params: { artistName: post.name, postImage: post.image, postCaption: post.caption },
                  })
                }
                accessibilityRole="button"
                accessibilityLabel={`Solicitar comision a ${post.name}`}
                className="absolute right-3 top-3 h-7 w-7 items-center justify-center rounded-full bg-gold"
                style={FLOAT_SHADOW}>
                <Ionicons name="cash-outline" size={15} color={colors.ink.DEFAULT} />
              </Pressable>
            )}
          </View>

          <View pointerEvents="box-none" className="absolute inset-x-0 items-center" style={{ bottom: -20 }}>
            <View
              className="flex-row items-center gap-1 rounded-full bg-ink-700/90 px-2 py-1.5"
              style={FLOAT_SHADOW}>
              <View className="relative">
                <Pressable
                  onPress={handleLikePress}
                  accessibilityRole="button"
                  accessibilityLabel={`Me gusta, ${post.likes}`}
                  className="h-11 flex-row items-center justify-center gap-1.5 px-3">
                  <Animated.View style={starStyle}>
                    <Ionicons name={liked ? 'star' : 'star-outline'} size={20} color={colors.gold} />
                  </Animated.View>
                  <Text className="text-xs text-sand-100">{post.likes}</Text>
                </Pressable>
                <LikeBurst trigger={burstTrigger} />
              </View>

              <View className="h-4 w-px bg-sand-50/25" />

              <Pressable
                onPress={() => router.push('/comments')}
                accessibilityRole="button"
                accessibilityLabel={`Comentarios, ${post.comments}`}
                className="h-11 flex-row items-center justify-center gap-1.5 px-3">
                <Ionicons name="chatbubble-outline" size={19} color={colors.sand[50]} />
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
                <Ionicons name="paper-plane-outline" size={19} color={colors.sand[50]} />
                <Text className="text-xs text-sand-100">{post.shares}</Text>
              </Pressable>

              <View className="h-4 w-px bg-sand-50/25" />

              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Etiquetar"
                className="h-11 w-11 items-center justify-center">
                <Ionicons name="pricetag-outline" size={19} color={colors.sand[50]} />
              </Pressable>
            </View>
          </View>
        </View>

        <Text
          className="font-serif text-lg italic text-ink"
          numberOfLines={captionExpanded ? undefined : 2}
          ellipsizeMode="tail">
          <Text style={{ color: roleColors[post.color].fg }}>— </Text>
          {post.caption}
        </Text>

        <Pressable onPress={() => setCaptionExpanded((value) => !value)} hitSlop={4}>
          <Text className="text-xs font-semibold text-stone-700">
            {captionExpanded ? 'Ver menos' : 'Ver más'}
          </Text>
        </Pressable>

        <Text className="text-xs font-medium" style={{ color: roleColors[post.color].fg }}>
          {post.tags.map((tag) => `#${tag}`).join('  ')}
        </Text>
      </View>
    </View>
  );
}

export default function InicioScreen() {
  const posts = usePostsStore((state) => state.posts);
  const [tab, setTab] = useState<'seguidos' | 'para-ti'>('seguidos');
  const [isCollapsed, setIsCollapsed] = useState(false);
  const scrollY = useSharedValue(0);
  const wasCollapsed = useSharedValue(false);
  const lastScrollY = useSharedValue(0);

  const scrollHandler = useAnimatedScrollHandler((event) => {
    const y = event.contentOffset.y;
    scrollY.value = y;

    const shouldCollapse = y > COLLAPSE_DISTANCE;
    if (shouldCollapse !== wasCollapsed.value) {
      wasCollapsed.value = shouldCollapse;
      runOnJS(setIsCollapsed)(shouldCollapse);
    }

    // Hide the floating navbar while scrolling down, bring it back
    // scrolling up (or once you're back near the top). The top header
    // itself no longer hides: it only collapses the pill below, so
    // there's a single animation driving it instead of this direction
    // based one fighting with the collapse.
    const delta = y - lastScrollY.value;
    if (y <= 10) {
      navBarVisibility.value = withTiming(1, { duration: 200 });
    } else if (delta > 6) {
      navBarVisibility.value = withTiming(0, { duration: 200 });
    } else if (delta < -6) {
      navBarVisibility.value = withTiming(1, { duration: 200 });
    }
    lastScrollY.value = y;
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
      <AppBackground scrollY={scrollY} />
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
            <Ionicons name="add" size={24} color={colors.accent.DEFAULT} />
          </View>
          <Text className="flex-1 text-sm font-medium text-stone-700">
            ¿Qué querés compartir hoy?
          </Text>
        </Pressable>

        {posts.map((post) => (
          <PostCard key={post.id} post={post} />
        ))}
      </Animated.ScrollView>

      <View pointerEvents="box-none" className="absolute inset-x-0 top-0 pt-14">
        <View className="flex-row items-center justify-between px-5 pb-3">
          <View style={FLOAT_SHADOW}>
            <LiquidGlassView
              glassType="clear"
              glassTintColor={colors.sand[50]}
              glassOpacity={0.7}
              isInteractive={false}
              style={{ borderRadius: 16, paddingHorizontal: 16, paddingVertical: 10 }}>
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
                    color={tab === 'seguidos' ? colors.accent.DEFAULT : colors.stone[700]}
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
                    color={tab === 'para-ti' ? colors.accent.DEFAULT : colors.stone[700]}
                  />
                </Pressable>
              </Animated.View>
            </LiquidGlassView>
          </View>

          <View style={FLOAT_SHADOW}>
            <Pressable
              onPress={() => router.push({ pathname: '/messages', params: { tab: 'notificaciones' } })}
              accessibilityRole="button"
              accessibilityLabel="Notificaciones">
              <LiquidGlassView
                glassType="clear"
                glassTintColor={colors.sand[50]}
                glassOpacity={0.7}
                isInteractive={false}
                style={{
                  height: 44,
                  width: 44,
                  borderRadius: 22,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                <Ionicons name="notifications-outline" size={20} color={colors.ink.DEFAULT} />
              </LiquidGlassView>
            </Pressable>
          </View>
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
