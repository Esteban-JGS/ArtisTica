import { Text, View } from 'react-native';

const AVATAR_COLORS: Record<string, string> = {
  terracota: '#c2653b',
  verde: '#3f6b63',
  mostaza: '#d99a3f',
  taupe: '#8b8279',
};

export function Avatar({
  initial,
  color = 'terracota',
  size = 44,
}: {
  initial: string;
  color?: keyof typeof AVATAR_COLORS;
  size?: number;
}) {
  return (
    <View
      className="items-center justify-center rounded-full"
      style={{ width: size, height: size, backgroundColor: AVATAR_COLORS[color] }}>
      <Text className="font-serif text-lg text-sand-50" style={{ fontSize: size * 0.4 }}>
        {initial}
      </Text>
    </View>
  );
}
