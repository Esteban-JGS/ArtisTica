import { LiquidGlassView } from '@sbaiahmed1/react-native-blur';
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

type GlassButtonVariant = 'primary' | 'glass' | 'ghost';

export function GlassButton({
  variant,
  icon,
  label,
  onPress,
  style,
}: {
  variant: GlassButtonVariant;
  icon: ReactNode;
  label: string;
  onPress: () => void;
  style?: StyleProp<ViewStyle>;
}) {
  if (variant === 'primary') {
    return (
      <Pressable onPress={onPress} style={style}>
        {({ pressed }) => (
          <View style={[styles.primary, pressed && styles.primaryPressed]}>
            {icon}
            <Text style={styles.primaryLabel}>{label}</Text>
          </View>
        )}
      </Pressable>
    );
  }

  if (variant === 'glass') {
    return (
      <Pressable onPress={onPress} style={[styles.glassWrap, style]}>
        {({ pressed }) => (
          <LiquidGlassView
            glassType="clear"
            glassTintColor="#ffffff"
            glassOpacity={0.4}
            isInteractive={false}
            style={[styles.glass, pressed && styles.glassPressed]}>
            <View style={styles.glassContent}>
              {icon}
              <Text style={styles.glassLabel}>{label}</Text>
            </View>
          </LiquidGlassView>
        )}
      </Pressable>
    );
  }

  return (
    <Pressable onPress={onPress} style={style}>
      {({ pressed }) => (
        <View style={[styles.ghost, pressed && styles.ghostPressed]}>
          <Text style={styles.ghostLabel}>{label}</Text>
          {icon}
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  primary: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#c2653b',
    borderRadius: 19,
    paddingVertical: 16,
    paddingHorizontal: 20,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.22)',
    shadowColor: '#c2653b',
    shadowOpacity: 0.5,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 10 },
    elevation: 10,
  },
  primaryPressed: {
    backgroundColor: '#a1512d',
  },
  primaryLabel: {
    fontSize: 15.5,
    fontWeight: '600',
    color: '#ffffff',
  },
  glassWrap: {
    flex: 1,
  },
  glass: {
    overflow: 'hidden',
    borderRadius: 17,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.3)',
  },
  glassPressed: {
    opacity: 0.85,
  },
  glassContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    paddingHorizontal: 12,
  },
  glassLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ffffff',
  },
  ghost: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 11,
    paddingHorizontal: 20,
  },
  ghostPressed: {
    opacity: 0.6,
  },
  ghostLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.82)',
  },
});
