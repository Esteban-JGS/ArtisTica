/* eslint-disable react-hooks/immutability -- Reanimated shared values (.value) are mutable refs by design, not React-compiler-managed state; this screen mutates several of them from gesture/timing callbacks. */
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect } from 'react';
import { Alert, Pressable, Text, useWindowDimensions, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  Easing,
  interpolate,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { usePostsStore } from '@/stores/posts-store';
import { colors } from '@/theme';

export default function OpcionesPublicacionScreen() {
  const { postId, authorName } = useLocalSearchParams<{ postId: string; authorName?: string }>();
  const hidePost = usePostsStore((state) => state.hidePost);
  const { height: windowHeight } = useWindowDimensions();
  const sheetHeight = Math.round(windowHeight * 0.35);

  const backdropOpacity = useSharedValue(0);
  const sheetTranslateY = useSharedValue(sheetHeight);

  useEffect(() => {
    backdropOpacity.value = withTiming(1, { duration: 220 });
    sheetTranslateY.value = withTiming(0, { duration: 300, easing: Easing.out(Easing.cubic) });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- shared values are stable refs, not reactive deps
  }, []);

  const handleClose = () => {
    backdropOpacity.value = withTiming(0, { duration: 160 });
    sheetTranslateY.value = withTiming(
      sheetHeight,
      { duration: 220, easing: Easing.in(Easing.cubic) },
      (finished) => {
        if (finished) runOnJS(router.back)();
      },
    );
  };

  const backdropStyle = useAnimatedStyle(() => ({ opacity: backdropOpacity.value }));
  const sheetStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: sheetTranslateY.value }],
  }));

  const dragGesture = Gesture.Pan()
    .onUpdate((event) => {
      const nextY = Math.max(0, event.translationY);
      sheetTranslateY.value = nextY;
      backdropOpacity.value = interpolate(nextY, [0, sheetHeight], [1, 0], 'clamp');
    })
    .onEnd((event) => {
      const shouldDismiss = event.translationY > 36 || event.velocityY > 700;
      if (shouldDismiss) {
        runOnJS(handleClose)();
      } else {
        sheetTranslateY.value = withTiming(0, { duration: 200, easing: Easing.out(Easing.cubic) });
        backdropOpacity.value = withTiming(1, { duration: 200 });
      }
    });

  const handleHide = () => {
    hidePost(postId);
    handleClose();
  };

  const handleReport = () => {
    const message = authorName
      ? `Vamos a revisar la publicación de ${authorName}.`
      : 'Vamos a revisar esta publicación.';
    Alert.alert('Gracias', message, [{ text: 'Listo', onPress: handleClose }]);
  };

  return (
    <View style={{ flex: 1, justifyContent: 'flex-end' }}>
      <Animated.View
        pointerEvents="box-none"
        style={[{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }, backdropStyle]}>
        <Pressable className="flex-1 bg-ink/40" onPress={handleClose} />
      </Animated.View>

      <Animated.View
        className="rounded-t-3xl bg-sand-50"
        style={[{ maxHeight: sheetHeight }, sheetStyle]}>
        <SafeAreaView edges={['bottom']}>
          <GestureDetector gesture={dragGesture}>
            <View className="items-center py-3">
              <View className="h-1 w-10 rounded-full bg-sand-300" />
            </View>
          </GestureDetector>

          <View className="border-t border-sand-300 py-2">
            <Pressable onPress={handleHide} className="flex-row items-center gap-4 px-5 py-3.5">
              <View className="h-9 w-9 items-center justify-center rounded-full bg-sand-100">
                <Ionicons name="eye-off-outline" size={18} color={colors.ink[700]} />
              </View>
              <Text className="text-sm font-medium text-ink">Ocultar esta publicación</Text>
            </Pressable>

            <Pressable onPress={handleReport} className="flex-row items-center gap-4 px-5 py-3.5">
              <View className="h-9 w-9 items-center justify-center rounded-full bg-sand-100">
                <Ionicons name="flag-outline" size={18} color={colors.ink[700]} />
              </View>
              <Text className="text-sm font-medium text-ink">Reportar publicación</Text>
            </Pressable>

            <Pressable onPress={handleClose} className="flex-row items-center gap-4 px-5 py-3.5">
              <View className="h-9 w-9 items-center justify-center rounded-full bg-sand-100">
                <Ionicons name="close-outline" size={18} color={colors.ink[700]} />
              </View>
              <Text className="text-sm font-medium text-ink">Cancelar</Text>
            </Pressable>
          </View>
        </SafeAreaView>
      </Animated.View>
    </View>
  );
}
