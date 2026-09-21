import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar } from '@/components/avatar';

const QUICK_CONTACTS: {
  id: string;
  name: string;
  initial: string;
  color: 'terracota' | 'verde' | 'mostaza' | 'taupe';
}[] = [
  { id: '1', name: 'Caro', initial: 'C', color: 'verde' },
  { id: '2', name: 'Fede', initial: 'F', color: 'mostaza' },
  { id: '3', name: 'Ana', initial: 'A', color: 'taupe' },
  { id: '4', name: 'Naty', initial: 'N', color: 'terracota' },
];

const SHARE_ACTIONS: { id: string; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { id: 'copy', label: 'Copiar enlace', icon: 'link-outline' },
  { id: 'story', label: 'Compartir en tu historia', icon: 'sparkles-outline' },
  { id: 'tag', label: 'Etiquetar a un amigo', icon: 'pricetag-outline' },
  { id: 'external', label: 'Compartir afuera de Artística', icon: 'arrow-redo-outline' },
];

export default function CompartirScreen() {
  const { authorName } = useLocalSearchParams<{ authorName?: string }>();
  const { height: windowHeight } = useWindowDimensions();
  const sheetHeight = Math.round(windowHeight * 0.6);

  return (
    <View className="flex-1 justify-end">
      <Pressable className="absolute inset-0 bg-ink/40" onPress={() => router.back()} />

      <View className="rounded-t-3xl bg-sand-50" style={{ maxHeight: sheetHeight }}>
        <SafeAreaView edges={['bottom']}>
          <View className="items-center pt-2.5">
            <View className="h-1 w-10 rounded-full bg-sand-300" />
          </View>

          <View className="flex-row items-center justify-between border-b border-sand-300 px-5 py-3">
            <Text className="text-base font-semibold text-ink">
              {authorName ? `Compartir obra de ${authorName}` : 'Compartir'}
            </Text>
            <Pressable onPress={() => router.back()}>
              <Ionicons name="close" size={22} color="#201d1a" />
            </Pressable>
          </View>

          <View className="gap-3 py-4">
            <Text className="px-5 text-xs font-semibold uppercase text-stone-700">Enviar a</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="gap-4 px-5">
              {QUICK_CONTACTS.map((contact) => (
                <Pressable key={contact.id} className="items-center gap-1.5">
                  <Avatar initial={contact.initial} color={contact.color} size={52} />
                  <Text className="text-xs text-ink">{contact.name}</Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>

          <View className="border-t border-sand-300 py-2">
            {SHARE_ACTIONS.map((action) => (
              <Pressable
                key={action.id}
                onPress={() => router.back()}
                className="flex-row items-center gap-4 px-5 py-3.5">
                <View className="h-9 w-9 items-center justify-center rounded-full bg-sand-100">
                  <Ionicons name={action.icon} size={18} color="#3d362f" />
                </View>
                <Text className="text-sm font-medium text-ink">{action.label}</Text>
              </Pressable>
            ))}
          </View>
        </SafeAreaView>
      </View>
    </View>
  );
}
