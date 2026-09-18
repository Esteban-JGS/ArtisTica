import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

function AuthButton({
  icon,
  label,
  variant = 'light',
  onPress,
}: {
  icon: React.ReactNode;
  label: string;
  variant?: 'light' | 'solid';
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      className={
        variant === 'solid'
          ? 'flex-row items-center justify-center gap-2 rounded-full bg-accent px-6 py-4 active:bg-accent-dark'
          : 'flex-row items-center justify-center gap-2 rounded-full bg-sand-50/90 px-6 py-4 active:bg-sand-200'
      }>
      {icon}
      <Text className={variant === 'solid' ? 'text-base font-semibold text-sand-50' : 'text-base font-semibold text-ink'}>
        {label}
      </Text>
    </Pressable>
  );
}

export default function WelcomeScreen() {
  const enterApp = () => router.replace('/home');

  return (
    <View className="flex-1 bg-ink">
      <Image
        source={require('@/assets/images/login-wppr.avif')}
        style={{ position: 'absolute', width: '100%', height: '100%' }}
        contentFit="cover"
      />
      <LinearGradient
        colors={['rgba(32,29,26,0.35)', 'rgba(32,29,26,0.55)', 'rgba(32,29,26,0.92)']}
        locations={[0, 0.55, 1]}
        style={{ position: 'absolute', width: '100%', height: '100%' }}
      />

      <SafeAreaView className="flex-1 justify-between px-6 py-8">
        <View className="flex-1 items-center justify-center gap-6">
          <Image
            source={require('@/assets/images/logo-mark.png')}
            style={{ width: 96, height: 96 }}
            contentFit="contain"
          />
          <View className="items-center gap-3">
            <Text className="font-serif text-5xl italic text-sand-50">Artística</Text>
            <Text className="max-w-[280px] text-center text-base text-sand-200">
              Donde el trabajo se muestra, se conversa y se encarga.
            </Text>
          </View>
        </View>

        <View className="gap-3">
          <AuthButton
            icon={<Ionicons name="logo-google" size={18} color="#201d1a" />}
            label="Continuar con Google"
            onPress={enterApp}
          />
          <AuthButton
            icon={<Ionicons name="logo-apple" size={18} color="#201d1a" />}
            label="Continuar con Apple"
            onPress={enterApp}
          />
          <AuthButton
            icon={<Ionicons name="mail" size={18} color="#fdf8f3" />}
            label="Continuar con correo"
            variant="solid"
            onPress={enterApp}
          />
          <Pressable onPress={enterApp} className="mt-2 items-center">
            <Text className="text-sm text-sand-200">
              ¿Ya tenés cuenta? <Text className="font-semibold text-accent">Iniciar sesión</Text>
            </Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}
