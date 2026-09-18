export function buildNotchCutoutPath({
  width,
  notchRadius,
  notchWidth,
}: {
  width: number;
  notchRadius: number;
  notchWidth: number;
}) {
  const cx = width / 2;
  const flareX = notchWidth / 2;

  return `
    M${cx - flareX},0
    C${cx - flareX * 0.5},0 ${cx - notchRadius},${notchRadius} ${cx},${notchRadius}
    C${cx + notchRadius},${notchRadius} ${cx + flareX * 0.5},0 ${cx + flareX},0
    Z
  `;
}
