import type {Node} from '@revideo/2d';
import type {ThreadGenerator} from '@revideo/core';

/** Brand files (urls) the reel builder passes to every template. */
export interface Ctx {
  logo: string;
  ball: string;
}

/** The "parameters" object of one scene in script.json. */
export type Params = Record<string, unknown>;

/**
 * A template draws one kind of scene into `world` and animates it for `d` seconds.
 * It reads its characters and texts from `params` (with defaults), so one template
 * can be reused in many reels.
 */
export type Template = (world: Node, d: number, params: Params, ctx: Ctx) => ThreadGenerator;
