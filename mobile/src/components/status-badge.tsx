import { Text, View } from 'react-native';

export type CommissionStatus = 'Pendiente' | 'Negociando' | 'Pagado' | 'Entregado' | 'Liberado';

const STATUS_STYLES: Record<CommissionStatus, { bg: string; text: string }> = {
  Pendiente: { bg: 'bg-stone-400/20', text: 'text-stone-800' },
  Negociando: { bg: 'bg-accent/15', text: 'text-accent-dark' },
  Pagado: { bg: 'bg-gold/20', text: 'text-gold' },
  Entregado: { bg: 'bg-sage/15', text: 'text-sage' },
  Liberado: { bg: 'bg-stone-800/15', text: 'text-stone-900' },
};

export function StatusBadge({ status }: { status: CommissionStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <View className={`rounded-full px-2.5 py-1 ${style.bg}`}>
      <Text className={`text-[11px] font-semibold uppercase ${style.text}`}>{status}</Text>
    </View>
  );
}
