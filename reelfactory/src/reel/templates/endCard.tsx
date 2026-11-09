import {Img, Node, Rect, Txt} from '@revideo/2d';
import {all, chain, createRef, easeOutBack, easeOutBounce, easeOutQuad, waitFor} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import {FONT} from '../art/helpers';
import type {Template} from './types';

/**
 * end-card: the one closing card of a reel (max 5 s, ONE short spoken line).
 * The DASHX name is shown once, as the logo. Logo and ball photo are on screen from frame 0 (the ball settles
 * with a bounce), then the maker line fades in
 * ("Nav Durga Sports, Meerut", without repeating the brand word).
 * params: none. Use as the LAST scene of a reel; it works after any other templates.
 */
export const endCard: Template = function* (world, d, _params, ctx): ThreadGenerator {
  const logo = createRef<Img>();
  const ball = createRef<Img>();
  const maker = createRef<Node>();

  world.add(
    <>
      <Rect size={[1080, 1920]} fill={'#0b1220'} />
      <Img ref={logo} src={ctx.logo} width={700} y={-470} scale={0.85} />
      <Img ref={ball} src={ctx.ball} width={400} y={-330} />
      <Node ref={maker} opacity={0}>
        <Txt
          text={'Nav Durga Sports, Meerut'}
          fontFamily={FONT}
          fontWeight={700}
          fontSize={52}
          fill={'#ffffff'}
          y={205}
        />
        <Txt
          text={'Cricket Tennis Ball'}
          fontFamily={FONT}
          fontWeight={500}
          fontSize={42}
          fill={'#fbbf24'}
          y={280}
        />
      </Node>
    </>,
  );

  yield* all(
    logo().scale(1, 0.5, easeOutBack),
    all(ball().y(-120, 1.3, easeOutBounce), ball().rotation(360, 1.3, easeOutQuad)),
    chain(waitFor(1.5), maker().opacity(1, 0.5)),
    waitFor(d),
  );
};
