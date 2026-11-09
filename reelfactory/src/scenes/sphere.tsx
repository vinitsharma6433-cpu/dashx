import {Txt, makeScene2D} from '@revideo/2d';
import {all, createRef, linear} from '@revideo/core';

import {DotSphere} from '../components/DotSphere';

/**
 * Idea: "cyan sphere made of dots, rotating, with text 'AI Animation'
 * above it, 8 seconds."
 */
export default makeScene2D('sphere', function* (view) {
  view.fill('#06121f');

  const title = createRef<Txt>();
  const sphere = createRef<DotSphere>();

  view.add(
    <>
      <Txt
        ref={title}
        text={'AI Animation'}
        fontFamily={'sans-serif'}
        fontSize={120}
        fontWeight={800}
        fill={'#cffafe'}
        shadowColor={'#22d3ee'}
        shadowBlur={30}
        y={-450}
        opacity={0}
      />
      <DotSphere ref={sphere} radius={300} y={260} />
    </>,
  );

  // 0s - 8s: one full turn; title fades in during the first second.
  yield* all(title().opacity(1, 1), sphere().angle(Math.PI * 2, 8, linear));
});
