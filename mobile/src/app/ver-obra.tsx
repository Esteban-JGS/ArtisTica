import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { Image, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function VerObraScreen() {
  const { image, caption, authorName } = useLocalSearchParams<{
    image: string;
    caption?: string;
    authorName?: string;
  }>();

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

        {caption && (
          <View className="px-5 pb-6 pt-3">
            <Text className="text-sm text-sand-100">{caption}</Text>
          </View>
        )}
      </SafeAreaView>
    </View>
  );
}
