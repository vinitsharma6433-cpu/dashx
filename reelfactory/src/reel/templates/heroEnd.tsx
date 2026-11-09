import {Img} from '@revideo/2d';
import {all, chain, createRef, easeOutBounce, easeOutQuad, waitFor} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import {makeBackground} from '../art/background';
import {makeChar} from '../art/characters';
import {hop} from '../art/helpers';
import {pickWhoList, place} from './common';
import type {Template} from './types';

/**
 * hero-end: sunset background, the big DASHX ball bounces in, logo fades in, three characters cheer.
 * The reel builder adds the end card over the last 2.5 s of this scene.
 * params: cast (3 names: left, middle, right; default [sachin, dadaji, surya])
 */
export const heroEnd: Template = function* (world, d, params, ctx): ThreadGenerator {
  const [leftWho, midWho, rightWho] = pickWhoList(params, 'cast', ['sachin', 'dadaji', 'surya']);

  world.add(makeBackground(true));
  const left = makeChar(leftWho);
  const mid = makeChar(midWho);
  const right = makeChar(rightWho);
  const y = 270;
  const s = 0.95;
  place(world, left, -320, y, s, false);
  place(world, right, 320, y, s, true);
  place(world, mid, 0, y, s, false);
  for (const c of [left, right, mid]) {
    c.mouth.size([46, 26]);
  }
  left.armL.rotation(150);
  left.armR.rotation(-150);
  right.armL.rotation(150);
  right.armR.rotation(-150);
  mid.armL.rotation(150);
  mid.armR.rotation(-150);

  const bigBall = createRef<Img>();
  const logo = createRef<Img>();
  world.add(
    <>
      <Img ref={bigBall} src={ctx.ball} width={460} y={-1100} />
      <Img ref={logo} src={ctx.logo} width={560} y={-650} opacity={0} />
    </>,
  );

  yield* all(
    chain(waitFor(0.3), all(bigBall().y(-370, 1.4, easeOutBounce), bigBall().rotation(360, 1.4, easeOutQuad))),
    chain(waitFor(0.9), logo().opacity(1, 0.5)),
    hop(left.node, y, 22, 0.25, 8),
    chain(waitFor(0.12), hop(mid.node, y, 22, 0.25, 8)),
    chain(waitFor(0.24), hop(right.node, y, 22, 0.25, 8)),
    waitFor(d),
  );
};
