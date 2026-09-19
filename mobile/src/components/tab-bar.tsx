import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import type { BottomTabBarProps } from 'expo-router/tabs';
import { useEffect, useState } from 'react';
import { Pressable, Text, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, {
  Easing,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
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

const ACCENT = '#c2653b';
const FAB_SIZE = 60;
const ITEM_HEIGHT = 46;
const ITEM_GAP = 10;
const STACK_BOTTOM_MARGIN = 20;

type Route = BottomTabBarProps['state']['routes'][number];

type MenuItem = {
  key: string;
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  isActive: boolean;
  onPress: () => void;
};

function SpeedDialItem({
  item,
  index,
  progress,
}: {
  item: MenuItem;
  index: number;
  progress: SharedValue<number>;
}) {
  const offset = FAB_SIZE + ITEM_GAP + index * (ITEM_HEIGHT + ITEM_GAP);

  const animatedStyle = useAnimatedStyle(() => {
    const itemProgress = Math.min(Math.max(progress.value * 1.35 - index * 0.12, 0), 1);
    return {
      opacity: itemProgress,
      transform: [
        { translateY: interpolate(itemProgress, [0, 1], [16, -offset]) },
        { scale: interpolate(itemProgress, [0, 1], [0.7, 1]) },
      ],
    };
  });

  return (
    <Animated.View
      pointerEvents="box-none"
      style={[{ position: 'absolute', bottom: 0, alignItems: 'center', width: '100%' }, animatedStyle]}>
      <Pressable
        onPress={item.onPress}
        accessibilityRole="button"
        accessibilityLabel={item.label}
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: 8,
          backgroundColor: item.isActive ? ACCENT : '#fdf8f3',
          borderRadius: ITEM_HEIGHT / 2,
          height: ITEM_HEIGHT,
          paddingHorizontal: 18,
          shadowColor: '#3d362f',
          shadowOpacity: 0.16,
          shadowRadius: 8,
          shadowOffset: { width: 0, height: 3 },
          elevation: 6,
        }}>
        <Ionicons name={item.icon} size={18} color={item.isActive ? '#fdf8f3' : '#3d362f'} />
        <Text
          style={{
            fontSize: 14,
            fontWeight: '600',
            color: item.isActive ? '#fdf8f3' : '#3d362f',
          }}>
          {item.label}
        </Text>
      </Pressable>
    </Animated.View>
  );
}

export function TabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  const [open, setOpen] = useState(false);
  const progress = useSharedValue(0);

  useEffect(() => {
    progress.value = withTiming(open ? 1 : 0, {
      duration: 260,
      easing: Easing.out(Easing.cubic),
    });
  }, [open, progress]);

  const close = () => setOpen(false);

  const goTo = (route: Route) => {
    close();
    const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
    if (state.routes[state.index].key !== route.key && !event.defaultPrevented) {
      navigation.navigate(route.name);
    }
  };

  const activeRoute = state.routes[state.index];
  const activeIcon = TAB_ICONS[activeRoute.name] ?? 'ellipse';

  const items: MenuItem[] = [
    {
      key: 'create',
      icon: 'color-palette',
      label: 'Crear obra',
      isActive: false,
      onPress: () => {
        close();
        router.push('/create');
      },
    },
    ...state.routes.map((route) => ({
      key: route.key,
      icon: TAB_ICONS[route.name] ?? 'ellipse',
      label: TAB_LABELS[route.name] ?? route.name,
      isActive: route.key === activeRoute.key,
      onPress: () => goTo(route),
    })),
  ];

  const backdropStyle = useAnimatedStyle(() => ({
    opacity: interpolate(progress.value, [0, 1], [0, 1]),
  }));

  const fabRotation = useAnimatedStyle(() => ({
    transform: [{ rotate: `${interpolate(progress.value, [0, 1], [0, 45])}deg` }],
  }));

  const bottomOffset = STACK_BOTTOM_MARGIN + insets.bottom;

  return (
    <View
      pointerEvents="box-none"
      style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: height }}>
      {open ? (
        <Pressable
          onPress={close}
          style={{ position: 'absolute', top: -height, left: 0, right: 0, bottom: 0 }}>
          <Animated.View
            pointerEvents="none"
            style={[
              { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(32,29,26,0.4)' },
              backdropStyle,
            ]}
          />
        </Pressable>
      ) : null}

      <View
        pointerEvents="box-none"
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: bottomOffset,
          alignItems: 'center',
        }}>
        {items.map((item, index) => (
          <SpeedDialItem key={item.key} item={item} index={index} progress={progress} />
        ))}

        <Pressable
          onPress={() => setOpen((value) => !value)}
          accessibilityRole="button"
          accessibilityLabel={open ? 'Cerrar menú' : 'Abrir menú'}
          style={{
            width: FAB_SIZE,
            height: FAB_SIZE,
            borderRadius: FAB_SIZE / 2,
            overflow: 'hidden',
            shadowColor: '#c2653b',
            shadowOpacity: 0.5,
            shadowRadius: 12,
            shadowOffset: { width: 0, height: 6 },
            elevation: 8,
          }}>
          <LinearGradient
            colors={['#d4784d', '#c2653b', '#ad5730']}
            locations={[0, 0.52, 1]}
            start={{ x: 0.37, y: 0.02 }}
            end={{ x: 0.63, y: 0.98 }}
            style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
          />
          <View
            pointerEvents="none"
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: FAB_SIZE / 2,
              borderTopLeftRadius: FAB_SIZE / 2,
              borderTopRightRadius: FAB_SIZE / 2,
              backgroundColor: 'rgba(255,255,255,0.28)',
            }}
          />
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <Animated.View style={fabRotation}>
              <Ionicons name={open ? 'close' : activeIcon} size={26} color="#fdf8f3" />
            </Animated.View>
          </View>
        </Pressable>
      </View>
    </View>
  );
}
