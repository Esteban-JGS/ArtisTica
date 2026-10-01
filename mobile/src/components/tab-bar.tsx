/* eslint-disable react-hooks/immutability -- this React-Compiler-oriented rule doesn't understand Reanimated's mutable shared values, which are intentionally mutated from gesture worklets below (and passed as props to share them between components). This project doesn't run the React Compiler, so the rule's assumption doesn't apply. */
import { Ionicons } from '@expo/vector-icons';
import { LiquidGlassView } from '@sbaiahmed1/react-native-blur';
import { router } from 'expo-router';
import type { BottomTabBarProps } from 'expo-router/tabs';
import { useEffect } from 'react';
import { Pressable, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { navBarVisibility } from '@/lib/nav-visibility';
import { colors, PILL_SHADOW } from '@/theme';
import Animated, {
  Easing,
  interpolate,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
  type SharedValue,
} from 'react-native-reanimated';

const TAB_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  home: 'home',
  explore: 'compass',
  messages: 'chatbubbles',
  profile: 'person',
};

const TAB_LABELS: Record<string, string> = {
  home: 'Inicio',
  explore: 'Explorar',
  messages: 'Mensajes',
  profile: 'Perfil',
};

// Flip to try the real glass effect again. On devices without native
// Liquid Glass (iOS < 26, Android < 13) it falls back to a BlurView
// that recomputes every frame and visibly chugs, especially with the
// feed scrolling behind it — that's why it's off by default.
const USE_LIQUID_GLASS = true;

const ACCENT = colors.accent.DEFAULT;
const INK = colors.ink.DEFAULT;
const CREAM = colors.sand[50];
const ITEM_SIZE = 56;
const ITEM_GAP = 10;
const PILL_PADDING = 8;
const BOTTOM_MARGIN = 20;
const PLUS_SIZE = 44;
const PLUS_REST_TOP = -60;

// How long you need to hold the Home icon before the "+" pops up, and
// how far you then need to drag it upward to arm it for release.
const HOLD_DELAY = 300;
const DRAG_TRIGGER = 46;

type Route = BottomTabBarProps['state']['routes'][number];

function HomeTabButton({
  isActive,
  onNavigate,
  holding,
  armed,
  dragY,
}: {
  isActive: boolean;
  onNavigate: () => void;
  holding: SharedValue<number>;
  armed: SharedValue<boolean>;
  dragY: SharedValue<number>;
}) {
  const resetPlus = () => {
    'worklet';
    armed.value = false;
    holding.value = withTiming(0, { duration: 150 });
    dragY.value = withTiming(0, { duration: 150 });
  };

  const openCreate = () => {
    resetPlus();
    router.push('/create');
  };

  // A plain quick tap navigates home. `activateAfterLongPress` is
  // gesture-handler's built-in primitive for "hold, then drag" — a
  // single Pan that only starts tracking movement once you've held it
  // past HOLD_DELAY, so there's no separate LongPress/Pan pair that can
  // cancel each other out once you start dragging.
  const tap = Gesture.Tap()
    .maxDuration(HOLD_DELAY)
    .onEnd((_event, success) => {
      if (success) runOnJS(onNavigate)();
    });

  const holdAndDrag = Gesture.Pan()
    .activateAfterLongPress(HOLD_DELAY)
    .onStart(() => {
      holding.value = withTiming(1, { duration: 180, easing: Easing.out(Easing.cubic) });
    })
    .onUpdate((event) => {
      const next = Math.min(0, event.translationY);
      dragY.value = next;
      armed.value = next < -DRAG_TRIGGER;
    })
    .onEnd(() => {
      if (armed.value) {
        runOnJS(openCreate)();
      } else {
        resetPlus();
      }
    });

  const gesture = Gesture.Race(tap, holdAndDrag);

  const iconStyle = useAnimatedStyle(() => ({
    transform: [{ scale: interpolate(holding.value, [0, 1], [1, 0.9]) }],
  }));

  return (
    <GestureDetector gesture={gesture}>
      <Animated.View
        style={[
          {
            width: ITEM_SIZE,
            height: ITEM_SIZE,
            alignItems: 'center',
            justifyContent: 'center',
          },
          iconStyle,
        ]}>
        <Ionicons name="home" size={26} color={isActive ? CREAM : INK} />
      </Animated.View>
    </GestureDetector>
  );
}

export function TabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const holding = useSharedValue(0);
  const armed = useSharedValue(false);
  const dragY = useSharedValue(0);

  const goTo = (route: Route) => {
    const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
    if (state.routes[state.index].key !== route.key && !event.defaultPrevented) {
      navigation.navigate(route.name);
    }
  };

  const activeRoute = state.routes[state.index];
  const bottomOffset = BOTTOM_MARGIN + insets.bottom;
  const homeIndex = state.routes.findIndex((route) => route.name === 'home');
  const plusLeft =
    PILL_PADDING + homeIndex * (ITEM_SIZE + ITEM_GAP) + ITEM_SIZE / 2 - PLUS_SIZE / 2;

  // The accent pill slides to the active tab instead of just popping
  // up on it, so switching tabs reads like moving a toggle.
  const indicatorX = useSharedValue(state.index * (ITEM_SIZE + ITEM_GAP));

  useEffect(() => {
    indicatorX.value = withSpring(state.index * (ITEM_SIZE + ITEM_GAP), {
      damping: 28,
      stiffness: 220,
    });

    // Only the Home feed drives navBarVisibility (it's a module-level
    // value shared across screens). Force it back on when leaving Home
    // so it can't get stuck hidden on a tab with no scroll handler for it.
    if (activeRoute.name !== 'home') {
      navBarVisibility.value = withTiming(1, { duration: 200 });
    }
  }, [state.index, indicatorX, activeRoute.name]);

  const indicatorStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: indicatorX.value }],
  }));

  const plusStyle = useAnimatedStyle(() => ({
    opacity: holding.value,
    transform: [
      { translateY: interpolate(holding.value, [0, 1], [-PLUS_REST_TOP, 0]) + dragY.value * 0.4 },
      { scale: interpolate(holding.value, [0, 1], [0.6, armed.value ? 1.18 : 1]) },
    ],
  }));

  // Hides the whole navbar by sliding it down and fading it out when
  // the feed scrolls down, driven from home.tsx via the shared value.
  const visibilityStyle = useAnimatedStyle(() => ({
    opacity: navBarVisibility.value,
    transform: [{ translateY: interpolate(navBarVisibility.value, [0, 1], [90, 0]) }],
  }));

  const pillStyle = {
    borderRadius: 32,
    overflow: 'hidden' as const,
    flexDirection: 'row' as const,
    gap: ITEM_GAP,
    padding: PILL_PADDING,
  };

  const pillContent = (
    <>
      <Animated.View
        pointerEvents="none"
        style={[
          {
            position: 'absolute',
            left: PILL_PADDING,
            top: PILL_PADDING,
            width: ITEM_SIZE,
            height: ITEM_SIZE,
            borderRadius: ITEM_SIZE / 2,
            backgroundColor: ACCENT,
          },
          indicatorStyle,
        ]}
      />

      {state.routes.map((route) => {
        const isActive = route.key === activeRoute.key;

        if (route.name === 'home') {
          return (
            <HomeTabButton
              key={route.key}
              isActive={isActive}
              onNavigate={() => goTo(route)}
              holding={holding}
              armed={armed}
              dragY={dragY}
            />
          );
        }

        return (
          <Pressable
            key={route.key}
            onPress={() => goTo(route)}
            accessibilityRole="button"
            accessibilityLabel={TAB_LABELS[route.name] ?? route.name}
            style={{
              width: ITEM_SIZE,
              height: ITEM_SIZE,
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <Ionicons
              name={TAB_ICONS[route.name] ?? 'ellipse'}
              size={26}
              color={isActive ? CREAM : INK}
            />
          </Pressable>
        );
      })}
    </>
  );

  return (
    <Animated.View
      pointerEvents="box-none"
      style={[
        {
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: bottomOffset,
          alignItems: 'center',
        },
        visibilityStyle,
      ]}>
      <View style={PILL_SHADOW}>
        <Animated.View
          pointerEvents="none"
          style={[
            { position: 'absolute', left: plusLeft, top: PLUS_REST_TOP },
            plusStyle,
          ]}>
          <View
            style={{
              width: PLUS_SIZE,
              height: PLUS_SIZE,
              borderRadius: PLUS_SIZE / 2,
              backgroundColor: ACCENT,
              alignItems: 'center',
              justifyContent: 'center',
              shadowColor: ACCENT,
              shadowOpacity: 0.5,
              shadowRadius: 8,
              shadowOffset: { width: 0, height: 3 },
              elevation: 6,
            }}>
            <Ionicons name="add" size={22} color={CREAM} />
          </View>
        </Animated.View>

        {USE_LIQUID_GLASS ? (
          <LiquidGlassView
            glassType="clear"
            glassTintColor={CREAM}
            glassOpacity={0.7}
            isInteractive={false}
            style={pillStyle}>
            {pillContent}
          </LiquidGlassView>
        ) : (
          <View style={[pillStyle, { backgroundColor: 'rgba(253,248,243,0.72)' }]}>
            {pillContent}
          </View>
        )}
      </View>
    </Animated.View>
  );
}
