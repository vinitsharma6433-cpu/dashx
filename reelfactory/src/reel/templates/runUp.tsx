import {Node} from '@revideo/2d';
import {all, chain, createRef, easeInOutQuad, easeInQuad, easeOutSine, linear, waitFor} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import {makeBackground} from '../art/background';
import {makeBall, makeBat, makeChar} from '../art/characters';
import {hop, posIn, swing} from '../art/helpers';
import {GROUND, S, lookAt, pickWho, place, pickBool} from './common';
import type {Template} from './types';

/**
 * run-up: the bowler runs in (legs swinging, ball in hand) while the batter waits with the bat.
 * params: batter (who, default sachin), bowler (who, default surya)
 */
export const runUp: Template = function* (world, d, params): ThreadGenerator {
  const batterWho = pickWho(params, 'batter', 'sachin');
  const bowlerWho = pickWho(params, 'bowler', 'surya');
  // near: the bowler starts on screen (dialogue reels, so a talking bowler is visible); default is the long run from off screen
  const near = pickBool(params, 'near', false);

  world.add(makeBackground(pickBool(params, 'sunset', false)));
  const batter = makeChar(batterWho);
  const bowler = makeChar(bowlerWho);
  place(world, batter, -250, GROUND, S, false);
  place(world, bowler, near ? 430 : 650, GROUND, S, true);

  // The batter waits with the bat.
  const bat = makeBat();
  batter.handR.add(bat);
  bat.rotation(55);
  batter.armR.rotation(-35);
  batter.armL.rotation(-35);
  lookAt(batter, 6, 0);

  // The bowler holds the ball.
  const inHand = makeBall(40);
  bowler.handR.add(inHand);
  lookAt(bowler, 6, 0);

  const run = 2.7; // seconds of running
  const half = 0.27;
  const steps = Math.round(run / half);
  const flying = createRef<Node>();

  yield* all(
    chain(waitFor(0.1), bowler.node.x(160, run, easeOutSine)),
    swing(bowler.legL, 42, half, steps),
    swing(bowler.legR, 42, half, steps, -1),
    swing(bowler.armL, 48, half, steps, -1),
    hop(bowler.node, GROUND, 9, half / 2, steps),
    chain(
      waitFor(0.1 + run),
      all(bowler.legL.rotation(0, 0.2), bowler.legR.rotation(0, 0.2), bowler.armL.rotation(0, 0.2)),
      // bowling arm swings over the head
      bowler.armR.rotation(-360, 0.7, easeInOutQuad),
      (function* () {
        const at = posIn(bowler.handR, world);
        inHand.remove();
        world.add(<Node ref={flying} position={at} />);
        flying().add(makeBall(46));
        yield* all(flying().x(at.x - 220, 0.35, linear), flying().y(at.y + 60, 0.35, easeInQuad));
      })(),
    ),
    waitFor(d),
  );
};
