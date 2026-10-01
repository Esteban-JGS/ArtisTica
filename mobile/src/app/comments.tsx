/* eslint-disable react-hooks/immutability -- Reanimated shared values (.value) are mutable refs by design, not React-compiler-managed state; this screen mutates several of them from gesture/timing callbacks. */
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
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

import { Avatar } from '@/components/avatar';
import { colors } from '@/theme';

type CommentColor = 'terracota' | 'verde' | 'mostaza' | 'taupe';

type Reply = {
  id: string;
  name: string;
  initial: string;
  color: CommentColor;
  text: string;
  time: string;
};

type Comment = {
  id: string;
  name: string;
  initial: string;
  color: CommentColor;
  text: string;
  time: string;
  likes: number;
  replies: Reply[];
};

const INITIAL_COMMENTS: Comment[] = [
  {
    id: '1',
    name: 'Caro Diseños',
    initial: 'C',
    color: 'verde',
    text: 'Qué textura tan real, se nota el trabajo detrás.',
    time: 'hace 1 h',
    likes: 12,
    replies: [
      {
        id: '1-1',
        name: 'Vale Grabados',
        initial: 'V',
        color: 'terracota',
        text: '¡Gracias, Caro! Fue un proceso largo pero valió la pena 🙌',
        time: 'hace 50 min',
      },
    ],
  },
  {
    id: '2',
    name: 'Fede Arte',
    initial: 'F',
    color: 'mostaza',
    text: 'Me encantaría ver el proceso completo 👀',
    time: 'hace 45 min',
    likes: 4,
    replies: [],
  },
  {
    id: '3',
    name: 'Ana Bordados',
    initial: 'A',
    color: 'taupe',
    text: 'Guardado para inspirarme después.',
    time: 'hace 20 min',
    likes: 2,
    replies: [],
  },
  {
    id: '4',
    name: 'Nico Escultor',
    initial: 'N',
    color: 'verde',
    text: '¿Qué papel usaste para esta tirada?',
    time: 'hace 18 min',
    likes: 1,
    replies: [
      {
        id: '4-1',
        name: 'Vale Grabados',
        initial: 'V',
        color: 'terracota',
        text: 'Un algodón de 300g, aguanta bien la tinta.',
        time: 'hace 10 min',
      },
    ],
  },
  {
    id: '5',
    name: 'Taller Norte',
    initial: 'T',
    color: 'taupe',
    text: 'Increíble el detalle del follaje, se ve súper vivo.',
    time: 'hace 15 min',
    likes: 7,
    replies: [],
  },
  {
    id: '6',
    name: 'Sofi Cerámica',
    initial: 'S',
    color: 'mostaza',
    text: 'La niebla quedó espectacular, ¿es grabado o litografía?',
    time: 'hace 12 min',
    likes: 3,
    replies: [],
  },
  {
    id: '7',
    name: 'Mateo Ríos',
    initial: 'M',
    color: 'verde',
    text: 'Cada vez mejor tu trabajo, se nota la evolución.',
    time: 'hace 9 min',
    likes: 5,
    replies: [],
  },
  {
    id: '8',
    name: 'Luna Atelier',
    initial: 'L',
    color: 'terracota',
    text: 'Esto necesita estar en una expo ya mismo.',
    time: 'hace 5 min',
    likes: 9,
    replies: [],
  },
];

export default function ComentariosScreen() {
  const { height: windowHeight } = useWindowDimensions();
  const sheetHeight = Math.round(windowHeight * 0.75);

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

  // Dragging the handle down even a little (small distance or a quick
  // flick) dismisses the sheet entirely instead of requiring a full
  // drag to the bottom of the screen.
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

  const [comments, setComments] = useState<Comment[]>(INITIAL_COMMENTS);
  const [draft, setDraft] = useState('');
  const [replyingTo, setReplyingTo] = useState<{ id: string; name: string } | null>(null);
  const inputRef = useRef<TextInput>(null);

  const totalCount = comments.reduce((sum, comment) => sum + 1 + comment.replies.length, 0);

  const startReply = (comment: Comment) => {
    setReplyingTo({ id: comment.id, name: comment.name });
    inputRef.current?.focus();
  };

  const handleSend = () => {
    const text = draft.trim();
    if (!text) return;

    if (replyingTo) {
      setComments((prev) =>
        prev.map((comment) =>
          comment.id === replyingTo.id
            ? {
                ...comment,
                replies: [
                  ...comment.replies,
                  {
                    id: `${comment.id}-r${comment.replies.length + 1}`,
                    name: 'Vos',
                    initial: 'L',
                    color: 'terracota',
                    text,
                    time: 'ahora',
                  },
                ],
              }
            : comment,
        ),
      );
    } else {
      setComments((prev) => [
        ...prev,
        {
          id: `new-${prev.length + 1}`,
          name: 'Vos',
          initial: 'L',
          color: 'terracota',
          text,
          time: 'ahora',
          likes: 0,
          replies: [],
        },
      ]);
    }

    setDraft('');
    setReplyingTo(null);
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
                Comentarios · {totalCount}
              </Text>
              <Pressable onPress={handleClose}>
                <Ionicons name="close" size={22} color={colors.ink.DEFAULT} />
              </Pressable>
            </View>

            <ScrollView className="flex-1" contentContainerClassName="gap-5 px-5 py-4">
              {comments.map((comment) => (
                <View key={comment.id} className="gap-3">
                  <View className="flex-row gap-3">
                    <Avatar initial={comment.initial} color={comment.color} size={36} />
                    <View className="flex-1 gap-1">
                      <View className="flex-row items-center gap-2">
                        <Text className="text-base font-semibold text-ink">{comment.name}</Text>
                        <Text className="text-xs text-stone-600">{comment.time}</Text>
                      </View>
                      <Text className="text-xl leading-snug tracking-tight text-ink">{comment.text}</Text>
                      <Pressable onPress={() => startReply(comment)} hitSlop={6} className="self-start">
                        <Text className="text-sm font-semibold text-stone-600">Responder</Text>
                      </Pressable>
                    </View>
                    <View className="items-center gap-0.5 pt-1">
                      <Ionicons name="star-outline" size={15} color={colors.stone[700]} />
                      <Text className="text-xs text-stone-600">{comment.likes}</Text>
                    </View>
                  </View>

                  {comment.replies.length > 0 && (
                    <View className="ml-11 gap-3 border-l border-sand-300 pl-3">
                      {comment.replies.map((reply) => (
                        <View key={reply.id} className="flex-row gap-2.5">
                          <Avatar initial={reply.initial} color={reply.color} size={28} />
                          <View className="flex-1 gap-1">
                            <View className="flex-row items-center gap-2">
                              <Text className="text-base font-semibold text-ink">{reply.name}</Text>
                              <Text className="text-xs text-stone-600">{reply.time}</Text>
                            </View>
                            <Text className="text-xl leading-snug tracking-tight text-ink">{reply.text}</Text>
                          </View>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
              ))}
            </ScrollView>

            {replyingTo && (
              <View className="flex-row items-center justify-between bg-sand-200 px-5 py-2">
                <Text className="text-xs text-stone-700">
                  Respondiendo a <Text className="font-semibold text-ink">{replyingTo.name}</Text>
                </Text>
                <Pressable onPress={() => setReplyingTo(null)} hitSlop={8}>
                  <Ionicons name="close" size={16} color={colors.stone[700]} />
                </Pressable>
              </View>
            )}

            <View className="flex-row items-center gap-3 border-t border-sand-300 px-5 py-3">
              <Avatar initial="L" color="terracota" size={32} />
              <TextInput
                ref={inputRef}
                value={draft}
                onChangeText={setDraft}
                placeholder={replyingTo ? `Responder a ${replyingTo.name}…` : 'Agregá un comentario…'}
                placeholderTextColor={colors.stone[700]}
                className="flex-1 rounded-full bg-sand-100 px-4 py-2.5 text-sm text-ink"
              />
              <Pressable onPress={handleSend} disabled={!draft.trim()} hitSlop={8}>
                <Ionicons name="send" size={20} color={draft.trim() ? colors.accent.DEFAULT : '#c9beb2'} />
              </Pressable>
            </View>
          </SafeAreaView>
        </KeyboardAvoidingView>
      </Animated.View>
    </View>
  );
}
