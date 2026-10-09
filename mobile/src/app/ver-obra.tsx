import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { Image, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useProfileStore } from '@/stores/profile-store';
import { colors } from '@/theme';

export default function VerObraScreen() {
  const { image, caption, authorName, authorRole, authorColor, acceptsCommissions } = useLocalSearchParams<{
    image: string;
    caption?: string;
    authorName?: string;
    authorRole?: string;
    authorColor?: string;
    acceptsCommissions?: string;
  }>();
  const ownName = useProfileStore((state) => state.profile.name);
  // Solo se ofrece ir al artista cuando la obra es de otra persona
  const showArtist = Boolean(authorName) && authorName !== ownName && authorRole !== undefined;

  const openArtist = () =>
    authorName &&
    router.replace({
      pathname: '/artista/[id]',
      params: { id: authorName, name: authorName, role: authorRole, color: authorColor },
    });

  const requestCommission = () =>
    router.replace({
      pathname: '/solicitar-comision',
      params: { artistName: authorName, postImage: image, postCaption: caption },
    });

  return (
    <View style={{ flex: 1, backgroundColor: '#000' }}>
      <SafeAreaView style={{ flex: 1 }}>
        <View className="flex-row items-center justify-between px-5 py-3">
          <Text className="text-sm font-medium text-sand-50">{authorName ?? ''}</Text>
          <Pressable onPress={() => router.back()} hitSlop={8}>
            <Ionicons name="close" size={26} color="#fdf8f3" />
          </Pressable>
        </View>

        <View className="flex-1 items-center justify-center">
          <Image source={{ uri: image }} className="h-full w-full" resizeMode="contain" />
        </View>

        {(caption || showArtist) && (
          <View className="gap-3 px-5 pb-6 pt-3">
            {caption && <Text className="text-sm text-sand-100">{caption}</Text>}
            {showArtist && (
              <View className="flex-row gap-2">
                <Pressable onPress={openArtist} className="flex-1 items-center rounded-full bg-sand-50/15 py-3">
                  <Text className="text-sm font-semibold text-sand-50">Ver perfil de {authorName}</Text>
                </Pressable>
                {acceptsCommissions === '1' && (
                  <Pressable
                    onPress={requestCommission}
                    className="flex-row items-center gap-1.5 rounded-full bg-gold px-4 py-3">
                    <Ionicons name="cash-outline" size={15} color={colors.ink.DEFAULT} />
                    <Text className="text-sm font-semibold text-ink">Solicitar</Text>
                  </Pressable>
                )}
              </View>
            )}
          </View>
        )}
      </SafeAreaView>
    </View>
  );
}
