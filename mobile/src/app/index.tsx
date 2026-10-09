import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { useMemo } from 'react';
import { Text, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

import { GlassButton } from '@/components/glass-button';
import { LoginGallery } from '@/components/login-gallery';
import { useCommissionsStore } from '@/stores/commissions-store';
import { useProfileStore } from '@/stores/profile-store';
import { colors } from '@/theme';

function getGreeting(hour: number) {
  if (hour < 12) return 'Buenos días';
  if (hour < 19) return 'Buenas tardes';
  return 'Buenas noches';
}

function getTimeTint(hour: number) {
  if (hour < 12) return 'rgba(240,196,132,0.26)'; // mañana dorada
  if (hour < 19) return 'rgba(198,104,72,0.34)'; // tarde terracota
  return 'rgba(66,74,132,0.34)'; // noche azulada
}

export default function AuthScreen() {
  const insets = useSafeAreaInsets();
  // Google y Apple todavia no estan conectados: entran con la cuenta de la demo
  const enterWithProvider = () => {
    useProfileStore.getState().signIn();
    useCommissionsStore.getState().loadDemo();
    router.replace('/home');
  };
  const hour = useMemo(() => new Date().getHours(), []);
  const greeting = useMemo(() => getGreeting(hour), [hour]);
  const timeTint = useMemo(() => getTimeTint(hour), [hour]);

  return (
    <View style={{ flex: 1, backgroundColor: '#18130d' }}>
      <LoginGallery />
      <LinearGradient
        colors={['rgba(24,18,13,0.6)', 'rgba(18,13,9,0.96)']}
        style={{ position: 'absolute', width: '100%', height: '100%' }}
      />
      <View
        pointerEvents="none"
        style={{ position: 'absolute', width: '100%', height: '100%', backgroundColor: timeTint }}
      />

      <SafeAreaView
        edges={['bottom']}
        style={{
          flex: 1,
          justifyContent: 'flex-end',
          paddingTop: 16,
          paddingHorizontal: 22,
          paddingBottom: 24 + insets.bottom,
        }}>
        <View style={{ gap: 10 }}>
          <Text
            style={{
              fontSize: 12,
              fontWeight: '600',
              letterSpacing: 2,
              textTransform: 'uppercase',
              color: 'rgba(255,255,255,0.65)',
            }}>
            {greeting}
          </Text>
          <Text
            style={{
              fontFamily: 'InstrumentSerif_400Regular_Italic',
              fontStyle: 'italic',
              fontSize: 44,
              color: colors.sand[50],
            }}>
            Artística
          </Text>
          <Text style={{ fontSize: 18, fontWeight: '700', color: colors.sand[50] }}>
            Acá tu talento se ve, se valora y se paga.
          </Text>
          <Text style={{ fontSize: 14, color: 'rgba(255,255,255,0.7)', lineHeight: 20 }}>
            Publicá tu obra, construí comunidad con otros artistas y gestioná tus comisiones de
            forma segura.
          </Text>
        </View>

        <View style={{ marginTop: 28, gap: 10 }}>
          <GlassButton
            variant="primary"
            icon={<Ionicons name="mail-outline" size={19} color="#ffffff" />}
            label="Crear mi cuenta"
            onPress={() => router.push('/registro')}
          />
          <View style={{ flexDirection: 'row', gap: 9 }}>
            <GlassButton
              variant="glass"
              icon={<Ionicons name="logo-google" size={17} color="#ffffff" />}
              label="Google"
              onPress={enterWithProvider}
            />
            <GlassButton
              variant="glass"
              icon={<Ionicons name="logo-apple" size={17} color="#ffffff" />}
              label="Apple"
              onPress={enterWithProvider}
            />
          </View>
          <GlassButton
            variant="ghost"
            icon={<Ionicons name="arrow-forward-outline" size={14} color="rgba(255,255,255,0.82)" />}
            label="Ya tengo cuenta"
            onPress={() => router.push('/ingresar')}
            style={{ alignSelf: 'center' }}
          />
        </View>
      </SafeAreaView>
    </View>
  );
}
