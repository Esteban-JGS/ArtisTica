import { useMemo } from 'react';
import { useWindowDimensions } from 'react-native';
import Svg, { Circle, Defs, Pattern, Rect } from 'react-native-svg';

const TILE_SIZE = 64;
const SPECKS_PER_TILE = 7;

// A paper-grain speckle, tiled to cover its container. Meant to sit
// behind flat cream backgrounds so they read as textured paper instead
// of a cold, perfectly flat color.
//
// `width`/`height` default to the window size (full-page background
// use). Pass a fixed, generously large size instead when using it
// inside a card — the pattern tiles seamlessly, so it doesn't need to
// match the card's real size exactly, and a wrapping `overflow:
// hidden` clips it to the card's rounded corners.
export function PaperTexture({
  width,
  height,
  speckOpacity = 0.35,
}: {
  width?: number;
  height?: number;
  speckOpacity?: number;
}) {
  const window = useWindowDimensions();
  const resolvedWidth = width ?? window.width;
  const resolvedHeight = height ?? window.height;

  const specks = useMemo(() => {
    let seed = 42;
    const random = () => {
      seed = (seed * 9301 + 49297) % 233280;
      return seed / 233280;
    };
    return Array.from({ length: SPECKS_PER_TILE }, () => ({
      cx: random() * TILE_SIZE,
      cy: random() * TILE_SIZE,
      r: 0.4 + random() * 0.7,
    }));
  }, []);

  return (
    <Svg
      pointerEvents="none"
      width={resolvedWidth}
      height={resolvedHeight}
      style={{ position: 'absolute', top: 0, left: 0 }}>
      <Defs>
        <Pattern
          id="paperGrain"
          width={TILE_SIZE}
          height={TILE_SIZE}
          patternUnits="userSpaceOnUse">
          {specks.map((speck, index) => (
            <Circle
              key={index}
              cx={speck.cx}
              cy={speck.cy}
              r={speck.r}
              fill="#8b7355"
              opacity={speckOpacity}
            />
          ))}
        </Pattern>
      </Defs>
      <Rect width={resolvedWidth} height={resolvedHeight} fill="url(#paperGrain)" />
    </Svg>
  );
}
