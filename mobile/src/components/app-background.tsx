import { Image } from 'expo-image';
import { useWindowDimensions, View } from 'react-native';
import Animated, { type SharedValue, useAnimatedStyle } from 'react-native-reanimated';

import { backgroundSource, useBackgroundStore } from '@/stores/background-store';

// Alto de cada copia apilada de la textura de corcho. Entre mas grande,
// mas realista se ve el grano (menos "estampado de papel tapiz").
const CORK_TILE_HEIGHT = 480;

function wrap(value: number, max: number) {
  'worklet';
  return ((value % max) + max) % max;
}

// El corcho es la unica textura pensada para repetirse sin costura (ver
// background-store.ts), asi que es la unica que se anima: apila copias
// identicas y las corre con el scroll, envolviendo cada CORK_TILE_HEIGHT
// px. Como las copias son identicas, el salto del envolvido es invisible
// y el loop queda infinito. Con scrollY se mueve 1:1 con los posts; sin
// el (otras pantallas sin scroll propio) queda fija.
function ScrollingCorkBackground({ scrollY }: { scrollY?: SharedValue<number> }) {
  const { height: screenHeight } = useWindowDimensions();
  const tileCount = Math.ceil(screenHeight / CORK_TILE_HEIGHT) + 2;

  const stackStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: -wrap(scrollY ? scrollY.value : 0, CORK_TILE_HEIGHT) }],
  }));

  return (
    <View pointerEvents="none" style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, overflow: 'hidden' }}>
      <Animated.View style={[{ position: 'absolute', top: -CORK_TILE_HEIGHT, left: 0, right: 0 }, stackStyle]}>
        {Array.from({ length: tileCount }).map((_, index) => (
          <Image
            key={index}
            source={backgroundSource('corcho', 0)}
            style={{ width: '100%', height: CORK_TILE_HEIGHT }}
            contentFit="cover"
          />
        ))}
      </Animated.View>
      <View
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(247,245,241,0.45)',
        }}
      />
    </View>
  );
}

// Una textura detras del palette sand, haciendo de fondo de mural/taller
// (se elige en Perfil > Personalizacion). Con tinte suave del tono sand
// para que las tarjetas flotantes y el texto sigan legibles sin aplanar
// la textura en un lavado blanco.
export function AppBackground({ scrollY }: { scrollY?: SharedValue<number> }) {
  const backgroundId = useBackgroundStore((state) => state.backgroundId);

  if (backgroundId === 'corcho') {
    return <ScrollingCorkBackground scrollY={scrollY} />;
  }

  return (
    <View pointerEvents="none" style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
      <Image source={backgroundSource(backgroundId, 1200)} style={{ flex: 1 }} contentFit="cover" />
      <View
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(247,245,241,0.45)',
        }}
      />
    </View>
  );
}
