import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { type ReactNode, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCommissionsStore } from '@/stores/commissions-store';
import { usePostsStore } from '@/stores/posts-store';
import { handleError, hasForbiddenContact, useProfileStore } from '@/stores/profile-store';
import { colors } from '@/theme';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PASSWORD_MIN = 8;

function toHandle(text: string) {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9_]/g, '');
}

function Field({ label, error, children }: { label: string; error?: string | null; children: ReactNode }) {
  return (
    <View className="gap-2">
      <Text className="text-xs font-semibold uppercase text-stone-700">{label}</Text>
      {children}
      {error && <Text className="text-xs text-accent">{error}</Text>}
    </View>
  );
}

function AccountType({
  selected,
  icon,
  title,
  description,
  onPress,
}: {
  selected: boolean;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  description: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      className={
        selected
          ? 'flex-1 gap-1.5 rounded-2xl border-2 border-accent bg-sand-50 p-3'
          : 'flex-1 gap-1.5 rounded-2xl border-2 border-transparent bg-sand-50 p-3'
      }>
      <Ionicons name={icon} size={20} color={selected ? colors.accent.DEFAULT : colors.stone[700]} />
      <Text className="text-sm font-semibold text-ink">{title}</Text>
      <Text className="text-xs text-stone-700">{description}</Text>
    </Pressable>
  );
}

export default function RegistroScreen() {
  const register = useProfileStore((state) => state.register);
  const clearAccount = useCommissionsStore((state) => state.clearAccount);
  const posts = usePostsStore((state) => state.posts);
  const [name, setName] = useState('');
  const [handle, setHandle] = useState('');
  const [handleEdited, setHandleEdited] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isArtist, setIsArtist] = useState(true);
  const [submitted, setSubmitted] = useState(false);

  // Los usuarios que ya existen en la demo: la cuenta propia y los artistas del feed
  const takenHandles = new Set(['lunaatelier', ...posts.map((post) => toHandle(post.name))]);

  const nameError = (() => {
    if (name.trim() === '') return 'Poné tu nombre o el de tu taller.';
    if (hasForbiddenContact(name)) return 'No se permiten teléfonos ni WhatsApp.';
    return null;
  })();
  const handleProblem = handleError(handle) ?? (takenHandles.has(handle) ? 'Ese usuario ya existe.' : null);
  const emailError = EMAIL_PATTERN.test(email.trim()) ? null : 'Revisá el correo.';
  const passwordError = password.length >= PASSWORD_MIN ? null : `Mínimo ${PASSWORD_MIN} caracteres.`;
  const isValid = !nameError && !handleProblem && !emailError && !passwordError;

  const changeName = (text: string) => {
    setName(text);
    // Sugiere el usuario a partir del nombre hasta que lo editen a mano
    if (!handleEdited) setHandle(toHandle(text).slice(0, 30));
  };

  const submit = () => {
    setSubmitted(true);
    if (!isValid) return;
    register({ name: name.trim(), handle, isArtist });
    clearAccount();
    router.replace('/home');
  };

  const inputClass = 'rounded-xl bg-sand-50 px-4 py-3 text-base text-ink';
  const show = (error: string | null, value: string) => (submitted || value !== '' ? error : null);

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
              <Text className="font-serif text-4xl italic text-ink">Creá tu cuenta</Text>
              <Text className="text-sm text-stone-700">
                Publicar, abrir comisiones y recibir pedidos no tiene costo.
              </Text>
            </View>

            <View className="flex-row gap-3">
              <AccountType
                selected={isArtist}
                icon="color-palette-outline"
                title="Soy artista"
                description="Publico mi obra y recibo encargos"
                onPress={() => setIsArtist(true)}
              />
              <AccountType
                selected={!isArtist}
                icon="search-outline"
                title="Busco artistas"
                description="Quiero encargar arte hecho por personas"
                onPress={() => setIsArtist(false)}
              />
            </View>

            <Field label="Nombre" error={show(nameError, name)}>
              <TextInput
                value={name}
                onChangeText={changeName}
                placeholder={isArtist ? 'Tu nombre o el de tu taller' : 'Tu nombre'}
                placeholderTextColor={colors.stone[700]}
                maxLength={80}
                className={inputClass}
              />
            </Field>

            <Field label="Usuario" error={show(handleProblem, handle)}>
              <View className="flex-row items-center rounded-xl bg-sand-50 px-4">
                <Text className="text-base text-stone-700">@</Text>
                <TextInput
                  value={handle}
                  onChangeText={(text) => {
                    setHandleEdited(true);
                    setHandle(toHandle(text));
                  }}
                  autoCapitalize="none"
                  autoCorrect={false}
                  maxLength={30}
                  className="flex-1 py-3 text-base text-ink"
                />
              </View>
            </Field>

            <Field label="Correo" error={show(emailError, email)}>
              <TextInput
                value={email}
                onChangeText={setEmail}
                placeholder="vos@correo.com"
                placeholderTextColor={colors.stone[700]}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                className={inputClass}
              />
            </Field>

            <Field label="Contraseña" error={show(passwordError, password)}>
              <View className="flex-row items-center rounded-xl bg-sand-50 pr-3">
                <TextInput
                  value={password}
                  onChangeText={setPassword}
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
            </Field>

            <Pressable
              onPress={submit}
              className={isValid ? 'items-center rounded-full bg-accent py-3.5' : 'items-center rounded-full bg-accent/40 py-3.5'}>
              <Text className="text-base font-semibold text-sand-50">Crear cuenta</Text>
            </Pressable>

            <Text className="text-center text-xs text-stone-700">
              Al crear tu cuenta aceptás que en Artística solo se publica arte hecho por personas.
            </Text>

            <Pressable onPress={() => router.replace('/ingresar')} className="items-center py-2">
              <Text className="text-sm text-stone-800">
                ¿Ya tenés cuenta? <Text className="font-semibold text-accent">Ingresá</Text>
              </Text>
            </Pressable>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}
