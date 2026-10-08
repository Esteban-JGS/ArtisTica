import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, ScrollView, Switch, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { CURRENT_AUTHOR, usePostsStore } from '@/stores/posts-store';
import { colors } from '@/theme';

const CATEGORIES = ['Dibujantes', 'Músicos', 'Pintores', 'Artesanos', 'Escultores'];

export default function CrearScreen() {
  const addPost = usePostsStore((state) => state.addPost);
  const [image, setImage] = useState<string | null>(null);
  const [caption, setCaption] = useState('');
  const [category, setCategory] = useState('Dibujantes');
  const [openToCommissions, setOpenToCommissions] = useState(true);

  const canPublish = image !== null;

  const publish = () => {
    if (!canPublish || !image) return;
    addPost({
      ...CURRENT_AUTHOR,
      time: 'ahora',
      image,
      caption: caption.trim(),
      tags: [category.toLowerCase()],
      acceptsCommissions: openToCommissions,
    });
    router.back();
  };

  const pickFromLibrary = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) return;
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (!result.canceled) setImage(result.assets[0].uri);
  };

  const pickFromCamera = async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) return;
    const result = await ImagePicker.launchCameraAsync({ quality: 0.8 });
    if (!result.canceled) setImage(result.assets[0].uri);
  };

  return (
    <View className="flex-1 bg-sand-100">
      <SafeAreaView className="flex-1">
        <View className="flex-row items-center justify-between border-b border-sand-300 px-5 py-3">
          <Pressable onPress={() => router.back()}>
            <Text className="text-base text-stone-800">Cancelar</Text>
          </Pressable>
          <Text className="text-base font-semibold text-ink">Nueva obra</Text>
          <Pressable
            onPress={publish}
            disabled={!canPublish}
            className={canPublish ? 'rounded-full bg-accent px-4 py-2' : 'rounded-full bg-accent/40 px-4 py-2'}>
            <Text className="text-sm font-semibold text-sand-50">Publicar</Text>
          </Pressable>
        </View>

        <ScrollView contentContainerClassName="gap-5 p-5" showsVerticalScrollIndicator={false}>
          {image ? (
            <Pressable onPress={pickFromLibrary} className="overflow-hidden rounded-2xl">
              <Image source={{ uri: image }} className="aspect-square w-full" />
            </Pressable>
          ) : (
            <View className="items-center gap-3 rounded-2xl border border-dashed border-stone-500 bg-sand-50 px-6 py-10">
              <Ionicons name="image-outline" size={28} color={colors.stone[700]} />
              <Text className="text-base font-semibold text-ink">Muestra tu creatividad</Text>
              <Text className="text-sm text-stone-700">Subí una foto de tu obra</Text>
              <View className="flex-row gap-2">
                <Pressable onPress={pickFromLibrary} className="rounded-full bg-sand-200 px-4 py-2">
                  <Text className="text-sm font-medium text-ink">Galería</Text>
                </Pressable>
                <Pressable onPress={pickFromCamera} className="rounded-full bg-sand-200 px-4 py-2">
                  <Text className="text-sm font-medium text-ink">Cámara</Text>
                </Pressable>
              </View>
            </View>
          )}

          <TextInput
            value={caption}
            onChangeText={setCaption}
            placeholder="¿Qué estás pensando?"
            placeholderTextColor={colors.stone[700]}
            multiline
            className="border-b border-sand-300 pb-3 text-base text-ink"
          />

          <View className="gap-2">
            <Text className="text-xs font-semibold uppercase text-stone-700">Categoría</Text>
            <View className="flex-row flex-wrap gap-2">
              {CATEGORIES.map((item) => (
                <Pressable
                  key={item}
                  onPress={() => setCategory(item)}
                  className={
                    item === category
                      ? 'rounded-full bg-accent px-4 py-2'
                      : 'rounded-full bg-sand-50 px-4 py-2'
                  }>
                  <Text className={item === category ? 'text-sm font-semibold text-sand-50' : 'text-sm text-ink'}>
                    {item}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>

          <View className="flex-row items-center gap-3 rounded-2xl bg-sand-50 px-4 py-3">
            <Ionicons name="lock-closed-outline" size={18} color={colors.accent.DEFAULT} />
            <View className="flex-1">
              <Text className="text-sm font-semibold text-ink">Abierto a comisiones</Text>
              <Text className="text-xs text-stone-700">Muestra el badge en esta obra</Text>
            </View>
            <Switch
              value={openToCommissions}
              onValueChange={setOpenToCommissions}
              trackColor={{ false: colors.sand[300], true: colors.accent.DEFAULT }}
              thumbColor={colors.sand[50]}
            />
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
