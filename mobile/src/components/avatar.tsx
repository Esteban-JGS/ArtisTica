import { Text, View } from 'react-native';

import { roleColors } from '@/theme';

export function Avatar({
  initial,
  color = 'terracota',
  size = 44,
}: {
  initial: string;
  color?: keyof typeof roleColors;
  size?: number;
}) {
  return (
    <View
      className="items-center justify-center rounded-full"
      style={{ width: size, height: size, backgroundColor: roleColors[color].base }}>
      <Text className="font-serif text-lg text-sand-50" style={{ fontSize: size * 0.4 }}>
        {initial}
      </Text>
    </View>
  );
}
