import {Img, Node, Rect, Txt} from '@revideo/2d';
import {all, chain, createRef, easeOutBack, waitFor} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import {FONT} from '../art/helpers';
import type {Template} from './types';

/** The call to action shown as text on the end card. The same sentence is spoken (Hindi) and subtitled. */
export const CTA_TEXT = 'Amazon, Flipkart ya Meesho par\nDASHX cricket tennis ball search karo';

/**
 * end-card: the one closing card of a reel (max 5 s, ONE short spoken line = the call to action).
 * The DASHX logo and the product photo (assets/store-images/, shown as they are: no stretching, no recolouring)
 * are on screen from the first frame, and the call to action appears as text at the same moment the voice says it.
 * The old end-card pictures (assets/dashx-logo.png, hero-ball.png) are still used when the store images are missing.
 * params: none. Use as the LAST scene of a reel; it works after any other templates.
 */
export const endCard: Template = function* (world, d, _params, ctx): ThreadGenerator {
  const logo = createRef<Img>();
  const photo = createRef<Rect>();
  const cta = createRef<Node>();

  world.add(
    <>
      <Rect size={[1080, 1920]} fill={'#000000'} />
      <Img ref={logo} src={ctx.endLogo ?? ctx.logo} width={520} y={-560} scale={0.9} />
      <Rect ref={photo} size={[440, 440]} y={-60} radius={36} clip scale={0.9} opacity={0}>
        <Img src={ctx.endPhoto ?? ctx.ball} width={440} />
      </Rect>
      <Node ref={cta} opacity={0}>
        <Txt
          text={CTA_TEXT}
          fontFamily={FONT}
          fontWeight={700}
          fontSize={46}
          lineHeight={62}
          fill={'#fbbf24'}
          textAlign={'center'}
          y={250}
        />
      </Node>
    </>,
  );

  yield* all(
    logo().scale(1, 0.5, easeOutBack),
    all(photo().opacity(1, 0.3), photo().scale(1, 0.5, easeOutBack)),
    chain(waitFor(0.25), cta().opacity(1, 0.3)),
    waitFor(d),
  );
};
