import { LiquidGlassView } from '@sbaiahmed1/react-native-blur';
import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { Extrapolation, interpolate, type SharedValue, useAnimatedStyle } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '@/theme';

export const GLASS_HEADER_HEIGHT = 52;
// Cuanto hay que bajar para que el vidrio quede del todo opaco.
const FADE_DISTANCE = 24;

// Espacio que el contenido tiene que dejar arriba para arrancar debajo
// del encabezado.
export function useGlassHeaderOffset() {
  const { top } = useSafeAreaInsets();
  return top + GLASS_HEADER_HEIGHT;
}

// Encabezado que flota sobre el contenido. Arriba de todo es
// transparente y deja ver el corcho; al bajar aparece un vidrio y el
// contenido pasa por debajo difuminado, en vez de cortarse en seco.
export function GlassHeader({ scrollY, children }: { scrollY: SharedValue<number>; children: ReactNode }) {
  const { top } = useSafeAreaInsets();

  const backdropStyle = useAnimatedStyle(() => ({
    opacity: interpolate(scrollY.value, [0, FADE_DISTANCE], [0, 1], Extrapolation.CLAMP),
  }));

  return (
    <View pointerEvents="box-none" style={{ position: 'absolute', top: 0, left: 0, right: 0 }}>
      <Animated.View
        pointerEvents="none"
        style={[
          StyleSheet.absoluteFill,
          { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: 'rgba(32,29,26,0.18)' },
          backdropStyle,
        ]}>
        <LiquidGlassView
          glassType="clear"
          glassTintColor={colors.sand[50]}
          glassOpacity={0.85}
          isInteractive={false}
          style={StyleSheet.absoluteFill}
        />
      </Animated.View>
      <View
        className="flex-row items-center justify-between px-5"
        style={{ paddingTop: top, height: top + GLASS_HEADER_HEIGHT }}>
        {children}
      </View>
    </View>
  );
}
