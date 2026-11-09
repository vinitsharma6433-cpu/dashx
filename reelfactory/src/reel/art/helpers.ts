import type {Node} from '@revideo/2d';
import {Vector2, easeInOutSine} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

export const FONT = "'Noto Sans Devanagari', Arial, sans-serif";

/** Swing a node's rotation +amp / -amp / +amp ... (legs and arms while running). */
export function* swing(
  node: Node,
  amp: number,
  half: number,
  count: number,
  phase = 1,
): ThreadGenerator {
  for (let i = 0; i < count; i++) {
    yield* node.rotation(phase * amp * (i % 2 === 0 ? 1 : -1), half, easeInOutSine);
  }
}

/** Small up/down hop of a node (running bob, celebration jumps). */
export function* hop(
  node: Node,
  baseY: number,
  height: number,
  half: number,
  count: number,
): ThreadGenerator {
  for (let i = 0; i < count; i++) {
    yield* node.y(baseY - height, half, easeInOutSine);
    yield* node.y(baseY, half, easeInOutSine);
  }
}

/** Camera shake: jitter a node around (0, 0) with fading strength. */
export function* shake(
  node: Node,
  amp: number,
  steps: number,
  step: number,
): ThreadGenerator {
  for (let i = 0; i < steps; i++) {
    const s = i % 2 === 0 ? 1 : -1;
    const k = 1 - i / steps;
    yield* node.position([s * amp * k, -s * amp * 0.5 * k], step);
  }
  yield* node.position([0, 0], step);
}

/** Where `target` is, expressed in the coordinates of `parent`. */
export function posIn(target: Node, parent: Node): Vector2 {
  const abs = target.absolutePosition();
  const p = new DOMPoint(abs.x, abs.y).matrixTransform(parent.worldToLocal());
  return new Vector2(p.x, p.y);
}
