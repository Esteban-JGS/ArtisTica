import { Ionicons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { router } from 'expo-router';
import type { BottomTabBarProps } from 'expo-router/tabs';
import { Platform, Pressable, Text, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';

import { buildNotchCutoutPath } from '@/components/notch-path';

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
const INACTIVE = '#8b8279';
const PAGE_BG = '#f7f5f1';
const BAR_HEIGHT = 64;
const CORNER_RADIUS = 28;
const NOTCH_RADIUS = 38;
const NOTCH_WIDTH = 104;
const FAB_SIZE = 60;

export function TabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const totalHeight = BAR_HEIGHT + insets.bottom;

  const cutoutPath = buildNotchCutoutPath({
    width,
    notchRadius: NOTCH_RADIUS,
    notchWidth: NOTCH_WIDTH,
  });

  return (
    <View style={{ height: totalHeight }}>
      <View
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          borderTopLeftRadius: CORNER_RADIUS,
          borderTopRightRadius: CORNER_RADIUS,
          overflow: 'hidden',
        }}>
        <BlurView
          intensity={45}
          tint="light"
          style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
        />
        <View
          pointerEvents="none"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(253,248,243,0.45)',
          }}
        />
      </View>
      <Svg
        width={width}
        height={NOTCH_RADIUS}
        style={{ position: 'absolute', top: 0, left: 0 }}>
        <Path d={cutoutPath} fill={PAGE_BG} />
      </Svg>

      <View
        pointerEvents="box-none"
        className="absolute inset-x-0 top-0 flex-row items-center justify-between px-6 pt-4"
        style={{ height: BAR_HEIGHT }}>
        {state.routes.map((route, index) => {
          const isFocused = state.index === index;
          const color = isFocused ? ACCENT : INACTIVE;
          const label = TAB_LABELS[route.name] ?? route.name;

          const onPress = () => {
            const event = navigation.emit({
              type: 'tabPress',
              target: route.key,
              canPreventDefault: true,
            });
            if (!isFocused && !event.defaultPrevented) {
              navigation.navigate(route.name);
            }
          };

          return (
            <Pressable
              key={route.key}
              onPress={onPress}
              accessibilityRole="tab"
              accessibilityState={{ selected: isFocused }}
              accessibilityLabel={label}
              android_ripple={{ color: '#e2ddd5', borderless: true }}
              className="flex-1 items-center gap-1">
              <Ionicons name={TAB_ICONS[route.name] ?? 'ellipse'} size={22} color={color} />
              <Text
                style={{ color }}
                className={isFocused ? 'text-xs font-semibold' : 'text-xs font-medium'}>
                {label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <Pressable
        onPress={() => router.push('/create')}
        accessibilityRole="button"
        accessibilityLabel="Crear obra"
        android_ripple={{ color: '#a1512d', borderless: true }}
        className="absolute items-center justify-center rounded-full bg-accent active:bg-accent-dark"
        style={{
          width: FAB_SIZE,
          height: FAB_SIZE,
          borderRadius: FAB_SIZE / 2,
          left: width / 2 - FAB_SIZE / 2,
          top: -FAB_SIZE / 2 + 6,
          ...Platform.select({
            android: { elevation: 6 },
            default: {
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 4 },
              shadowOpacity: 0.25,
              shadowRadius: 6,
            },
          }),
        }}>
        <Ionicons name="color-palette" size={24} color="#fdf8f3" />
      </Pressable>
    </View>
  );
}
