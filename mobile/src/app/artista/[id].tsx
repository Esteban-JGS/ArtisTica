import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppBackground } from '@/components/app-background';
import { colors, roleColors } from '@/theme';

const PORTFOLIO_COUNT = 6;

export default function PerfilArtistaScreen() {
  const { id, name, role, initial, color } = useLocalSearchParams<{
    id: string;
    name?: string;
    role?: string;
    initial?: string;
    color?: string;
  }>();
  const [isFollowing, setIsFollowing] = useState(false);

  const roleColor = color && color in roleColors ? roleColors[color as keyof typeof roleColors] : roleColors.terracota;
  const displayName = name ?? id;
  const seed = encodeURIComponent(id);

  const portfolio = Array.from({ length: PORTFOLIO_COUNT }, (_, i) => ({
    id: String(i),
    image: `https://picsum.photos/seed/${seed}-${i}/500/500`,
  }));

  return (
    <View className="flex-1 bg-sand-100">
      <AppBackground />
      <SafeAreaView edges={['top']} className="flex-1">
        <View className="flex-row items-center justify-between px-5 py-3">
          <Pressable onPress={() => router.back()} hitSlop={8}>
            <Ionicons name="chevron-back" size={24} color={colors.ink.DEFAULT} />
          </Pressable>
          <Text className="text-base font-semibold text-ink">{displayName}</Text>
          <View style={{ width: 24 }} />
        </View>

        <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
          <View className="h-40 bg-sage">
            <Image source={{ uri: `https://picsum.photos/seed/${seed}-cover/800/500` }} className="h-full w-full" />
          </View>

          <View className="-mt-10 px-5">
            <View
              className="h-20 w-20 items-center justify-center rounded-full border-4 border-sand-100"
              style={{ backgroundColor: roleColor.base }}>
              <Text className="font-serif text-3xl text-sand-50">{initial ?? displayName?.[0]}</Text>
            </View>

            <View className="mt-3 flex-row items-center gap-2">
              <Text className="font-serif text-3xl italic text-ink">{displayName}</Text>
            </View>
            {role && (
              <View className="mt-1 self-start rounded-full px-2 py-0.5" style={{ backgroundColor: roleColor.bg }}>
                <Text className="text-xs font-medium" style={{ color: roleColor.fg }}>
                  {role}
                </Text>
              </View>
            )}

            <View className="mt-4 flex-row justify-between rounded-2xl bg-sand-50 px-4 py-3">
              <View className="items-center">
                <Text className="text-base font-semibold text-ink">{portfolio.length * 7}</Text>
                <Text className="text-xs text-stone-700">OBRAS</Text>
              </View>
              <View className="items-center">
                <Text className="text-base font-semibold text-ink">2.4k</Text>
                <Text className="text-xs text-stone-700">SEGUIDORES</Text>
              </View>
              <View className="items-center">
                <Text className="text-base font-semibold text-ink">186</Text>
                <Text className="text-xs text-stone-700">SIGUIENDO</Text>
              </View>
            </View>

            <View className="mt-4 flex-row gap-3">
              <Pressable
                onPress={() => setIsFollowing((value) => !value)}
                className={
                  isFollowing
                    ? 'flex-1 items-center rounded-full bg-sand-50 py-3'
                    : 'flex-1 items-center rounded-full bg-accent py-3'
                }>
                <Text className={isFollowing ? 'font-semibold text-ink' : 'font-semibold text-sand-50'}>
                  {isFollowing ? 'Siguiendo' : 'Seguir'}
                </Text>
              </Pressable>
              <Pressable
                onPress={() => router.push({ pathname: '/solicitar-comision', params: { artistName: displayName } })}
                className="flex-1 items-center rounded-full bg-sand-50 py-3">
                <Text className="font-semibold text-ink">Solicitar comisión</Text>
              </Pressable>
            </View>

            <View className="mt-6 flex-row flex-wrap gap-2 py-4">
              {portfolio.map((item) => (
                <Image
                  key={item.id}
                  source={{ uri: item.image }}
                  className="aspect-square rounded-xl"
                  style={{ width: '31.5%' }}
                />
              ))}
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
