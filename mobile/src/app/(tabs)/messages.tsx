import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { AppBackground, useCorkScroll } from '@/components/app-background';
import { Avatar } from '@/components/avatar';
import { StatusBadge } from '@/components/status-badge';
import {
  type AppNotification,
  formatColones,
  nextStepOf,
  relativeTime,
  useCommissionsStore,
} from '@/stores/commissions-store';
import { colors, NOTE_SHADOW } from '@/theme';

type Tab = 'chats' | 'comisiones' | 'notificaciones';

function openNotification(item: AppNotification) {
  useCommissionsStore.getState().markNotificationRead(item.id);
  const target = item.target;
  switch (target.kind) {
    case 'commission':
      router.push({ pathname: '/comision/[id]', params: { id: target.id } });
      return;
    case 'artist':
      router.push({
        pathname: '/artista/[id]',
        params: { id: target.party.name, name: target.party.name, color: target.party.color },
      });
      return;
    case 'profile':
      router.navigate('/profile');
      return;
    case 'comments':
      router.push('/comments');
  }
}

function EmptyState({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  return (
    <View className="items-center gap-3 rounded-2xl bg-sand-50 px-4 py-12" style={NOTE_SHADOW}>
      <Ionicons name={icon} size={28} color={colors.stone[700]} />
      <Text className="text-center text-sm text-stone-700">{text}</Text>
    </View>
  );
}

export default function MensajesScreen() {
  const { scrollY, onScroll } = useCorkScroll();
  const { tab: tabParam } = useLocalSearchParams<{ tab?: string }>();
  const tab: Tab = tabParam === 'chats' || tabParam === 'notificaciones' ? tabParam : 'comisiones';
  const setTab = (next: Tab) => router.setParams({ tab: next });
  const [searching, setSearching] = useState(false);
  const [query, setQuery] = useState('');

  const conversations = useCommissionsStore((state) => state.conversations);
  const commissions = useCommissionsStore((state) => state.commissions);
  const notifications = useCommissionsStore((state) => state.notifications);

  const normalizedQuery = query.trim().toLowerCase();
  const matches = (...texts: string[]) =>
    normalizedQuery === '' || texts.some((text) => text.toLowerCase().includes(normalizedQuery));

  const chatList = [...conversations]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .filter((chat) => matches(chat.counterpart.name, chat.messages.at(-1)?.text ?? ''));
  const commissionList = [...commissions]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .filter((item) => matches(item.counterpart.name, item.title));
  const notificationList = notifications.filter((item) => matches(item.who.name, item.text));

  const unreadChats = conversations.filter((chat) => chat.unread > 0).length;
  const pendingCommissions = commissions.filter((item) => nextStepOf(item).mine).length;
  const unreadNotifications = notifications.filter((item) => !item.read).length;

  const toggleSearch = () => {
    setSearching((value) => !value);
    setQuery('');
  };

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: 'chats', label: 'Chats', count: unreadChats },
    { id: 'comisiones', label: 'Comisiones', count: pendingCommissions },
    { id: 'notificaciones', label: 'Notis', count: unreadNotifications },
  ];

  return (
    <View className="flex-1 bg-sand-100">
      <AppBackground scrollY={scrollY} />
      <View className="flex-row items-center justify-between px-5 pb-3 pt-14">
        <Text className="font-serif text-3xl italic text-ink">Mensajes</Text>
        <Pressable
          onPress={toggleSearch}
          accessibilityRole="button"
          accessibilityLabel={searching ? 'Cerrar búsqueda' : 'Buscar'}
          className="h-10 w-10 items-center justify-center rounded-full bg-sand-50">
          <Ionicons name={searching ? 'close' : 'search'} size={18} color={colors.ink.DEFAULT} />
        </Pressable>
      </View>

      {searching && (
        <View className="mx-5 mb-3 flex-row items-center gap-2 rounded-full bg-sand-50 px-4 py-2.5">
          <Ionicons name="search" size={16} color={colors.stone[700]} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            autoFocus
            placeholder="Buscar por nombre o encargo"
            placeholderTextColor={colors.stone[700]}
            className="flex-1 text-sm text-ink"
          />
        </View>
      )}

      <View className="mx-5 mb-4 flex-row rounded-full bg-ink p-1">
        {tabs.map((item) => (
          <Pressable
            key={item.id}
            onPress={() => setTab(item.id)}
            className={
              tab === item.id
                ? 'flex-1 flex-row items-center justify-center gap-1.5 rounded-full bg-sand-50 py-2'
                : 'flex-1 flex-row items-center justify-center gap-1.5 py-2'
            }>
            <Text className={tab === item.id ? 'text-sm font-semibold text-ink' : 'text-sm text-sand-200'}>
              {item.label}
            </Text>
            {item.count > 0 && (
              <View className="h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1">
                <Text className="text-[10px] font-bold text-sand-50">{item.count}</Text>
              </View>
            )}
          </Pressable>
        ))}
      </View>

      <Animated.ScrollView
        onScroll={onScroll}
        scrollEventThrottle={16}
        contentContainerClassName="px-5 pb-32"
        keyboardShouldPersistTaps="handled">
        {tab === 'chats' &&
          (chatList.length === 0 ? (
            <EmptyState
              icon="chatbubbles-outline"
              text={
                normalizedQuery
                  ? 'No hay chats con esa búsqueda.'
                  : 'Tus conversaciones aparecen acá cuando consultás a un artista.'
              }
            />
          ) : (
            <View className="rounded-2xl bg-sand-50 px-4" style={NOTE_SHADOW}>
              {chatList.map((chat, index) => {
                const commission = commissions.find((item) => item.id === chat.commissionId);
                const last = chat.messages.at(-1);
                return (
                  <Pressable
                    key={chat.id}
                    onPress={() => router.push({ pathname: '/chat/[id]', params: { id: chat.id } })}
                    className={
                      index < chatList.length - 1
                        ? 'flex-row items-center gap-3 border-b border-sand-300 py-3'
                        : 'flex-row items-center gap-3 py-3'
                    }>
                    <Avatar initial={chat.counterpart.initial} color={chat.counterpart.color} />
                    <View className="flex-1 gap-1">
                      <View className="flex-row items-center gap-2">
                        <Text className="font-semibold text-ink">{chat.counterpart.name}</Text>
                        {commission ? (
                          <StatusBadge status={commission.status} />
                        ) : (
                          <Text className="text-[11px] font-semibold uppercase text-stone-700">Entre artistas</Text>
                        )}
                      </View>
                      <Text
                        className={chat.unread > 0 ? 'text-sm font-semibold text-ink' : 'text-sm text-stone-700'}
                        numberOfLines={1}>
                        {last ? `${last.from === 'me' ? 'Vos: ' : ''}${last.text}` : ''}
                      </Text>
                    </View>
                    <View className="items-end gap-1.5">
                      <Text className="text-xs text-stone-600">{relativeTime(chat.updatedAt)}</Text>
                      {chat.unread > 0 && <View className="h-2.5 w-2.5 rounded-full bg-accent" />}
                    </View>
                  </Pressable>
                );
              })}
            </View>
          ))}

        {tab === 'comisiones' &&
          (commissionList.length === 0 ? (
            <EmptyState
              icon="document-text-outline"
              text={
                normalizedQuery
                  ? 'No hay comisiones con esa búsqueda.'
                  : 'Cuando pidas o recibas un encargo, lo seguís desde acá.'
              }
            />
          ) : (
            commissionList.map((item) => {
              const step = nextStepOf(item);
              return (
                <Pressable
                  key={item.id}
                  onPress={() => router.push({ pathname: '/comision/[id]', params: { id: item.id } })}
                  className="mb-3 gap-2 rounded-2xl bg-sand-50 p-4"
                  style={NOTE_SHADOW}>
                  <View className="flex-row items-center gap-3">
                    <Avatar initial={item.counterpart.initial} color={item.counterpart.color} size={36} />
                    <View className="flex-1">
                      <Text className="text-xs text-stone-700">
                        {item.myRole === 'cliente' ? `Pedido a ${item.counterpart.name}` : `Encargo de ${item.counterpart.name}`}
                      </Text>
                      <Text className="font-semibold text-ink" numberOfLines={1}>
                        {item.title}
                      </Text>
                    </View>
                    <StatusBadge status={item.status} />
                  </View>
                  <View className="flex-row items-center justify-between">
                    <Text
                      className={step.mine ? 'text-xs font-semibold text-accent' : 'text-xs text-stone-700'}
                      numberOfLines={1}>
                      {step.text}
                    </Text>
                    {item.quote && (
                      <Text className="text-xs font-semibold text-ink">{formatColones(item.quote.price)}</Text>
                    )}
                  </View>
                </Pressable>
              );
            })
          ))}

        {tab === 'notificaciones' &&
          (notificationList.length === 0 ? (
            <EmptyState icon="notifications-outline" text="No tenés notificaciones." />
          ) : (
            <View className="rounded-2xl bg-sand-50 px-4" style={NOTE_SHADOW}>
              {notificationList.map((item, index) => (
                <Pressable
                  key={item.id}
                  onPress={() => openNotification(item)}
                  className={
                    index < notificationList.length - 1
                      ? 'flex-row items-center gap-3 border-b border-sand-300 py-3'
                      : 'flex-row items-center gap-3 py-3'
                  }>
                  <View className="relative">
                    <Avatar initial={item.who.initial} color={item.who.color} />
                    <View
                      className="absolute -bottom-1 -right-1 h-5 w-5 items-center justify-center rounded-full bg-accent"
                      style={{ borderWidth: 2, borderColor: colors.sand[50] }}>
                      <Ionicons name={item.icon} size={10} color={colors.sand[50]} />
                    </View>
                  </View>
                  <View className="flex-1">
                    <Text className={item.read ? 'text-sm text-stone-800' : 'text-sm text-ink'}>
                      <Text className="font-semibold">{item.who.name}</Text> {item.text}
                    </Text>
                  </View>
                  <View className="items-end gap-1.5">
                    <Text className="text-xs text-stone-600">{relativeTime(item.at)}</Text>
                    {!item.read && <View className="h-2.5 w-2.5 rounded-full bg-accent" />}
                  </View>
                </Pressable>
              ))}
            </View>
          ))}
      </Animated.ScrollView>
    </View>
  );
}
