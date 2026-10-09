import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCommissionsStore } from '@/stores/commissions-store';
import { DEMO_ACCOUNT, useProfileStore } from '@/stores/profile-store';
import { colors } from '@/theme';

export default function IngresarScreen() {
  const signIn = useProfileStore((state) => state.signIn);
  const loadDemo = useCommissionsStore((state) => state.loadDemo);
  // Viene con la cuenta de la demo cargada para no tipearla en la presentacion
  const [email, setEmail] = useState(DEMO_ACCOUNT.email);
  const [password, setPassword] = useState(DEMO_ACCOUNT.password);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = email.trim() !== '' && password !== '';

  const submit = () => {
    if (email.trim().toLowerCase() !== DEMO_ACCOUNT.email || password !== DEMO_ACCOUNT.password) {
      setError('El correo o la contraseña no coinciden.');
      return;
    }
    signIn();
    loadDemo();
    router.replace('/home');
  };

  const forgotPassword = () =>
    Alert.alert('Revisá tu correo', `Si ${email.trim() || 'tu correo'} tiene cuenta, te mandamos un enlace para cambiar la contraseña.`);

  const inputClass = 'rounded-xl bg-sand-50 px-4 py-3 text-base text-ink';

  return (
    <View className="flex-1 bg-sand-100">
      <SafeAreaView className="flex-1">
        <View className="flex-row items-center px-5 py-3">
          <Pressable onPress={() => router.back()} hitSlop={8} accessibilityLabel="Volver">
            <Ionicons name="chevron-back" size={24} color={colors.ink.DEFAULT} />
          </Pressable>
        </View>

        <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView
            contentContainerClassName="gap-5 px-5 pb-8"
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}>
            <View className="gap-1">
              <Text className="font-serif text-4xl italic text-ink">Qué bueno verte</Text>
              <Text className="text-sm text-stone-700">Ingresá para ver a quienes seguís y tus comisiones.</Text>
            </View>

            <View className="gap-2">
              <Text className="text-xs font-semibold uppercase text-stone-700">Correo</Text>
              <TextInput
                value={email}
                onChangeText={(text) => {
                  setEmail(text);
                  setError(null);
                }}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                className={inputClass}
              />
            </View>

            <View className="gap-2">
              <Text className="text-xs font-semibold uppercase text-stone-700">Contraseña</Text>
              <View className="flex-row items-center rounded-xl bg-sand-50 pr-3">
                <TextInput
                  value={password}
                  onChangeText={(text) => {
                    setPassword(text);
                    setError(null);
                  }}
                  secureTextEntry={!showPassword}
                  autoCapitalize="none"
                  className="flex-1 px-4 py-3 text-base text-ink"
                />
                <Pressable
                  onPress={() => setShowPassword((value) => !value)}
                  hitSlop={8}
                  accessibilityLabel={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}>
                  <Ionicons name={showPassword ? 'eye-off-outline' : 'eye-outline'} size={20} color={colors.stone[700]} />
                </Pressable>
              </View>
              <Pressable onPress={forgotPassword} className="self-end py-1">
                <Text className="text-xs font-semibold text-stone-800">¿Olvidaste tu contraseña?</Text>
              </Pressable>
            </View>

            {error && <Text className="text-sm text-accent">{error}</Text>}

            <Pressable
              onPress={submit}
              disabled={!canSubmit}
              className={canSubmit ? 'items-center rounded-full bg-accent py-3.5' : 'items-center rounded-full bg-accent/40 py-3.5'}>
              <Text className="text-base font-semibold text-sand-50">Ingresar</Text>
            </Pressable>

            <Pressable onPress={() => router.replace('/registro')} className="items-center py-2">
              <Text className="text-sm text-stone-800">
                ¿No tenés cuenta? <Text className="font-semibold text-accent">Creala gratis</Text>
              </Text>
            </Pressable>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}
