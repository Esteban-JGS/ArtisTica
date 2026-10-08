import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar } from '@/components/avatar';
import { StatusBadge } from '@/components/status-badge';
import { clockTime, type Message, nextStepOf, useCommissionsStore } from '@/stores/commissions-store';
import { mentionsOffPlatformPayment } from '@/stores/profile-store';
import { colors } from '@/theme';

const OFF_PLATFORM_WARNING = 'Si pagás fuera de Artística, no tenés protección ni reseña.';

function Bubble({ message }: { message: Message }) {
  if (message.from === 'system') {
    return (
      <View className="my-1 items-center px-6">
        <View className="flex-row items-center gap-1.5 rounded-full bg-sand-200 px-3 py-1.5">
          <Ionicons name="shield-checkmark-outline" size={12} color={colors.stone[900]} />
          <Text className="text-center text-xs text-stone-900">{message.text}</Text>
        </View>
      </View>
    );
  }

  const mine = message.from === 'me';
  return (
    <View className={mine ? 'items-end' : 'items-start'}>
      <View
        className={mine ? 'max-w-[80%] gap-2 rounded-2xl rounded-br-md bg-accent p-3' : 'max-w-[80%] gap-2 rounded-2xl rounded-bl-md bg-sand-50 p-3'}>
        {message.image && (
          <Pressable
            onPress={() => router.push({ pathname: '/ver-obra', params: { image: message.image } })}
            className="overflow-hidden rounded-xl">
            <Image source={{ uri: message.image }} style={{ width: 220, height: 160 }} />
          </Pressable>
        )}
        <Text className={mine ? 'text-sm text-sand-50' : 'text-sm text-ink'}>{message.text}</Text>
        <Text className={mine ? 'self-end text-[10px] text-sand-100' : 'self-end text-[10px] text-stone-600'}>
          {clockTime(message.at)}
        </Text>
      </View>
    </View>
  );
}

export default function ChatScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const conversation = useCommissionsStore((state) => state.conversations.find((item) => item.id === id));
  const commission = useCommissionsStore((state) =>
    state.commissions.find((item) => item.id === conversation?.commissionId),
  );
  const sendMessage = useCommissionsStore((state) => state.sendMessage);
  const markConversationRead = useCommissionsStore((state) => state.markConversationRead);
  const [draft, setDraft] = useState('');
  const scrollRef = useRef<ScrollView>(null);

  const messageCount = conversation?.messages.length ?? 0;
  useEffect(() => {
    // Lo que llega con el chat abierto tambien queda leido
    markConversationRead(id);
  }, [id, messageCount, markConversationRead]);

  if (!conversation) {
    return (
      <SafeAreaView className="flex-1 items-center justify-center bg-sand-100">
        <Text className="text-sm text-stone-700">Esta conversación ya no existe.</Text>
      </SafeAreaView>
    );
  }

  const showWarning = mentionsOffPlatformPayment(draft);
  const step = commission ? nextStepOf(commission) : null;

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    sendMessage(conversation.id, text);
    setDraft('');
  };

  return (
    <View className="flex-1 bg-sand-100">
      <SafeAreaView edges={['top', 'bottom']} className="flex-1">
        <View className="flex-row items-center gap-3 border-b border-sand-300 px-4 py-2.5">
          <Pressable onPress={() => router.back()} hitSlop={8} accessibilityLabel="Volver">
            <Ionicons name="chevron-back" size={24} color={colors.ink.DEFAULT} />
          </Pressable>
          <Pressable
            onPress={() =>
              router.push({
                pathname: '/artista/[id]',
                params: { id: conversation.counterpart.name, name: conversation.counterpart.name, color: conversation.counterpart.color },
              })
            }
            className="flex-1 flex-row items-center gap-3">
            <Avatar initial={conversation.counterpart.initial} color={conversation.counterpart.color} size={38} />
            <View className="flex-1">
              <Text className="font-semibold text-ink">{conversation.counterpart.name}</Text>
              <Text className="text-xs text-stone-700" numberOfLines={1}>
                {commission ? commission.title : 'Mensaje directo entre artistas'}
              </Text>
            </View>
          </Pressable>
        </View>

        {commission && step && (
          <Pressable
            onPress={() => router.push({ pathname: '/comision/[id]', params: { id: commission.id } })}
            className="mx-4 mt-3 flex-row items-center gap-3 rounded-2xl bg-sand-50 px-4 py-3">
            <StatusBadge status={commission.status} />
            <Text
              className={step.mine ? 'flex-1 text-xs font-semibold text-accent' : 'flex-1 text-xs text-stone-700'}
              numberOfLines={1}>
              {step.text}
            </Text>
            <Text className="text-xs font-semibold text-ink">Ver encargo</Text>
            <Ionicons name="chevron-forward" size={14} color={colors.ink.DEFAULT} />
          </Pressable>
        )}

        <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView
            ref={scrollRef}
            className="flex-1"
            contentContainerClassName="gap-2 px-4 py-4"
            onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
            keyboardShouldPersistTaps="handled">
            {conversation.messages.map((message) => (
              <Bubble key={message.id} message={message} />
            ))}
          </ScrollView>

          {showWarning && (
            <View className="mx-4 mb-2 flex-row items-center gap-2 rounded-xl bg-gold/20 px-3 py-2">
              <Ionicons name="alert-circle-outline" size={16} color={colors.ink[700]} />
              <Text className="flex-1 text-xs text-ink">{OFF_PLATFORM_WARNING}</Text>
            </View>
          )}

          <View className="flex-row items-end gap-2 border-t border-sand-300 px-4 py-2.5">
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder="Escribí un mensaje"
              placeholderTextColor={colors.stone[700]}
              multiline
              className="max-h-28 flex-1 rounded-2xl bg-sand-50 px-4 py-2.5 text-sm text-ink"
            />
            <Pressable
              onPress={send}
              disabled={!draft.trim()}
              accessibilityLabel="Enviar"
              className={draft.trim() ? 'h-10 w-10 items-center justify-center rounded-full bg-accent' : 'h-10 w-10 items-center justify-center rounded-full bg-accent/40'}>
              <Ionicons name="send" size={16} color={colors.sand[50]} />
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}
