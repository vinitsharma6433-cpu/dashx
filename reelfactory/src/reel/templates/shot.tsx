import {all, chain, easeInOutQuad, easeInQuad, easeOutQuad, linear, waitFor} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import {makeBackground} from '../art/background';
import {makeBall, makeBat, makeBurst, makeChar} from '../art/characters';
import {shake} from '../art/helpers';
import {GROUND, S, gasp, lookAt, pickWho, place, pickBool} from './common';
import type {Template} from './types';

/**
 * shot: the batter swings, the ball flies high and gets small (perspective), camera shake on the hit.
 * params: batter (who, default sachin), watcher (who, default surya)
 */
export const shot: Template = function* (world, d, params): ThreadGenerator {
  const batterWho = pickWho(params, 'batter', 'sachin');
  const watcherWho = pickWho(params, 'watcher', 'surya');

  world.add(makeBackground(pickBool(params, 'sunset', false)));
  const batter = makeChar(batterWho);
  const watcher = makeChar(watcherWho);
  place(world, batter, -250, GROUND, S, false);
  place(world, watcher, 400, GROUND, S, true);

  const bat = makeBat();
  batter.handR.add(bat);
  batter.armR.rotation(-35);
  batter.armL.rotation(-35);
  bat.rotation(55);
  lookAt(batter, 6, 0);
  lookAt(watcher, -4, 0);

  const contact: [number, number] = [70, 150];
  const ball = makeBall(46);
  ball.position([600, 40]);
  const burst = makeBurst();
  burst.position(contact);
  world.add(ball);
  world.add(burst);

  const hit = 1.45;
  yield* all(
    // batter: wind up, then a fast swing at the hit time
    chain(
      waitFor(0.2),
      all(
        batter.armR.rotation(30, 0.9, easeInOutQuad),
        batter.armL.rotation(30, 0.9, easeInOutQuad),
        bat.rotation(-70, 0.9, easeInOutQuad),
        batter.body.rotation(-6, 0.9, easeInOutQuad),
      ),
      waitFor(hit - 0.2 - 0.9 - 0.2),
      all(
        batter.armR.rotation(-75, 0.2, easeInQuad),
        batter.armL.rotation(-75, 0.2, easeInQuad),
        bat.rotation(185, 0.2, easeInQuad),
        batter.body.rotation(8, 0.2, easeInQuad),
      ),
    ),
    // ball: arrives with one bounce, then flies up and shrinks
    chain(
      waitFor(0.3),
      all(
        ball.x(contact[0], hit - 0.3, linear),
        chain(
          ball.y(330, 0.55, easeInQuad),
          ball.y(contact[1], hit - 0.3 - 0.55, easeOutQuad),
        ),
      ),
      all(
        ball.x(240, 2.6, easeOutQuad),
        ball.y(-800, 2.6, easeOutQuad),
        ball.scale(0.22, 2.6, linear),
      ),
    ),
    // hit: burst + camera shake
    chain(
      waitFor(hit),
      all(
        burst.opacity(1, 0.05),
        burst.scale(1.3, 0.3, easeOutQuad),
        chain(waitFor(0.15), burst.opacity(0, 0.2)),
        shake(world, 16, 8, 0.045),
      ),
    ),
    // the watcher looks up with an open mouth
    chain(
      waitFor(hit + 0.1),
      all(
        gasp(watcher, 0.2),
        watcher.pupilL.y(-10, 0.2),
        watcher.pupilR.y(-10, 0.2),
        watcher.head.rotation(-6, 0.3),
      ),
    ),
    waitFor(d),
  );
};
