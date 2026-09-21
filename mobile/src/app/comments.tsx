import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
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
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar } from '@/components/avatar';

const MOCK_COMMENTS: {
  id: string;
  name: string;
  initial: string;
  color: 'terracota' | 'verde' | 'mostaza' | 'taupe';
  text: string;
  time: string;
  likes: number;
}[] = [
  {
    id: '1',
    name: 'Caro Diseños',
    initial: 'C',
    color: 'verde',
    text: 'Qué textura tan real, se nota el trabajo detrás.',
    time: 'hace 1 h',
    likes: 12,
  },
  {
    id: '2',
    name: 'Fede Arte',
    initial: 'F',
    color: 'mostaza',
    text: 'Me encantaría ver el proceso completo 👀',
    time: 'hace 45 min',
    likes: 4,
  },
  {
    id: '3',
    name: 'Ana Bordados',
    initial: 'A',
    color: 'taupe',
    text: 'Guardado para inspirarme después.',
    time: 'hace 20 min',
    likes: 2,
  },
];

export default function ComentariosScreen() {
  const { authorName, commentsCount } = useLocalSearchParams<{
    authorName?: string;
    commentsCount?: string;
  }>();
  const [draft, setDraft] = useState('');
  const { height: windowHeight } = useWindowDimensions();
  const sheetHeight = Math.round(windowHeight * 0.75);

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={{ flex: 1, justifyContent: 'flex-end' }}>
      <Pressable className="absolute inset-0 bg-ink/40" onPress={() => router.back()} />

      <View className="rounded-t-3xl bg-sand-50" style={{ height: sheetHeight }}>
        <SafeAreaView edges={['bottom']} className="flex-1">
          <View className="items-center pt-2.5">
            <View className="h-1 w-10 rounded-full bg-sand-300" />
          </View>

          <View className="flex-row items-center justify-between border-b border-sand-300 px-5 py-3">
            <Text className="text-base font-semibold text-ink">
              Comentarios{commentsCount ? ` · ${commentsCount}` : ''}
            </Text>
            <Pressable onPress={() => router.back()}>
              <Ionicons name="close" size={22} color="#201d1a" />
            </Pressable>
          </View>

          <ScrollView className="flex-1" contentContainerClassName="gap-4 px-5 py-4">
            {MOCK_COMMENTS.map((comment) => (
              <View key={comment.id} className="flex-row gap-3">
                <Avatar initial={comment.initial} color={comment.color} size={36} />
                <View className="flex-1 gap-1">
                  <View className="flex-row items-center gap-2">
                    <Text className="text-sm font-semibold text-ink">{comment.name}</Text>
                    <Text className="text-xs text-stone-600">{comment.time}</Text>
                  </View>
                  <Text className="text-sm text-ink">{comment.text}</Text>
                </View>
                <View className="items-center gap-0.5 pt-1">
                  <Ionicons name="star-outline" size={15} color="#8b8279" />
                  <Text className="text-xs text-stone-600">{comment.likes}</Text>
                </View>
              </View>
            ))}
          </ScrollView>

          <View className="flex-row items-center gap-3 border-t border-sand-300 px-5 py-3">
            <Avatar initial="L" color="terracota" size={32} />
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder={authorName ? `Responder a ${authorName}…` : 'Agregá un comentario…'}
              placeholderTextColor="#8b8279"
              className="flex-1 rounded-full bg-sand-100 px-4 py-2.5 text-sm text-ink"
            />
            <Pressable disabled={!draft.trim()} hitSlop={8}>
              <Ionicons name="send" size={20} color={draft.trim() ? '#c2653b' : '#c9beb2'} />
            </Pressable>
          </View>
        </SafeAreaView>
      </View>
    </KeyboardAvoidingView>
  );
}
