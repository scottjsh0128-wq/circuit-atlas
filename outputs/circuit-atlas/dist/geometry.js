// Display-only transforms. Cadence orientation and electrical connectivity are unchanged.
export function orientation(layout = {}) {
  const rotation = Number.isFinite(layout.rotation) ? ((Math.round(layout.rotation / 90) * 90) % 360 + 360) % 360 : 0;
  return { rotation, mirrored: layout.mirrored === true };
}

export function changeOrientation(layout, action) {
  const { rotation, mirrored } = orientation(layout);
  if (action === 'rotate') return { ...layout, rotation: (rotation + 90) % 360, mirrored };
  // A horizontal reflection in screen coordinates: F R(theta) = R(-theta) F.
  if (action === 'mirror') return { ...layout, rotation: (360 - rotation) % 360, mirrored: !mirrored };
  throw new Error('Unknown orientation action');
}

export function nodeMatrix(layout, width, height) {
  const { rotation, mirrored } = orientation(layout);
  const [cos, sin] = [[1, 0], [0, 1], [-1, 0], [0, -1]][rotation / 90];
  const sign = mirrored ? -1 : 1;
  const a = cos * sign, b = sin * sign, c = -sin, d = cos;
  const cx = width / 2, cy = height / 2;
  return [a, b, c, d, layout.x + cx - a * cx - c * cy, layout.y + cy - b * cx - d * cy];
}

export function transformPoint(matrix, x, y) {
  const [a, b, c, d, e, f] = matrix;
  return { x: a * x + c * y + e, y: b * x + d * y + f };
}

export function nodeBounds(layout, width, height) {
  const m = nodeMatrix(layout, width, height);
  const points = [[0, 0], [width, 0], [0, height], [width, height]].map(([x, y]) => transformPoint(m, x, y));
  return { minX: Math.min(...points.map(p => p.x)), minY: Math.min(...points.map(p => p.y)), maxX: Math.max(...points.map(p => p.x)), maxY: Math.max(...points.map(p => p.y)) };
}
