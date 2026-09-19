import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import type { BottomTabBarProps } from 'expo-router/tabs';
import { Pressable, Text, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Defs, LinearGradient as SvgLinearGradient, Path, Stop } from 'react-native-svg';

import { buildLiquidBarPaths } from '@/components/notch-path';

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
const BAR_HEIGHT = 104;
const CORNER_RADIUS = 28;
const CURVE_AREA_HEIGHT = 40;
const FAB_SIZE = 58;

type Route = BottomTabBarProps['state']['routes'][number];

export function TabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const totalHeight = BAR_HEIGHT + insets.bottom;
  const { edgePath, materialPath } = buildLiquidBarPaths(width, totalHeight);

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
        style={{ flex: 1, alignItems: 'center', gap: 6 }}>
        <Ionicons name={TAB_ICONS[route.name] ?? 'ellipse-outline'} size={23} color={color} />
        <Text
          style={{
            fontSize: 9.5,
            letterSpacing: 9.5 * 0.06,
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

  return (
    <View style={{ height: totalHeight }}>
      <View
        pointerEvents="none"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          shadowColor: '#3d362f',
          shadowOpacity: 0.18,
          shadowRadius: 18,
          shadowOffset: { width: 0, height: -6 },
          elevation: 24,
        }}>
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
          {/* A plain SVG fill, not a blurred/masked native view: it renders
              identically everywhere and the notch is a real gap because
              nothing is painted there — no experimental Android APIs. */}
          <Svg width={width} height={totalHeight} style={{ position: 'absolute', top: 0, left: 0 }}>
            <Defs>
              <SvgLinearGradient id="materialFill" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor="#fffdfa" stopOpacity={0.96} />
                <Stop offset="0.46" stopColor="#fdf8f3" stopOpacity={0.86} />
                <Stop offset="1" stopColor="#fdf8f3" stopOpacity={0.97} />
              </SvgLinearGradient>
            </Defs>
            <Path d={materialPath} fill="url(#materialFill)" />
          </Svg>
        </View>
      </View>

      <Svg
        width={width}
        height={CURVE_AREA_HEIGHT}
        style={{ position: 'absolute', top: 0, left: 0 }}
        pointerEvents="none">
        <Defs>
          <SvgLinearGradient id="edgeBright" x1="0" y1="0" x2="1" y2="0">
            <Stop offset="0" stopColor="#ffffff" stopOpacity={0} />
            <Stop offset="0.14" stopColor="#ffffff" stopOpacity={0.95} />
            <Stop offset="0.86" stopColor="#ffffff" stopOpacity={0.95} />
            <Stop offset="1" stopColor="#ffffff" stopOpacity={0} />
          </SvgLinearGradient>
          <SvgLinearGradient id="edgeDim" x1="0" y1="0" x2="1" y2="0">
            <Stop offset="0" stopColor="#96785f" stopOpacity={0} />
            <Stop offset="0.14" stopColor="#96785f" stopOpacity={0.16} />
            <Stop offset="0.86" stopColor="#96785f" stopOpacity={0.16} />
            <Stop offset="1" stopColor="#96785f" stopOpacity={0} />
          </SvgLinearGradient>
        </Defs>
        <Path
          d={edgePath}
          stroke="url(#edgeDim)"
          strokeWidth={1}
          fill="none"
          transform="translate(0, 1.6)"
        />
        <Path d={edgePath} stroke="url(#edgeBright)" strokeWidth={1.6} fill="none" />
      </Svg>

      <View
        pointerEvents="box-none"
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 0,
          height: BAR_HEIGHT,
          flexDirection: 'row',
          alignItems: 'flex-start',
          paddingTop: 40,
          paddingHorizontal: 12,
        }}>
        {leftRoutes.map((route, index) => renderTab(route, index))}
        <View style={{ flex: 1 }} />
        {rightRoutes.map((route, index) => renderTab(route, index + leftRoutes.length))}
      </View>

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
          bottom: 54,
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
