import { Text, View } from 'react-native';

import type { CommissionStatus } from '@/stores/commissions-store';

export const STATUS_LABELS: Record<CommissionStatus, string> = {
  consulta: 'Consulta',
  cotizado: 'Cotizado',
  en_proceso: 'En proceso',
  vista_previa: 'Vista previa',
  completado: 'Completado',
  rechazado: 'Rechazado',
};

const STATUS_STYLES: Record<CommissionStatus, { bg: string; text: string }> = {
  consulta: { bg: 'bg-stone-400/20', text: 'text-stone-800' },
  cotizado: { bg: 'bg-accent/15', text: 'text-accent-dark' },
  en_proceso: { bg: 'bg-gold/20', text: 'text-gold' },
  vista_previa: { bg: 'bg-sage/15', text: 'text-sage' },
  completado: { bg: 'bg-stone-800/15', text: 'text-stone-900' },
  rechazado: { bg: 'bg-stone-400/20', text: 'text-stone-700' },
};

export function StatusBadge({ status }: { status: CommissionStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <View className={`rounded-full px-2.5 py-1 ${style.bg}`}>
      <Text className={`text-[11px] font-semibold uppercase ${style.text}`}>{STATUS_LABELS[status]}</Text>
    </View>
  );
}
