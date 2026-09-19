import { useMemo } from 'react';
import { useWindowDimensions } from 'react-native';
import Svg, { Circle, Defs, Line, Pattern, Rect } from 'react-native-svg';

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

// Roughly one stain per 9000px² and one grain streak per 12000px² —
// tuned so a phone screen gets a few dozen of each without feeling busy.
const STAIN_DENSITY = 1 / 9000;
const GRAIN_DENSITY = 1 / 12000;

// A rawer, worn-surface texture: coffee-toned stains and loose grain
// streaks, more "well-used studio table" than "clean paper" — closer
// to a paint palette, a guitar body, or a clay jug than to office
// stationery. Unlike PaperTexture, this scatters elements once across
// the whole given area instead of repeating a small tile, so it never
// reads as an obvious, mechanical pattern.
export function RusticTexture({
  width,
  height,
  opacity = 1,
}: {
  width?: number;
  height?: number;
  opacity?: number;
}) {
  const window = useWindowDimensions();
  const resolvedWidth = width ?? window.width;
  const resolvedHeight = height ?? window.height;

  const { stains, grainLines } = useMemo(() => {
    let seed = 7;
    const random = () => {
      seed = (seed * 9301 + 49297) % 233280;
      return seed / 233280;
    };
    const area = resolvedWidth * resolvedHeight;
    const stainCount = Math.max(6, Math.round(area * STAIN_DENSITY));
    const grainCount = Math.max(6, Math.round(area * GRAIN_DENSITY));

    const stains = Array.from({ length: stainCount }, () => ({
      cx: random() * resolvedWidth,
      cy: random() * resolvedHeight,
      r: 9 + random() * 24,
      opacity: 0.05 + random() * 0.05,
    }));
    const grainLines = Array.from({ length: grainCount }, () => {
      const x = random() * resolvedWidth;
      const y = random() * resolvedHeight;
      const length = 16 + random() * 36;
      const angle = random() * Math.PI;
      return {
        x1: x,
        y1: y,
        x2: x + Math.cos(angle) * length,
        y2: y + Math.sin(angle) * length,
        opacity: 0.08 + random() * 0.08,
        strokeWidth: 0.8 + random() * 0.8,
      };
    });
    return { stains, grainLines };
  }, [resolvedWidth, resolvedHeight]);

  return (
    <Svg
      pointerEvents="none"
      width={resolvedWidth}
      height={resolvedHeight}
      opacity={opacity}
      style={{ position: 'absolute', top: 0, left: 0 }}>
      {stains.map((stain, index) => (
        <Circle
          key={`stain-${index}`}
          cx={stain.cx}
          cy={stain.cy}
          r={stain.r}
          fill="#6f4e2f"
          opacity={stain.opacity}
        />
      ))}
      {grainLines.map((line, index) => (
        <Line
          key={`grain-${index}`}
          x1={line.x1}
          y1={line.y1}
          x2={line.x2}
          y2={line.y2}
          stroke="#4a3117"
          strokeWidth={line.strokeWidth}
          strokeLinecap="round"
          opacity={line.opacity}
        />
      ))}
    </Svg>
  );
}
