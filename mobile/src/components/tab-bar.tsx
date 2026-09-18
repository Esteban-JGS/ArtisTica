import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import type { BottomTabBarProps } from 'expo-router/tabs';
import { Platform, Pressable, Text, View } from 'react-native';
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

const ACCENT = '#c2653b';
const INACTIVE = '#8b8279';

export function TabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();

  return (
    <View
      className="flex-row items-center justify-between border-t border-sand-200 bg-sand-50 px-6 pt-3"
      style={{ paddingBottom: insets.bottom + 12 }}>
      {state.routes.map((route, index) => {
        const isFocused = state.index === index;
        const color = isFocused ? ACCENT : INACTIVE;
        const label = TAB_LABELS[route.name] ?? route.name;

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
          <Pressable
            key={route.key}
            onPress={onPress}
            accessibilityRole="tab"
            accessibilityState={{ selected: isFocused }}
            accessibilityLabel={label}
            android_ripple={{ color: '#e2ddd5', borderless: true }}
            className="flex-1 items-center gap-1 py-1">
            <Ionicons name={TAB_ICONS[route.name] ?? 'ellipse'} size={22} color={color} />
            <Text
              style={{ color }}
              className={isFocused ? 'text-xs font-semibold' : 'text-xs font-medium'}>
              {label}
            </Text>
          </Pressable>
        );
      })}

      <Pressable
        onPress={() => router.push('/create')}
        accessibilityRole="button"
        accessibilityLabel="Crear obra"
        android_ripple={{ color: '#a1512d', borderless: true }}
        className="absolute -top-6 h-14 w-14 items-center justify-center rounded-full bg-accent active:bg-accent-dark"
        style={{
          left: '50%',
          marginLeft: -28,
          ...Platform.select({
            android: { elevation: 6 },
            default: {
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 4 },
              shadowOpacity: 0.25,
              shadowRadius: 6,
            },
          }),
        }}>
        <Ionicons name="color-palette" size={24} color="#fdf8f3" />
      </Pressable>
    </View>
  );
}
