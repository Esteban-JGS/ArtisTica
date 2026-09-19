const VIEWBOX_WIDTH = 380;

// x-coordinates of the notch curve from the design spec (viewBox 380×104):
// M0,36 C73,36 112,36 133,32 C159,26 163,4 190,4 C217,4 221,26 247,32 C268,36 307,36 380,36
const CURVE_X = [0, 73, 112, 133, 159, 163, 190, 217, 221, 247, 268, 307, 380];

export function buildLiquidBarPaths(width: number, bodyHeight: number) {
  const scale = width / VIEWBOX_WIDTH;
  const [x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12] = CURVE_X.map(
    (value) => value * scale,
  );

  // The top edge of the glass material (used as a stroked highlight line).
  const edgePath = `M${x0},36 C${x1},36 ${x2},36 ${x3},32 C${x4},26 ${x5},4 ${x6},4 C${x7},4 ${x8},26 ${x9},32 C${x10},36 ${x11},36 ${x12},36`;

  // The material itself: everything below the curve, down to the bottom of
  // the bar. Used as a MaskedView mask so the notch is a real hole — nothing
  // is rendered there at all, letting whatever is behind the bar show
  // through sharp and unblurred.
  const materialPath = `${edgePath} L${x12},${bodyHeight} L0,${bodyHeight} Z`;

  return { edgePath, materialPath };
}
