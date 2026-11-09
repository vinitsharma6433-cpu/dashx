import type {Node} from '@revideo/2d';
import {all, easeInOutSine} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import type {Char} from '../art/characters';
import {CHARACTERS} from '../templateInfo';
import type {Who} from '../templateInfo';
import type {Params} from './types';

export const S = 1.15; // character scale

/** The characters placed in the scene being drawn (by name). The reel looks the speaker up here to animate the mouth. */
export const LIVE: Partial<Record<string, Char>> = {};
export const GROUND = 340; // y of the feet in most scenes (leaves room for the subtitle below)

export function place(world: Node, c: Char, x: number, y: number, s: number, flip: boolean) {
  const k = s * (c.height ?? 1); // small people (Golu) and big people (the coach) get their own size
  if (c.who) LIVE[c.who] = c;
  c.node.position([x, y]);
  c.node.scale([flip ? -k : k, k]);
  world.add(c.node);
}

/** Gentle breathing: the torso grows and shrinks a little. */
export function* breathe(c: Char, seconds: number): ThreadGenerator {
  for (let i = 0; i < Math.floor(seconds); i++) {
    yield* c.body.scale([1, 1.03], 0.5, easeInOutSine);
    yield* c.body.scale([1, 1], 0.5, easeInOutSine);
  }
}

export function lookAt(c: Char, dx: number, dy: number) {
  c.pupilL.position([-26 + dx, -2 + dy]);
  c.pupilR.position([26 + dx, -2 + dy]);
}

/** Surprise: open mouth, raised eyebrows. */
export function* gasp(c: Char, time: number): ThreadGenerator {
  yield* all(c.mouth.size([30, 38], time), c.browL.y(-40, time), c.browR.y(-40, time));
}

// ---- reading parameters from script.json (with defaults) ----

function isWho(v: unknown): v is Who {
  return typeof v === 'string' && (CHARACTERS as readonly string[]).includes(v);
}

export function pickWho(params: Params, key: string, fallback: Who): Who {
  const v = params[key];
  if (v === undefined) return fallback;
  if (!isWho(v)) throw new Error(`params.${key} must be one of ${CHARACTERS.join(', ')}`);
  return v;
}

export function pickWhoList(params: Params, key: string, fallback: Who[]): Who[] {
  const v = params[key];
  if (v === undefined) return fallback;
  if (!Array.isArray(v) || v.length !== fallback.length || !v.every(isWho)) {
    throw new Error(`params.${key} must be a list of ${fallback.length} names from ${CHARACTERS.join(', ')}`);
  }
  return v as Who[];
}

export function pickText(params: Params, key: string, fallback: string): string {
  const v = params[key];
  if (v === undefined) return fallback;
  if (typeof v !== 'string') throw new Error(`params.${key} must be text`);
  return v;
}

export function pickBool(params: Params, key: string, fallback: boolean): boolean {
  const v = params[key];
  if (v === undefined) return fallback;
  if (typeof v !== 'boolean') throw new Error(`params.${key} must be true or false`);
  return v;
}
