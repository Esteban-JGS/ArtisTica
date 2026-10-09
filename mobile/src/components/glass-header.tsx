import { LiquidGlassView } from '@sbaiahmed1/react-native-blur';
import { useFocusEffect } from 'expo-router';
import { setStatusBarStyle } from 'expo-status-bar';
import { type ReactNode, useCallback } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  Extrapolation,
  interpolate,
  runOnJS,
  type SharedValue,
  useAnimatedReaction,
  useAnimatedStyle,
} from 'react-native-reanimated';
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

function applyStatusBar(scrolled: boolean) {
  setStatusBarStyle(scrolled ? 'light' : 'dark');
}

// Vidrio en tinta que aparece al bajar, igual que la barra de navegacion:
// lo que flota es oscuro y el contenido es papel. Arriba de todo es
// transparente y deja ver el corcho; con scroll se vuelve opaco y el
// contenido pasa por debajo difuminado, en vez de cortarse en seco.
// Llena a su contenedor, que tiene que flotar sobre la lista.
export function GlassBackdrop({ scrollY }: { scrollY: SharedValue<number> }) {
  const backdropStyle = useAnimatedStyle(() => ({
    opacity: interpolate(scrollY.value, [0, FADE_DISTANCE], [0, 1], Extrapolation.CLAMP),
  }));

  // Sobre el vidrio oscuro, la hora y la bateria pasan a claras.
  useAnimatedReaction(
    () => scrollY.value > FADE_DISTANCE / 2,
    (scrolled, previous) => {
      if (scrolled !== previous) runOnJS(applyStatusBar)(scrolled);
    },
  );
  useFocusEffect(
    useCallback(() => {
      applyStatusBar(scrollY.value > FADE_DISTANCE / 2);
      return () => applyStatusBar(false);
    }, [scrollY]),
  );

  return (
    <Animated.View
      pointerEvents="none"
      style={[
        StyleSheet.absoluteFill,
        { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: 'rgba(32,29,26,0.18)' },
        backdropStyle,
      ]}>
      <LiquidGlassView
        glassType="clear"
        glassTintColor={colors.ink.DEFAULT}
        glassOpacity={0.92}
        isInteractive={false}
        style={StyleSheet.absoluteFill}
      />
    </Animated.View>
  );
}

// Encabezado de una fila (volver, titulo, accion) sobre GlassBackdrop.
// Recibe el color con el que dibujar su contenido: sobre el corcho es
// tinta y pasa a crema con un fundido cuando aparece el vidrio.
export function GlassHeader({
  scrollY,
  children,
}: {
  scrollY: SharedValue<number>;
  children: (color: string) => ReactNode;
}) {
  const { top } = useSafeAreaInsets();
  const onGlassStyle = useAnimatedStyle(() => ({
    opacity: interpolate(scrollY.value, [0, FADE_DISTANCE], [0, 1], Extrapolation.CLAMP),
  }));
  const onCorkStyle = useAnimatedStyle(() => ({
    opacity: interpolate(scrollY.value, [0, FADE_DISTANCE], [1, 0], Extrapolation.CLAMP),
  }));

  const row = (color: string) => (
    <View
      pointerEvents="box-none"
      className="flex-row items-center justify-between px-5"
      style={{ paddingTop: top, height: top + GLASS_HEADER_HEIGHT }}>
      {children(color)}
    </View>
  );

  return (
    <View pointerEvents="box-none" style={{ position: 'absolute', top: 0, left: 0, right: 0 }}>
      <GlassBackdrop scrollY={scrollY} />
      <Animated.View pointerEvents="box-none" style={onCorkStyle}>
        {row(colors.ink.DEFAULT)}
      </Animated.View>
      <Animated.View pointerEvents="box-none" style={[StyleSheet.absoluteFill, onGlassStyle]}>
        {row(colors.sand[50])}
      </Animated.View>
    </View>
  );
}
