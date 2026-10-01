/* eslint-disable react-hooks/immutability -- Reanimated shared values (.value) are mutable refs by design, not React-compiler-managed state; this screen mutates several of them from gesture/timing callbacks. */
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';
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

import { colors } from '@/theme';

const BUDGETS = ['Menos de 50k', '50k a 150k', 'Más de 150k'];

export default function SolicitarComisionScreen() {
  const { artistName } = useLocalSearchParams<{ artistName?: string }>();
  const { height: windowHeight } = useWindowDimensions();
  const sheetHeight = Math.round(windowHeight * 0.65);

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

  const [idea, setIdea] = useState('');
  const [budget, setBudget] = useState(BUDGETS[0]);
  const [sent, setSent] = useState(false);

  const handleSend = () => {
    if (!idea.trim()) return;
    // Sin backend todavia: solo confirma en pantalla. Cuando exista la
    // consulta real, esto manda idea + presupuesto a la API y crea el
    // pedido en estado "consulta".
    setSent(true);
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
        style={[{ height: sheetHeight }, sheetStyle]}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={{ flex: 1 }}>
          <SafeAreaView edges={['bottom']} className="flex-1">
            <GestureDetector gesture={dragGesture}>
              <View className="items-center py-3">
                <View className="h-1 w-10 rounded-full bg-sand-300" />
              </View>
            </GestureDetector>

            <View className="flex-row items-center justify-between border-b border-sand-300 px-5 py-3">
              <Text className="text-base font-semibold text-ink">
                {artistName ? `Solicitar comisión a ${artistName}` : 'Solicitar comisión'}
              </Text>
              <Pressable onPress={handleClose}>
                <Ionicons name="close" size={22} color={colors.ink.DEFAULT} />
              </Pressable>
            </View>

            {sent ? (
              <View className="flex-1 items-center justify-center gap-3 px-8">
                <Ionicons name="checkmark-circle" size={48} color={colors.accent.DEFAULT} />
                <Text className="text-center text-base font-semibold text-ink">
                  Listo, le avisamos a {artistName ?? 'el artista'}
                </Text>
                <Text className="text-center text-sm text-stone-700">
                  Te va a responder por el chat de esta consulta.
                </Text>
                <Pressable onPress={handleClose} className="mt-2 rounded-full bg-accent px-6 py-3">
                  <Text className="text-sm font-semibold text-sand-50">Listo</Text>
                </Pressable>
              </View>
            ) : (
              <View className="flex-1 gap-5 px-5 py-4">
                <View className="gap-2">
                  <Text className="text-xs font-semibold uppercase text-stone-700">Contame tu idea</Text>
                  <TextInput
                    value={idea}
                    onChangeText={setIdea}
                    placeholder="Describí lo que tenés en mente, referencias, tamaño…"
                    placeholderTextColor={colors.stone[700]}
                    multiline
                    numberOfLines={4}
                    className="rounded-2xl bg-sand-100 px-4 py-3 text-sm text-ink"
                    style={{ minHeight: 100, textAlignVertical: 'top' }}
                  />
                </View>

                <View className="gap-2">
                  <Text className="text-xs font-semibold uppercase text-stone-700">Presupuesto aproximado</Text>
                  <View className="flex-row flex-wrap gap-2">
                    {BUDGETS.map((item) => (
                      <Pressable
                        key={item}
                        onPress={() => setBudget(item)}
                        className={
                          item === budget
                            ? 'rounded-full bg-accent px-4 py-2'
                            : 'rounded-full bg-sand-100 px-4 py-2'
                        }>
                        <Text className={item === budget ? 'text-sm font-semibold text-sand-50' : 'text-sm text-ink'}>
                          {item}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                </View>

                <Pressable
                  onPress={handleSend}
                  disabled={!idea.trim()}
                  className={idea.trim() ? 'items-center rounded-full bg-accent py-3' : 'items-center rounded-full bg-accent/40 py-3'}>
                  <Text className="text-sm font-semibold text-sand-50">Enviar consulta</Text>
                </Pressable>
              </View>
            )}
          </SafeAreaView>
        </KeyboardAvoidingView>
      </Animated.View>
    </View>
  );
}
