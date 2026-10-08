import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import type { ReactNode } from 'react';
import { Alert, Image, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppBackground } from '@/components/app-background';
import { Avatar } from '@/components/avatar';
import { StatusBadge } from '@/components/status-badge';
import {
  artistNetOf,
  balanceOf,
  type Commission,
  type CommissionStatus,
  depositOf,
  formatColones,
  nextStepOf,
  relativeTime,
  SERVICE_FEE_PERCENT,
  useCommissionsStore,
} from '@/stores/commissions-store';
import { colors, NOTE_SHADOW } from '@/theme';

const STEPS: { status: CommissionStatus; label: string; detail: (commission: Commission) => string }[] = [
  { status: 'consulta', label: 'Consulta', detail: () => 'La idea, las referencias y el chat' },
  { status: 'cotizado', label: 'Cotización', detail: () => 'Precio, revisiones y fecha de entrega' },
  {
    status: 'en_proceso',
    label: 'Anticipo pagado',
    detail: (c) => (c.quote ? `${formatColones(depositOf(c.quote))} al aceptar. El trabajo arranca` : 'El trabajo arranca'),
  },
  {
    status: 'vista_previa',
    label: 'Vista previa',
    detail: (c) =>
      c.quote ? `Con marca de agua. Se autoriza el saldo de ${formatColones(balanceOf(c.quote))}` : 'Con marca de agua',
  },
  { status: 'completado', label: 'Aprobado y entregado', detail: () => 'Se cobra el saldo y se libera el archivo final' },
];

const STEP_ORDER: CommissionStatus[] = STEPS.map((step) => step.status);

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View className="gap-3 rounded-2xl bg-sand-50 p-4">
      <Text className="text-xs font-semibold uppercase text-stone-700">{title}</Text>
      {children}
    </View>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <View className="flex-row items-center justify-between">
      <Text className="text-sm text-stone-800">{label}</Text>
      <Text className={strong ? 'text-sm font-bold text-ink' : 'text-sm text-ink'}>{value}</Text>
    </View>
  );
}

function Timeline({ commission }: { commission: Commission }) {
  // Cada estado es un hito alcanzado: el paso en curso es el siguiente
  const rejected = commission.status === 'rechazado';
  const reachedIndex = rejected ? 0 : STEP_ORDER.indexOf(commission.status);
  return (
    <View>
      {STEPS.map((step, index) => {
        const reached = commission.history.find((item) => item.status === step.status);
        const done = index <= reachedIndex;
        const current = !rejected && index === reachedIndex + 1;
        const rejectedStep = rejected && index === 1;
        const isLast = index === STEPS.length - 1;
        let dotClass = 'h-6 w-6 items-center justify-center rounded-full bg-sand-300';
        if (done) dotClass = 'h-6 w-6 items-center justify-center rounded-full bg-sage';
        else if (current) dotClass = 'h-6 w-6 items-center justify-center rounded-full bg-accent';
        else if (rejectedStep) dotClass = 'h-6 w-6 items-center justify-center rounded-full bg-stone-500';
        return (
          <View key={step.status} className="flex-row gap-3">
            <View className="items-center">
              <View className={dotClass}>
                {done || rejectedStep ? (
                  <Ionicons name={done ? 'checkmark' : 'close'} size={14} color={colors.sand[50]} />
                ) : (
                  <Text className={current ? 'text-[11px] font-bold text-sand-50' : 'text-[11px] font-bold text-stone-700'}>
                    {index + 1}
                  </Text>
                )}
              </View>
              {!isLast && <View className={index < reachedIndex ? 'w-0.5 flex-1 bg-sage' : 'w-0.5 flex-1 bg-sand-300'} />}
            </View>
            <View className="flex-1 gap-0.5 pb-4">
              <View className="flex-row items-center justify-between">
                <Text className={done || current || rejectedStep ? 'text-sm font-semibold text-ink' : 'text-sm text-stone-700'}>
                  {rejectedStep ? 'Cotización rechazada' : step.label}
                </Text>
                {reached && <Text className="text-[11px] text-stone-600">{relativeTime(reached.at)}</Text>}
              </View>
              <Text className="text-xs text-stone-700">{step.detail(commission)}</Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

function Watermarked({ uri, watermark }: { uri: string; watermark: boolean }) {
  return (
    <Pressable
      onPress={() => router.push({ pathname: '/ver-obra', params: { image: uri } })}
      className="overflow-hidden rounded-xl">
      <Image source={{ uri }} className="w-full" style={{ aspectRatio: 4 / 3 }} />
      {watermark && (
        <View pointerEvents="none" className="absolute inset-0 items-center justify-center bg-ink/10">
          <Text
            className="font-serif text-2xl italic text-sand-50"
            style={{ opacity: 0.75, transform: [{ rotate: '-24deg' }] }}>
            Artística · vista previa
          </Text>
        </View>
      )}
    </Pressable>
  );
}

function Stars({ value, onChange }: { value: number; onChange?: (stars: number) => void }) {
  return (
    <View className="flex-row justify-center gap-2">
      {[1, 2, 3, 4, 5].map((star) => (
        <Pressable key={star} onPress={() => onChange?.(star)} disabled={!onChange} hitSlop={4}>
          <Ionicons name={star <= value ? 'star' : 'star-outline'} size={30} color={colors.gold} />
        </Pressable>
      ))}
    </View>
  );
}

export default function ComisionScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const commission = useCommissionsStore((state) => state.commissions.find((item) => item.id === id));
  const rejectQuote = useCommissionsStore((state) => state.rejectQuote);
  const deliverPreview = useCommissionsStore((state) => state.deliverPreview);
  const approvePreview = useCommissionsStore((state) => state.approvePreview);
  const rate = useCommissionsStore((state) => state.rate);

  if (!commission) {
    return (
      <SafeAreaView className="flex-1 items-center justify-center bg-sand-100">
        <Text className="text-sm text-stone-700">Este encargo ya no existe.</Text>
      </SafeAreaView>
    );
  }

  const { quote, counterpart } = commission;
  const isClient = commission.myRole === 'cliente';
  const step = nextStepOf(commission);
  const openChat = () =>
    router.push({ pathname: '/chat/[id]', params: { id: commission.conversationId } });

  const confirmReject = () =>
    Alert.alert('Rechazar cotización', 'No se te cobra nada y el chat queda abierto por si querés retomarlo.', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Rechazar', style: 'destructive', onPress: () => rejectQuote(commission.id) },
    ]);

  const confirmApprove = () =>
    quote &&
    Alert.alert(
      'Aprobar vista previa',
      `Se cobra el saldo de ${formatColones(balanceOf(quote))} que ya está autorizado y ${counterpart.name} te libera el archivo final.`,
      [
        { text: 'Todavía no', style: 'cancel' },
        { text: 'Aprobar', onPress: () => approvePreview(commission.id) },
      ],
    );

  const pickPreview = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) return;
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (!result.canceled) deliverPreview(commission.id, result.assets[0].uri);
  };

  let action: ReactNode = null;
  if (isClient && commission.status === 'cotizado' && quote) {
    action = (
      <View className="gap-2">
        <Pressable
          onPress={() => router.push({ pathname: '/pagar', params: { id: commission.id } })}
          className="items-center rounded-full bg-accent py-3.5">
          <Text className="text-base font-semibold text-sand-50">
            Aceptar y pagar anticipo · {formatColones(depositOf(quote))}
          </Text>
        </Pressable>
        <View className="flex-row gap-2">
          <Pressable onPress={openChat} className="flex-1 items-center rounded-full bg-sand-50 py-3">
            <Text className="text-sm font-semibold text-ink">Contraofertar</Text>
          </Pressable>
          <Pressable onPress={confirmReject} className="flex-1 items-center rounded-full bg-sand-50 py-3">
            <Text className="text-sm font-semibold text-stone-800">Rechazar</Text>
          </Pressable>
        </View>
      </View>
    );
  } else if (isClient && commission.status === 'vista_previa' && quote) {
    action = (
      <View className="gap-2">
        <Pressable onPress={confirmApprove} className="items-center rounded-full bg-accent py-3.5">
          <Text className="text-base font-semibold text-sand-50">Aprobar y pagar saldo · {formatColones(balanceOf(quote))}</Text>
        </Pressable>
        <Pressable onPress={openChat} className="items-center rounded-full bg-sand-50 py-3">
          <Text className="text-sm font-semibold text-ink">
            Pedir cambios ({quote.revisions} {quote.revisions === 1 ? 'revisión incluida' : 'revisiones incluidas'})
          </Text>
        </Pressable>
      </View>
    );
  } else if (!isClient && commission.status === 'consulta') {
    action = (
      <Pressable
        onPress={() => router.push({ pathname: '/cotizar', params: { id: commission.id } })}
        className="items-center rounded-full bg-accent py-3.5">
        <Text className="text-base font-semibold text-sand-50">Enviar cotización</Text>
      </Pressable>
    );
  } else if (!isClient && commission.status === 'en_proceso') {
    action = (
      <Pressable onPress={pickPreview} className="items-center rounded-full bg-accent py-3.5">
        <Text className="text-base font-semibold text-sand-50">Entregar vista previa</Text>
      </Pressable>
    );
  }

  return (
    <View className="flex-1 bg-sand-100">
      <AppBackground />
      <SafeAreaView edges={['top', 'bottom']} className="flex-1">
        <View className="flex-row items-center justify-between px-5 py-3">
          <Pressable onPress={() => router.back()} hitSlop={8} accessibilityLabel="Volver">
            <Ionicons name="chevron-back" size={24} color={colors.ink.DEFAULT} />
          </Pressable>
          <Text className="text-base font-semibold text-ink">{isClient ? 'Tu pedido' : 'Encargo recibido'}</Text>
          <Pressable onPress={openChat} hitSlop={8} accessibilityLabel="Abrir chat">
            <Ionicons name="chatbubble-ellipses-outline" size={22} color={colors.ink.DEFAULT} />
          </Pressable>
        </View>

        <ScrollView contentContainerClassName="gap-4 px-5 pb-6" showsVerticalScrollIndicator={false}>
          <View style={NOTE_SHADOW} className="gap-3 rounded-2xl bg-sand-50 p-4">
            <View className="flex-row items-center gap-3">
              <Avatar initial={counterpart.initial} color={counterpart.color} />
              <View className="flex-1">
                <Text className="text-xs text-stone-700">
                  {isClient ? `Pedido a ${counterpart.name}` : `Encargo de ${counterpart.name}`}
                </Text>
                <Text className="text-base font-semibold text-ink">{commission.title}</Text>
              </View>
              <StatusBadge status={commission.status} />
            </View>
            <View className={step.mine ? 'rounded-xl bg-accent/10 px-3 py-2' : 'rounded-xl bg-sand-100 px-3 py-2'}>
              <Text className={step.mine ? 'text-sm font-semibold text-accent' : 'text-sm text-stone-800'}>{step.text}</Text>
            </View>
          </View>

          <Section title="Seguimiento">
            <Timeline commission={commission} />
          </Section>

          {commission.previewImage && (
            <Section title={commission.status === 'completado' ? 'Entrega final' : 'Vista previa'}>
              <Watermarked uri={commission.previewImage} watermark={commission.status !== 'completado'} />
              <Text className="text-xs text-stone-700">
                {commission.status === 'completado'
                  ? 'Archivo final liberado, sin marca de agua.'
                  : 'La marca de agua se quita cuando se aprueba y se cobra el saldo.'}
              </Text>
            </Section>
          )}

          {quote && (
            <Section title="Cotización">
              <Text className="text-sm text-ink">{quote.description}</Text>
              <View className="gap-2 border-t border-sand-300 pt-3">
                <Row label="Revisiones incluidas" value={String(quote.revisions)} />
                <Row label="Entrega" value={quote.deliveryDate} />
                <Row label="Precio total" value={formatColones(quote.price)} strong />
                <Row label={`Anticipo (${quote.depositPercent}%)`} value={formatColones(depositOf(quote))} />
                <Row label="Saldo al aprobar" value={formatColones(balanceOf(quote))} />
                {!isClient && (
                  <Row
                    label={`Recibís (tarifa de ${SERVICE_FEE_PERCENT}%)`}
                    value={formatColones(artistNetOf(quote))}
                    strong
                  />
                )}
              </View>
            </Section>
          )}

          <Section title="La idea">
            <Text className="text-sm text-ink">{commission.idea}</Text>
            {commission.referenceImage && (
              <Pressable
                onPress={() => router.push({ pathname: '/ver-obra', params: { image: commission.referenceImage } })}
                className="flex-row items-center gap-3 rounded-xl bg-sand-100 p-2">
                <Image source={{ uri: commission.referenceImage }} className="h-12 w-12 rounded-lg" />
                <Text className="text-xs font-medium text-stone-800">Referencia adjunta</Text>
              </Pressable>
            )}
          </Section>

          {commission.status === 'completado' && isClient && (
            <Section title={commission.rating ? 'Tu reseña' : 'Calificá el encargo'}>
              <Stars
                value={commission.rating ?? 0}
                onChange={commission.rating ? undefined : (stars) => rate(commission.id, stars)}
              />
              {!commission.rating && (
                <Text className="text-center text-xs text-stone-700">
                  Tu reseña ayuda a que otras personas confíen en {counterpart.name}.
                </Text>
              )}
            </Section>
          )}

          <View className="flex-row gap-3 rounded-2xl bg-sage/10 p-4">
            <Ionicons name="shield-checkmark" size={20} color={colors.sage} />
            <Text className="flex-1 text-xs text-ink">
              {isClient
                ? 'Pago protegido: el anticipo arranca el trabajo y el saldo solo se cobra cuando aprobás la vista previa. Si algo sale mal, podés abrir una disputa.'
                : 'Pago protegido: cobrás el anticipo al aceptar y el saldo queda autorizado desde la vista previa. Todo lo acordado en el chat sirve como evidencia.'}
            </Text>
          </View>
        </ScrollView>

        {action && <View className="border-t border-sand-300 bg-sand-100 px-5 pb-2 pt-3">{action}</View>}
      </SafeAreaView>
    </View>
  );
}
