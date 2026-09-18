import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import type { BottomTabBarProps } from 'expo-router/tabs';
import { Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

const TAB_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  home: 'home',
  explore: 'compass',
  messages: 'chatbubbles',
  profile: 'person',
};

const TAB_LABELS: Record<string, string> = {
  home: 'Inicio',
  explore: 'Explorar',
  messages: 'Mensajes',
  profile: 'Perfil',
};

export function TabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();

  return (
    <View
      className="flex-row items-center justify-between bg-sand-50 px-6 pt-3"
      style={{ paddingBottom: insets.bottom + 12 }}>
      {state.routes.map((route, index) => {
        const isFocused = state.index === index;
        const color = isFocused ? '#c2653b' : '#8b8279';

        const onPress = () => {
          const event = navigation.emit({
            type: 'tabPress',
            target: route.key,
            canPreventDefault: true,
          });
          if (!isFocused && !event.defaultPrevented) {
            navigation.navigate(route.name);
          }
        };

        return (
          <Pressable key={route.key} onPress={onPress} className="flex-1 items-center gap-1 py-1">
            <Ionicons name={TAB_ICONS[route.name]} size={22} color={color} />
            <Text
              style={{ color }}
              className={isFocused ? 'text-xs font-semibold' : 'text-xs font-medium'}>
              {TAB_LABELS[route.name]}
            </Text>
          </Pressable>
        );
      })}

      <Pressable
        onPress={() => router.push('/create')}
        className="absolute -top-6 h-14 w-14 items-center justify-center rounded-full bg-accent shadow-lg active:bg-accent-dark"
        style={{ left: '50%', marginLeft: -28 }}>
        <Ionicons name="color-palette" size={24} color="#fdf8f3" />
      </Pressable>
    </View>
  );
}
