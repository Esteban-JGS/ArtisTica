import { Image } from 'expo-image';
import { useEffect, useMemo } from 'react';
import { View, useWindowDimensions } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

const TILE_GAP = 10;
const TILE_RADIUS = 16;
const PHOTO_WIDTH = 420;
const PHOTO_HEIGHT = 560;
const PHOTO_ASPECT_RATIO = PHOTO_HEIGHT / PHOTO_WIDTH;

const COLUMN_PHOTOS = [
  [
    '1493106641515-6b5631de4bb9', // torno
    '1465847899084-d164df4dedc6', // violines
    '1578926375605-eaf7559b1458', // óleo río
    '1522202176988-66273c2fd55f', // personas conversando
  ],
  [
    '1510915361894-db8b60106cb1', // guitarra
    '1565193566173-7a0ee3dbe261', // cerámica
    '1547153760-18fc86324498', // danza
    '1515405295579-ba7b45403062', // pintura abstracta
  ],
  [
    '1482160549825-59d1b23cb208', // arte urbano
    '1517048676732-d65bc937f952', // manos dibujando
    '1518834107812-67b0b7c58434', // danza b/n
    '1531384441138-2736e62e0919', // retrato músico
  ],
];

const COLUMN_DIRECTIONS: Array<1 | -1> = [1, -1, 1];
const COLUMN_DURATIONS = [26000, 21000, 31000];
const ROTATION_DEG = -7;
const OVERSCAN = 1.16;

function buildTiles(photoIds: string[], tileHeight: number) {
  return photoIds.map((id) => ({
    id,
    height: tileHeight,
    uri: `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=${PHOTO_WIDTH}&h=${PHOTO_HEIGHT}&q=70`,
  }));
}

function GalleryColumn({
  photoIds,
  direction,
  duration,
  width,
}: {
  photoIds: string[];
  direction: 1 | -1;
  duration: number;
  width: number;
}) {
  const tileHeight = Math.round(width * PHOTO_ASPECT_RATIO);
  const tiles = useMemo(() => buildTiles(photoIds, tileHeight), [photoIds, tileHeight]);
  const setHeight = useMemo(
    () => tiles.reduce((sum, tile) => sum + tile.height + TILE_GAP, 0),
    [tiles],
  );
  const translateY = useSharedValue(direction === 1 ? -setHeight : 0);

  useEffect(() => {
    translateY.value = direction === 1 ? -setHeight : 0;
    translateY.value = withRepeat(
      withTiming(direction === 1 ? 0 : -setHeight, {
        duration,
        easing: Easing.linear,
      }),
      -1,
      false,
    );
  }, [direction, duration, setHeight, translateY]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }],
  }));

  const renderTiles = [...tiles, ...tiles];

  return (
    <View style={{ width, overflow: 'hidden' }}>
      <Animated.View style={[{ gap: TILE_GAP }, animatedStyle]}>
        {renderTiles.map((tile, index) => (
          <Image
            key={`${tile.id}-${index}`}
            source={{ uri: tile.uri }}
            style={{ width, height: tile.height, borderRadius: TILE_RADIUS }}
            contentFit="cover"
          />
        ))}
      </Animated.View>
    </View>
  );
}

export function LoginGallery() {
  const { width, height } = useWindowDimensions();
  const columnCount = COLUMN_PHOTOS.length;
  const overscanWidth = width * OVERSCAN;
  const overscanHeight = height * OVERSCAN;
  const columnWidth = (overscanWidth - TILE_GAP * (columnCount - 1)) / columnCount;

  return (
    <View
      pointerEvents="none"
      style={{ position: 'absolute', width: '100%', height: '100%', overflow: 'hidden' }}>
      <View
        style={{
          position: 'absolute',
          width: overscanWidth,
          height: overscanHeight,
          left: (width - overscanWidth) / 2,
          top: (height - overscanHeight) / 2,
          flexDirection: 'row',
          gap: TILE_GAP,
          transform: [{ rotate: `${ROTATION_DEG}deg` }],
        }}>
        {COLUMN_PHOTOS.map((photoIds, index) => (
          <GalleryColumn
            key={index}
            photoIds={photoIds}
            direction={COLUMN_DIRECTIONS[index]}
            duration={COLUMN_DURATIONS[index]}
            width={columnWidth}
          />
        ))}
      </View>
    </View>
  );
}
