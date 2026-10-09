import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { type ReactNode, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  artistNetOf,
  balanceOf,
  deliveryDateIn,
  DEPOSIT_OPTIONS,
  depositOf,
  formatColones,
  MIN_PRICE,
  type Quote,
  SERVICE_FEE_PERCENT,
  useCommissionsStore,
} from '@/stores/commissions-store';
import { hasForbiddenContact } from '@/stores/profile-store';
import { colors } from '@/theme';

const MAX_REVISIONS = 5;

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View className="gap-2">
      <Text className="text-xs font-semibold uppercase text-stone-700">{label}</Text>
      {children}
    </View>
  );
}

export default function CotizarScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const commission = useCommissionsStore((state) => state.commissions.find((item) => item.id === id));
  const sendQuote = useCommissionsStore((state) => state.sendQuote);
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('');
  const [revisions, setRevisions] = useState(2);
  const [deliveryDate, setDeliveryDate] = useState(deliveryDateIn(14));
  const [depositPercent, setDepositPercent] = useState(50);

  if (!commission) {
    return (
      <SafeAreaView className="flex-1 items-center justify-center bg-sand-100">
        <Text className="text-sm text-stone-700">Este encargo ya no existe.</Text>
      </SafeAreaView>
    );
  }

  const amount = Number(price.replace(/\D/g, ''));
  const quote: Quote = { description: description.trim(), price: amount, revisions, deliveryDate, depositPercent };
  const error = (() => {
    if (description.trim() === '') return 'Describí qué incluye la pieza.';
    if (hasForbiddenContact(description)) return 'No se permiten teléfonos ni WhatsApp: el contacto va por la plataforma.';
    if (amount < MIN_PRICE) return `El precio mínimo de un pedido es ${formatColones(MIN_PRICE)}.`;
    if (deliveryDate.trim() === '') return 'Indicá la fecha de entrega.';
    return null;
  })();

  const submit = () => {
    if (error) return;
    sendQuote(commission.id, quote);
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
          <Text className="text-base font-semibold text-ink">Cotización</Text>
          <Pressable
            onPress={submit}
            disabled={error !== null}
            className={error === null ? 'rounded-full bg-accent px-4 py-2' : 'rounded-full bg-accent/40 px-4 py-2'}>
            <Text className="text-sm font-semibold text-sand-50">Enviar</Text>
          </Pressable>
        </View>

        <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView
            contentContainerClassName="gap-5 p-5"
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}>
            <View className="gap-1 rounded-2xl bg-sand-50 p-4">
              <Text className="text-xs text-stone-700">Consulta de {commission.counterpart.name}</Text>
              <Text className="text-sm text-ink">{commission.idea}</Text>
            </View>

            <Field label="Qué incluye">
              <TextInput
                value={description}
                onChangeText={setDescription}
                placeholder="Técnica, tamaño, formato de entrega…"
                placeholderTextColor={colors.stone[700]}
                multiline
                maxLength={500}
                className={`${inputClass} min-h-24`}
                textAlignVertical="top"
              />
            </Field>

            <Field label="Precio total">
              <View className="flex-row items-center rounded-xl bg-sand-50 px-4">
                <Text className="text-base text-stone-700">₡</Text>
                <TextInput
                  value={price}
                  onChangeText={(text) => setPrice(text.replace(/\D/g, ''))}
                  placeholder="35000"
                  placeholderTextColor={colors.stone[700]}
                  keyboardType="number-pad"
                  maxLength={8}
                  className="flex-1 py-3 pl-1 text-base text-ink"
                />
              </View>
            </Field>

            <View className="flex-row gap-3">
              <View className="flex-1">
                <Field label="Revisiones">
                  <View className="flex-row items-center justify-between rounded-xl bg-sand-50 px-2 py-1.5">
                    <Pressable
                      onPress={() => setRevisions((value) => Math.max(0, value - 1))}
                      hitSlop={6}
                      accessibilityLabel="Menos revisiones"
                      className="h-9 w-9 items-center justify-center rounded-full bg-sand-200">
                      <Ionicons name="remove" size={18} color={colors.ink.DEFAULT} />
                    </Pressable>
                    <Text className="text-base font-semibold text-ink">{revisions}</Text>
                    <Pressable
                      onPress={() => setRevisions((value) => Math.min(MAX_REVISIONS, value + 1))}
                      hitSlop={6}
                      accessibilityLabel="Más revisiones"
                      className="h-9 w-9 items-center justify-center rounded-full bg-sand-200">
                      <Ionicons name="add" size={18} color={colors.ink.DEFAULT} />
                    </Pressable>
                  </View>
                </Field>
              </View>
              <View className="flex-1">
                <Field label="Entrega">
                  <TextInput
                    value={deliveryDate}
                    onChangeText={setDeliveryDate}
                    maxLength={30}
                    className={inputClass}
                  />
                </Field>
              </View>
            </View>

            <Field label="Anticipo">
              <View className="flex-row gap-2">
                {DEPOSIT_OPTIONS.map((option) => (
                  <Pressable
                    key={option}
                    onPress={() => setDepositPercent(option)}
                    className={
                      option === depositPercent
                        ? 'flex-1 items-center rounded-full bg-accent py-2'
                        : 'flex-1 items-center rounded-full bg-sand-50 py-2'
                    }>
                    <Text
                      className={option === depositPercent ? 'text-sm font-semibold text-sand-50' : 'text-sm text-ink'}>
                      {option}%
                    </Text>
                  </Pressable>
                ))}
              </View>
            </Field>

            {amount >= MIN_PRICE && (
              <View className="gap-2 rounded-2xl bg-sand-50 p-4">
                <View className="flex-row justify-between">
                  <Text className="text-sm text-stone-800">Anticipo al aceptar</Text>
                  <Text className="text-sm text-ink">{formatColones(depositOf(quote))}</Text>
                </View>
                <View className="flex-row justify-between">
                  <Text className="text-sm text-stone-800">Saldo al aprobar</Text>
                  <Text className="text-sm text-ink">{formatColones(balanceOf(quote))}</Text>
                </View>
                <View className="flex-row justify-between border-t border-sand-300 pt-2">
                  <Text className="text-sm font-semibold text-ink">Recibís (tarifa de {SERVICE_FEE_PERCENT}%)</Text>
                  <Text className="text-sm font-bold text-ink">{formatColones(artistNetOf(quote))}</Text>
                </View>
              </View>
            )}

            {error && (description !== '' || price !== '') && <Text className="text-sm text-accent">{error}</Text>}
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}
