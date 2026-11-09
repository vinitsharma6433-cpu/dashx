import {all, chain, easeInOutSine, easeInQuad, easeOutQuad, linear, waitFor} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import {makeBackground} from '../art/background';
import {makeBall, makeBurst, makeChair, makeChar} from '../art/characters';
import {posIn} from '../art/helpers';
import {GROUND, S, gasp, lookAt, pickWho, pickWhoList, place, pickBool} from './common';
import type {Template} from './types';

/**
 * catch: the ball comes down, the seated catcher snatches it one-handed, the two watchers freeze open-mouthed.
 * params: catcher (who, default dadaji), watchers (2 names, default [sachin, surya])
 */
export const catchBall: Template = function* (world, d, params): ThreadGenerator {
  const catcherWho = pickWho(params, 'catcher', 'dadaji');
  const [w0Who, w1Who] = pickWhoList(params, 'watchers', ['sachin', 'surya']);

  world.add(makeBackground(pickBool(params, 'sunset', false)));
  const w0 = makeChar(w0Who);
  const w1 = makeChar(w1Who);
  const catcher = makeChar(catcherWho, {legLen: 70});
  const chair = makeChair(48);
  chair.position([300, GROUND]);
  chair.scale(S);
  world.add(chair);
  place(world, catcher, 300, GROUND, S, true);
  place(world, w0, -330, GROUND, S, false);
  place(world, w1, -90, GROUND, S, false);
  lookAt(w0, 4, -10);
  lookAt(w1, 4, -10);
  lookAt(catcher, -5, -8);
  w0.head.rotation(-6);
  w1.head.rotation(-6);

  // Where the raised hand ends up (read it, then put the arm back down).
  catcher.armR.rotation(-150);
  const target = posIn(catcher.handR, world);
  catcher.armR.rotation(0);

  const ball = makeBall(46);
  ball.position([60, -900]);
  ball.scale(0.22);
  const burst = makeBurst();
  burst.position([target.x, target.y]);
  world.add(ball);
  world.add(burst);

  const catchAt = 2.6;
  yield* all(
    // the ball falls and grows (it gets closer)
    chain(
      waitFor(0.2),
      all(
        ball.x(target.x, catchAt - 0.2, linear),
        ball.y(target.y, catchAt - 0.2, easeInQuad),
        ball.scale(1, catchAt - 0.2, linear),
      ),
      ball.scale(1.3, 0.1, easeOutQuad),
      ball.scale(1, 0.15, easeInOutSine),
    ),
    // the catcher raises an arm, catches, nods
    chain(
      waitFor(1.4),
      catcher.armR.rotation(-150, 0.9, easeOutQuad),
      waitFor(0.3),
      catcher.head.rotation(-7, 0.25, easeInOutSine),
      catcher.head.rotation(0, 0.25, easeInOutSine),
    ),
    chain(
      waitFor(catchAt),
      all(burst.opacity(1, 0.05), burst.scale(1.2, 0.3, easeOutQuad), chain(waitFor(0.15), burst.opacity(0, 0.2))),
    ),
    // watchers freeze with open mouths
    chain(
      waitFor(catchAt),
      all(
        gasp(w0, 0.15),
        gasp(w1, 0.15),
        w0.pupilL.position([-26, -2], 0.15),
        w0.pupilR.position([26, -2], 0.15),
        w1.pupilL.position([-26, -2], 0.15),
        w1.pupilR.position([26, -2], 0.15),
        w0.head.rotation(0, 0.2),
        w1.head.rotation(0, 0.2),
        w0.armL.rotation(12, 0.2),
        w1.armR.rotation(-12, 0.2),
      ),
    ),
    waitFor(d),
  );
};
