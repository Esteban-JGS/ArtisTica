import '@/global.css';

import {
  InstrumentSerif_400Regular,
  InstrumentSerif_400Regular_Italic,
  useFonts,
} from '@expo-google-fonts/instrument-serif';
import { QueryClientProvider } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { View } from 'react-native';

import { queryClient } from '@/lib/query-client';

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    InstrumentSerif_400Regular,
    InstrumentSerif_400Regular_Italic,
  });

  if (!fontsLoaded) {
    return <View className="flex-1 bg-sand-100" />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="create" options={{ presentation: 'modal' }} />
        <Stack.Screen
          name="comments"
          options={{
            presentation: 'transparentModal',
            animation: 'slide_from_bottom',
            contentStyle: { backgroundColor: 'transparent' },
          }}
        />
        <Stack.Screen
          name="share"
          options={{
            presentation: 'transparentModal',
            animation: 'slide_from_bottom',
            contentStyle: { backgroundColor: 'transparent' },
          }}
        />
      </Stack>
    </QueryClientProvider>
  );
}
