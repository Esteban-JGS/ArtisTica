import { Image } from 'expo-image';
import { useWindowDimensions, View } from 'react-native';
import Animated, {
  type SharedValue,
  useAnimatedScrollHandler,
  useAnimatedStyle,
  useSharedValue,
} from 'react-native-reanimated';

// Textura CC0 de ambientCG (ambientcg.com/a/Cork001), recoloreada a un
// tono de corcho natural a partir de su luminancia, con el grano
// acentuado. No se tine con el color de marca: el terracota tiene que
// resaltar sobre el tablero, no confundirse con el.
// Es local porque tiene que repetirse sin costura.
const CORK_TEXTURE = require('@/assets/images/texture-cork.avif');

// Alto de cada copia apilada de la textura de corcho. Entre mas grande,
// mas realista se ve el grano (menos "estampado de papel tapiz").
const CORK_TILE_HEIGHT = 480;

function wrap(value: number, max: number) {
  'worklet';
  return ((value % max) + max) % max;
}

// La textura se repite sin costura, asi que se anima: apila copias
// identicas y las corre con el scroll, envolviendo cada CORK_TILE_HEIGHT
// px. Como las copias son identicas, el salto del envolvido es invisible
// y el loop queda infinito. Con scrollY se mueve 1:1 con el contenido;
// sin el (pantallas sin scroll propio) queda fija.
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
            source={CORK_TEXTURE}
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
          backgroundColor: 'rgba(247,245,241,0.08)',
        }}
      />
    </View>
  );
}

// El tablero de corcho detras de toda la app, apenas aclarado. El texto
// nunca va directo sobre el: siempre sobre papel o vidrio.
export function AppBackground({ scrollY }: { scrollY?: SharedValue<number> }) {
  return <ScrollingCorkBackground scrollY={scrollY} />;
}

// Conecta el scroll de una pantalla con el corcho: onScroll va a un
// Animated.ScrollView (con scrollEventThrottle={16}) y scrollY a
// AppBackground. Corre en el hilo de UI, asi que el fondo no se atrasa.
export function useCorkScroll() {
  const scrollY = useSharedValue(0);
  const onScroll = useAnimatedScrollHandler((event) => {
    scrollY.value = event.contentOffset.y;
  });
  return { scrollY, onScroll };
}
