import { router } from 'expo-router';
import { type ReactNode, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Switch, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { hasForbiddenContact, PROVINCES, useProfileStore } from '@/stores/profile-store';
import { colors } from '@/theme';

const BIO_MAX = 120;
const ABOUT_MAX = 500;

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View className="gap-2">
      <Text className="text-xs font-semibold uppercase text-stone-700">{label}</Text>
      {children}
    </View>
  );
}

export default function EditarPerfilScreen() {
  const profile = useProfileStore((state) => state.profile);
  const updateProfile = useProfileStore((state) => state.updateProfile);
  const [role, setRole] = useState(profile.role);
  const [bio, setBio] = useState(profile.bio);
  const [about, setAbout] = useState(profile.about);
  const [place, setPlace] = useState(profile.place);
  const [commissionsOpen, setCommissionsOpen] = useState(profile.commissionsOpen);
  const [priceLow, setPriceLow] = useState(String(profile.priceLow));
  const [priceHigh, setPriceHigh] = useState(String(profile.priceHigh));
  const [openUntil, setOpenUntil] = useState(profile.openUntil);

  const low = Number(priceLow);
  const high = Number(priceHigh);
  const error = (() => {
    if (profile.isArtist && role.trim() === '') return 'Contá qué tipo de arte hacés.';
    if (hasForbiddenContact(`${bio} ${about}`))
      return 'No se permiten teléfonos ni WhatsApp: el contacto va por la plataforma.';
    if (!Number.isInteger(low) || !Number.isInteger(high) || low <= 0 || high <= 0)
      return 'Los precios tienen que ser números enteros.';
    if (low > high) return 'El precio mínimo no puede ser mayor que el máximo.';
    if (commissionsOpen && openUntil.trim() === '') return 'Indicá hasta cuándo tomás pedidos.';
    return null;
  })();

  const save = () => {
    if (error) return;
    updateProfile({
      role: role.trim(),
      bio: bio.trim(),
      about: about.trim(),
      place,
      commissionsOpen,
      priceLow: low,
      priceHigh: high,
      openUntil: openUntil.trim(),
    });
    router.back();
  };

  const inputClass = 'rounded-xl bg-sand-50 px-4 py-3 text-base text-ink';

  return (
    <View className="flex-1 bg-sand-100">
      <SafeAreaView className="flex-1">
        <View className="flex-row items-center justify-between border-b border-sand-300 px-5 py-3">
          <Pressable onPress={() => router.back()}>
            <Text className="text-base text-stone-800">Cancelar</Text>
          </Pressable>
          <Text className="text-base font-semibold text-ink">Editar perfil</Text>
          <Pressable
            onPress={save}
            disabled={error !== null}
            className={error === null ? 'rounded-full bg-accent px-4 py-2' : 'rounded-full bg-accent/40 px-4 py-2'}>
            <Text className="text-sm font-semibold text-sand-50">Guardar</Text>
          </Pressable>
        </View>

        <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView
            contentContainerClassName="gap-5 p-5"
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}>
            {profile.isArtist && (
              <Field label="Qué hacés">
                <TextInput
                  value={role}
                  onChangeText={setRole}
                  placeholder="Ilustradora, ceramista, muralista…"
                  placeholderTextColor={colors.stone[700]}
                  maxLength={40}
                  className={inputClass}
                />
              </Field>
            )}

            <Field label={`Bio corta · ${bio.length}/${BIO_MAX}`}>
              <TextInput
                value={bio}
                onChangeText={setBio}
                placeholder="Una línea que te presente"
                placeholderTextColor={colors.stone[700]}
                maxLength={BIO_MAX}
                multiline
                className={inputClass}
              />
            </Field>

            <Field label={`Sobre mí · ${about.length}/${ABOUT_MAX}`}>
              <TextInput
                value={about}
                onChangeText={setAbout}
                placeholder="Tu trayectoria, tu estilo, qué tipo de encargos tomás"
                placeholderTextColor={colors.stone[700]}
                maxLength={ABOUT_MAX}
                multiline
                className={`${inputClass} min-h-24`}
                textAlignVertical="top"
              />
            </Field>

            <Field label="Provincia">
              <View className="flex-row flex-wrap gap-2">
                {PROVINCES.map((item) => (
                  <Pressable
                    key={item}
                    onPress={() => setPlace(item)}
                    className={item === place ? 'rounded-full bg-accent px-4 py-2' : 'rounded-full bg-sand-50 px-4 py-2'}>
                    <Text className={item === place ? 'text-sm font-semibold text-sand-50' : 'text-sm text-ink'}>
                      {item}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </Field>

            {profile.isArtist && (
              <Field label="Ficha de comisión">
                <View className="gap-4 rounded-2xl bg-sand-50 p-4">
                  <View className="flex-row items-center gap-3">
                    <View className="flex-1">
                      <Text className="text-sm font-semibold text-ink">Abierto a comisiones</Text>
                      <Text className="text-xs text-stone-700">Los clientes pueden solicitarte un encargo</Text>
                    </View>
                    <Switch
                      value={commissionsOpen}
                      onValueChange={setCommissionsOpen}
                      trackColor={{ false: colors.sand[300], true: colors.accent.DEFAULT }}
                      thumbColor={colors.sand[50]}
                    />
                  </View>

                  <View className="flex-row gap-3">
                    <View className="flex-1 gap-1">
                      <Text className="text-xs text-stone-700">Desde (miles de ₡)</Text>
                      <TextInput
                        value={priceLow}
                        onChangeText={setPriceLow}
                        keyboardType="number-pad"
                        maxLength={4}
                        className="rounded-xl bg-sand-100 px-4 py-3 text-base text-ink"
                      />
                    </View>
                    <View className="flex-1 gap-1">
                      <Text className="text-xs text-stone-700">Hasta (miles de ₡)</Text>
                      <TextInput
                        value={priceHigh}
                        onChangeText={setPriceHigh}
                        keyboardType="number-pad"
                        maxLength={4}
                        className="rounded-xl bg-sand-100 px-4 py-3 text-base text-ink"
                      />
                    </View>
                  </View>

                  {commissionsOpen && (
                    <View className="gap-1">
                      <Text className="text-xs text-stone-700">Tomando pedidos hasta</Text>
                      <TextInput
                        value={openUntil}
                        onChangeText={setOpenUntil}
                        placeholder="noviembre"
                        placeholderTextColor={colors.stone[700]}
                        maxLength={20}
                        className="rounded-xl bg-sand-100 px-4 py-3 text-base text-ink"
                      />
                    </View>
                  )}
                </View>
              </Field>
            )}

            {error && <Text className="text-sm text-accent">{error}</Text>}
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}
