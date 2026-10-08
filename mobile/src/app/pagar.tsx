import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { balanceOf, depositOf, formatColones, useCommissionsStore } from '@/stores/commissions-store';
import { colors } from '@/theme';

const METHODS = [
  { id: 'tarjeta', label: 'Tarjeta terminada en 4242', icon: 'card-outline' as const },
  { id: 'sinpe', label: 'SINPE Móvil', icon: 'phone-portrait-outline' as const },
];

// Lo que tarda la pasarela en confirmar en la demo
const PROCESSING_MS = 1500;

export default function PagarScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const commission = useCommissionsStore((state) => state.commissions.find((item) => item.id === id));
  const payDeposit = useCommissionsStore((state) => state.payDeposit);
  const [method, setMethod] = useState(METHODS[0].id);
  const [phase, setPhase] = useState<'review' | 'processing' | 'done'>('review');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  if (!commission?.quote) {
    return (
      <SafeAreaView className="flex-1 items-center justify-center bg-sand-100">
        <Text className="text-sm text-stone-700">No hay nada para pagar.</Text>
      </SafeAreaView>
    );
  }

  const quote = commission.quote;
  const deposit = depositOf(quote);

  const pay = () => {
    setPhase('processing');
    timer.current = setTimeout(() => {
      payDeposit(commission.id, method === 'sinpe' ? 'SINPE Móvil' : 'tarjeta');
      setPhase('done');
    }, PROCESSING_MS);
  };

  if (phase === 'done') {
    return (
      <SafeAreaView className="flex-1 items-center justify-center gap-3 bg-sand-100 px-8">
        <Ionicons name="checkmark-circle" size={56} color={colors.sage} />
        <Text className="text-center text-xl font-semibold text-ink">Anticipo pagado</Text>
        <Text className="text-center text-sm text-stone-700">
          {commission.counterpart.name} ya puede empezar. Te avisamos cuando entregue la vista previa.
        </Text>
        <Pressable onPress={() => router.back()} className="mt-3 rounded-full bg-accent px-8 py-3">
          <Text className="text-sm font-semibold text-sand-50">Volver al encargo</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  return (
    <View className="flex-1 bg-sand-100">
      <SafeAreaView className="flex-1">
        <View className="flex-row items-center justify-between border-b border-sand-300 px-5 py-3">
          <Pressable onPress={() => router.back()} disabled={phase === 'processing'}>
            <Text className="text-base text-stone-800">Cancelar</Text>
          </Pressable>
          <Text className="text-base font-semibold text-ink">Pagar anticipo</Text>
          <View style={{ width: 60 }} />
        </View>

        <ScrollView contentContainerClassName="gap-4 p-5" showsVerticalScrollIndicator={false}>
          <View className="gap-1">
            <Text className="text-xs text-stone-700">Pedido a {commission.counterpart.name}</Text>
            <Text className="text-lg font-semibold text-ink">{commission.title}</Text>
          </View>

          <View className="gap-2 rounded-2xl bg-sand-50 p-4">
            <View className="flex-row justify-between">
              <Text className="text-sm text-stone-800">Precio acordado</Text>
              <Text className="text-sm text-ink">{formatColones(quote.price)}</Text>
            </View>
            <View className="flex-row justify-between">
              <Text className="text-sm font-semibold text-ink">Anticipo hoy ({quote.depositPercent}%)</Text>
              <Text className="text-sm font-bold text-ink">{formatColones(deposit)}</Text>
            </View>
            <View className="flex-row justify-between">
              <Text className="text-sm text-stone-800">Saldo al aprobar la vista previa</Text>
              <Text className="text-sm text-ink">{formatColones(balanceOf(quote))}</Text>
            </View>
          </View>

          <View className="gap-2">
            <Text className="text-xs font-semibold uppercase text-stone-700">Método de pago</Text>
            {METHODS.map((item) => {
              const selected = item.id === method;
              return (
                <Pressable
                  key={item.id}
                  onPress={() => setMethod(item.id)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected }}
                  className={
                    selected
                      ? 'flex-row items-center gap-3 rounded-2xl border-2 border-accent bg-sand-50 p-4'
                      : 'flex-row items-center gap-3 rounded-2xl border-2 border-transparent bg-sand-50 p-4'
                  }>
                  <Ionicons name={item.icon} size={20} color={colors.ink.DEFAULT} />
                  <Text className="flex-1 text-sm text-ink">{item.label}</Text>
                  <Ionicons
                    name={selected ? 'radio-button-on' : 'radio-button-off'}
                    size={20}
                    color={selected ? colors.accent.DEFAULT : colors.stone[600]}
                  />
                </Pressable>
              );
            })}
          </View>

          <View className="gap-2 rounded-2xl bg-sage/10 p-4">
            <View className="flex-row items-center gap-2">
              <Ionicons name="shield-checkmark" size={18} color={colors.sage} />
              <Text className="text-sm font-semibold text-ink">Pago protegido por Artística</Text>
            </View>
            <Text className="text-xs text-ink">• El anticipo le paga a {commission.counterpart.name} por empezar.</Text>
            <Text className="text-xs text-ink">• El saldo solo se cobra cuando aprobás la vista previa.</Text>
            <Text className="text-xs text-ink">• Si no entrega lo acordado, podés abrir una disputa.</Text>
          </View>
        </ScrollView>

        <View className="border-t border-sand-300 px-5 pb-2 pt-3">
          <Pressable
            onPress={pay}
            disabled={phase === 'processing'}
            className="flex-row items-center justify-center gap-2 rounded-full bg-accent py-3.5">
            {phase === 'processing' && <ActivityIndicator color={colors.sand[50]} />}
            <Text className="text-base font-semibold text-sand-50">
              {phase === 'processing' ? 'Procesando…' : `Pagar ${formatColones(deposit)}`}
            </Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}
