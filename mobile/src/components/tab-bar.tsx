import { Ionicons } from '@expo/vector-icons';
import { LiquidGlassView } from '@sbaiahmed1/react-native-blur';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import type { BottomTabBarProps } from 'expo-router/tabs';
import { Pressable, Text, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

const TAB_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  home: 'home-outline',
  explore: 'compass-outline',
  messages: 'chatbubbles-outline',
  profile: 'person-outline',
};

const TAB_LABELS: Record<string, string> = {
  home: 'INICIO',
  explore: 'EXPLORAR',
  messages: 'MENSAJES',
  profile: 'PERFIL',
};

const ACCENT = '#a1512d';
const INACTIVE = '#574e46';
const PILL_HEIGHT = 62;
const PILL_MARGIN_BOTTOM = 14;
const SIDE_MARGIN = 16;
const CENTER_GAP = 92;
const FAB_SIZE = 58;
// Reserved height for the whole bar: the pill's own footprint from the
// bottom, plus room for the FAB to poke above the pills.
const BAR_HEIGHT = PILL_MARGIN_BOTTOM + PILL_HEIGHT + FAB_SIZE / 2;

type Route = BottomTabBarProps['state']['routes'][number];

export function TabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const totalHeight = BAR_HEIGHT + insets.bottom;
  const pillWidth = (width - SIDE_MARGIN * 2 - CENTER_GAP) / 2;

  const renderTab = (route: Route, index: number) => {
    const isFocused = state.index === index;
    const color = isFocused ? ACCENT : INACTIVE;
    const label = TAB_LABELS[route.name] ?? route.name.toUpperCase();

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
        style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4 }}>
        <Ionicons name={TAB_ICONS[route.name] ?? 'ellipse-outline'} size={22} color={color} />
        <Text
          style={{
            fontSize: 9,
            letterSpacing: 9 * 0.06,
            fontWeight: isFocused ? '700' : '600',
            color,
          }}>
          {label}
        </Text>
      </Pressable>
    );
  };

  const leftRoutes = state.routes.slice(0, 2);
  const rightRoutes = state.routes.slice(2);

  const pillStyle = {
    position: 'absolute' as const,
    bottom: PILL_MARGIN_BOTTOM + insets.bottom,
    height: PILL_HEIGHT,
    width: pillWidth,
    borderRadius: PILL_HEIGHT / 2,
    overflow: 'hidden' as const,
    shadowColor: '#3d362f',
    shadowOpacity: 0.16,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
    elevation: 12,
  };

  return (
    <View style={{ height: totalHeight }}>
      <LiquidGlassView
        glassType="regular"
        glassTintColor="#fdf8f3"
        glassOpacity={0.55}
        style={{ ...pillStyle, left: SIDE_MARGIN, flexDirection: 'row' }}>
        {leftRoutes.map((route, index) => renderTab(route, index))}
      </LiquidGlassView>

      <LiquidGlassView
        glassType="regular"
        glassTintColor="#fdf8f3"
        glassOpacity={0.55}
        style={{ ...pillStyle, right: SIDE_MARGIN, flexDirection: 'row' }}>
        {rightRoutes.map((route, index) => renderTab(route, index + leftRoutes.length))}
      </LiquidGlassView>

      <Pressable
        onPress={() => router.push('/create')}
        accessibilityRole="button"
        accessibilityLabel="Crear obra"
        style={{
          position: 'absolute',
          width: FAB_SIZE,
          height: FAB_SIZE,
          borderRadius: FAB_SIZE / 2,
          left: width / 2 - FAB_SIZE / 2,
          bottom: PILL_MARGIN_BOTTOM + insets.bottom + PILL_HEIGHT - FAB_SIZE / 2,
          overflow: 'hidden',
          shadowColor: '#c2653b',
          shadowOpacity: 0.55,
          shadowRadius: 15,
          shadowOffset: { width: 0, height: 8 },
          elevation: 10,
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
        <View
          pointerEvents="none"
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            height: FAB_SIZE / 2.6,
            borderBottomLeftRadius: FAB_SIZE / 2,
            borderBottomRightRadius: FAB_SIZE / 2,
            backgroundColor: 'rgba(90,40,18,0.35)',
          }}
        />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="add-outline" size={26} color="#fdf8f3" />
        </View>
      </Pressable>
    </View>
  );
}
