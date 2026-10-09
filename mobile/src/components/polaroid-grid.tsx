import { Image } from 'expo-image';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Animated, { FadeIn } from 'react-native-reanimated';

import { colors, NOTE_SHADOW } from '@/theme';

export type PolaroidItem = { id: string; image: string; caption?: string };

type Columns = 1 | 2 | 3;
const COLUMN_OPTIONS: Columns[] = [1, 2, 3];

// Proporciones de una Polaroid 600 real: marco de 88 x 107 mm con la foto
// cuadrada de 79 mm. Los lados y el borde de arriba son finos y el de
// abajo casi cuatro veces mas grueso, que es lo que la hace reconocible.
const SIDE_RATIO = 4.5 / 88;
const TOP_RATIO = 6 / 88;
const BOTTOM_RATIO = 22 / 88;

// Separacion entre polaroids segun la cantidad de columnas. La vertical
// deja lugar para la cinta, que sobresale por arriba de cada foto.
const COLUMN_GAP: Record<Columns, number> = { 1: 0, 2: 18, 3: 12 };
const ROW_GAP: Record<Columns, number> = { 1: 34, 2: 30, 3: 24 };
// Con una sola columna la foto no ocupa todo el ancho: asi se ve el
// corcho a los lados y sigue pareciendo pegada, no un banner.
const SINGLE_COLUMN_WIDTH = 0.84;

// Inclinacion y caida fijas por posicion: cada foto queda un poco torcida
// como si la hubieran pegado a mano, pero no cambia entre renders.
const TILTS = [-2.4, 1.6, -1.1, 2.2, -1.8, 0.9, 2.6, -0.7, 1.3];
const TILT_SCALE: Record<Columns, number> = { 1: 0.6, 2: 1, 3: 1.2 };
const DROPS = [0, 7, 3, 9, 2, 6, 4, 0, 8];
// La letra no crece con la foto: mismo tamano en una o dos columnas, y
// hasta dos lineas para que la frase se lea. En tres columnas la franja
// queda muy chica y la foto va sin texto, como muchas polaroids reales.
const CAPTION_SIZE = 13;
const CAPTION_LINE = 16;

function ColumnsGlyph({ count, color }: { count: Columns; color: string }) {
  return (
    <View style={{ flexDirection: 'row', gap: 2, width: 16, height: 14 }}>
      {Array.from({ length: count }).map((_, index) => (
        <View key={index} style={{ flex: 1, borderRadius: 1.5, backgroundColor: color }} />
      ))}
    </View>
  );
}

function Polaroid({
  item,
  index,
  width,
  columns,
  tapeColor,
  onPress,
}: {
  item: PolaroidItem;
  index: number;
  width: number;
  columns: Columns;
  tapeColor: string;
  onPress: () => void;
}) {
  const side = width * SIDE_RATIO;
  const top = width * TOP_RATIO;
  const bottom = width * BOTTOM_RATIO;
  const photoSize = width - side * 2;
  const tilt = TILTS[index % TILTS.length] * TILT_SCALE[columns];
  const drop = columns === 1 ? 0 : DROPS[index % DROPS.length];
  const tapeWidth = width * 0.36;
  const tapeHeight = Math.min(Math.max(width * 0.1, 12), 26);

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="imagebutton"
      accessibilityLabel={item.caption ?? 'Ver obra'}
      style={[NOTE_SHADOW, { width, marginTop: drop, transform: [{ rotate: `${tilt}deg` }] }]}>
      <View
        style={{
          backgroundColor: colors.sand[50],
          borderRadius: 2,
          paddingTop: top,
          paddingHorizontal: side,
          height: top + photoSize + bottom,
        }}>
        <Image
          source={{ uri: item.image }}
          contentFit="cover"
          transition={200}
          style={{
            width: photoSize,
            height: photoSize,
            backgroundColor: colors.sand[200],
            borderWidth: StyleSheet.hairlineWidth,
            borderColor: 'rgba(32,29,26,0.14)',
          }}
        />
        {columns < 3 && item.caption ? (
          <View style={{ height: bottom, justifyContent: 'center', paddingHorizontal: 4 }}>
            <Text
              numberOfLines={2}
              className="text-center font-serif italic text-ink-700"
              style={{ fontSize: CAPTION_SIZE, lineHeight: CAPTION_LINE }}>
              {item.caption}
            </Text>
          </View>
        ) : null}
      </View>
      {/* Cinta translucida del color del artista, apenas torcida */}
      <View
        pointerEvents="none"
        style={{
          position: 'absolute',
          top: -tapeHeight / 2,
          left: (width - tapeWidth) / 2,
          width: tapeWidth,
          height: tapeHeight,
          backgroundColor: tapeColor,
          opacity: 0.55,
          transform: [{ rotate: `${index % 2 === 0 ? -4 : 3}deg` }],
        }}
      />
    </Pressable>
  );
}

// Portafolio como polaroids pegadas al corcho, con selector de 1, 2 o 3
// columnas. Mide su propio ancho para no depender del padding de la
// pantalla que lo usa.
export function PolaroidGrid({
  items,
  tapeColor,
  onOpen,
}: {
  items: PolaroidItem[];
  tapeColor: string;
  onOpen: (item: PolaroidItem) => void;
}) {
  const [columns, setColumns] = useState<Columns>(2);
  const [containerWidth, setContainerWidth] = useState(0);

  if (items.length === 0) return null;

  const itemWidth =
    columns === 1
      ? containerWidth * SINGLE_COLUMN_WIDTH
      : (containerWidth - COLUMN_GAP[columns] * (columns - 1)) / columns;

  return (
    <View className="py-4" onLayout={(event) => setContainerWidth(event.nativeEvent.layout.width)}>
      <View className="mb-6 flex-row self-end rounded-full bg-ink p-1">
        {COLUMN_OPTIONS.map((option) => (
          <Pressable
            key={option}
            onPress={() => setColumns(option)}
            accessibilityRole="button"
            accessibilityState={{ selected: columns === option }}
            accessibilityLabel={option === 1 ? 'Ver en 1 columna' : `Ver en ${option} columnas`}
            className={
              columns === option
                ? 'h-7 w-10 items-center justify-center rounded-full bg-sand-50'
                : 'h-7 w-10 items-center justify-center rounded-full'
            }>
            <ColumnsGlyph
              count={option}
              color={columns === option ? colors.ink.DEFAULT : colors.sand[200]}
            />
          </Pressable>
        ))}
      </View>

      {containerWidth > 0 && (
        <Animated.View
          key={columns}
          entering={FadeIn.duration(180)}
          style={{
            flexDirection: 'row',
            flexWrap: 'wrap',
            justifyContent: columns === 1 ? 'center' : 'flex-start',
            // Sin esto cada polaroid se estira al alto de la mas baja de su
            // fila (por la caida escalonada) y la sombra dibuja esa caja
            // estirada debajo del papel.
            alignItems: 'flex-start',
            columnGap: COLUMN_GAP[columns],
            rowGap: ROW_GAP[columns],
          }}>
          {items.map((item, index) => (
            <Polaroid
              key={item.id}
              item={item}
              index={index}
              width={itemWidth}
              columns={columns}
              tapeColor={tapeColor}
              onPress={() => onOpen(item)}
            />
          ))}
        </Animated.View>
      )}
    </View>
  );
}
