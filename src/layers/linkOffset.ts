export function getDirectionalLineOffset(
  _feature: GeoJSON.Feature,
  offsetPixels: number
): number {
  if (!offsetPixels) {
    return 0;
  }
  // deck.gl path offset is applied relative to the path direction, so using a
  // constant sign makes every link shift to the same side of its own heading.
  // Negative is the right-hand side for our current map rendering.
  return -offsetPixels;
}
