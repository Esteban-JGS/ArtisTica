import { Image } from 'expo-image';
import { View } from 'react-native';

import { backgroundImageUri, useBackgroundStore } from '@/stores/background-store';

// A textured photo behind the sand palette, standing in for a
// mural/workshop backdrop (pick it in Perfil > Personalización).
// Tinted lightly with the sand tone — just enough to keep floating
// cards and text legible without flattening the texture into a wash
// of white.
export function AppBackground() {
  const backgroundId = useBackgroundStore((state) => state.backgroundId);

  return (
    <View pointerEvents="none" style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
      <Image
        source={{ uri: backgroundImageUri(backgroundId, 1200) }}
        style={{ flex: 1 }}
        contentFit="cover"
      />
      <View
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(247,245,241,0.45)',
        }}
      />
    </View>
  );
}
