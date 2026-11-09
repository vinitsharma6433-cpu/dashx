import {Img, Node, Rect, Txt} from '@revideo/2d';
import {all, chain, createRef, easeOutBack, waitFor} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import {FONT} from '../art/helpers';
import type {Template} from './types';

/** The call to action shown as text on the end card. The same sentence is spoken (Hindi) and subtitled. */
export const CTA_TEXT = 'Amazon, Flipkart ya Meesho par\nDASHX cricket tennis ball\nsearch karo aur le lo';

/**
 * end-card: the one closing card of a reel (max 5 s, ONE short spoken line = the call to action).
 * The DASHX logo (assets/store-images/dashx-logo.png), one small product pack below it (pack-power-red.png or pack-light-green.png,
 * alternating from reel to reel) and the call to action text. Images are shown as they are: no stretching, no recolouring.
 * The logo is on screen from the first frame; the pack and the text appear as the voice says it.
 * When the store logo is missing, the old assets/dashx-logo.png is used.
 * params: none. Use as the LAST scene of a reel; it works after any other templates.
 */
export const endCard: Template = function* (world, d, _params, ctx): ThreadGenerator {
  const logo = createRef<Img>();
  const pack = createRef<Img>();
  const cta = createRef<Node>();

  world.add(
    <>
      <Rect size={[1080, 1920]} fill={'#000000'} />
      <Img ref={logo} src={ctx.endLogo ?? ctx.logo} width={520} y={-530} scale={0.9} />
      {ctx.endPack ? <Img ref={pack} src={ctx.endPack} height={300} y={-115} opacity={0} /> : <Node ref={pack as any} />}
      <Node ref={cta} opacity={0}>
        <Txt
          text={CTA_TEXT}
          fontFamily={FONT}
          fontWeight={700}
          fontSize={46}
          lineHeight={62}
          fill={'#fbbf24'}
          textAlign={'center'}
          y={150}
        />
      </Node>
    </>,
  );

  yield* all(
    logo().scale(1, 0.5, easeOutBack),
    chain(waitFor(0.15), ctx.endPack ? pack().opacity(1, 0.3) : waitFor(0)),
    chain(waitFor(0.25), cta().opacity(1, 0.3)),
    waitFor(d),
  );
};
