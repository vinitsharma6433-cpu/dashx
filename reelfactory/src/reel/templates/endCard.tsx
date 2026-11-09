import {Img, Node, Rect, Txt} from '@revideo/2d';
import {all, chain, createRef, easeOutBack, waitFor} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import {FONT} from '../art/helpers';
import type {Template} from './types';

/** The call to action shown as text on the end card. The same sentence is spoken (Hindi) and subtitled. */
export const CTA_TEXT = 'Amazon, Flipkart ya Meesho par\nDASHX cricket tennis ball buy karo';

/**
 * end-card: the one closing card of a reel (max 5 s, ONE short spoken line = the call to action).
 * Only the DASHX logo (assets/store-images/dashx-logo.png, shown as it is: no stretching, no recolouring) and the call to action text.
 * No product photo. The logo is on screen from the first frame; the text appears as the voice says it.
 * When the store logo is missing, the old assets/dashx-logo.png is used.
 * params: none. Use as the LAST scene of a reel; it works after any other templates.
 */
export const endCard: Template = function* (world, d, _params, ctx): ThreadGenerator {
  const logo = createRef<Img>();
  const cta = createRef<Node>();

  world.add(
    <>
      <Rect size={[1080, 1920]} fill={'#000000'} />
      <Img ref={logo} src={ctx.endLogo ?? ctx.logo} width={760} y={-260} scale={0.9} />
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
    chain(waitFor(0.25), cta().opacity(1, 0.3)),
    waitFor(d),
  );
};
