import { useMemo } from 'react';
import { useWindowDimensions } from 'react-native';
import Svg, { Circle, Defs, Pattern, Rect } from 'react-native-svg';

const TILE_SIZE = 64;
const SPECKS_PER_TILE = 7;

// A barely-there paper-grain speckle, tiled across the screen. Meant to
// sit behind flat cream backgrounds so they read as textured paper
// instead of a cold, perfectly flat color.
export function PaperTexture() {
  const { width, height } = useWindowDimensions();

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
      width={width}
      height={height}
      style={{ position: 'absolute', top: 0, left: 0 }}>
      <Defs>
        <Pattern
          id="paperGrain"
          width={TILE_SIZE}
          height={TILE_SIZE}
          patternUnits="userSpaceOnUse">
          {specks.map((speck, index) => (
            <Circle key={index} cx={speck.cx} cy={speck.cy} r={speck.r} fill="#8b7355" opacity={0.35} />
          ))}
        </Pattern>
      </Defs>
      <Rect width={width} height={height} fill="url(#paperGrain)" />
    </Svg>
  );
}
