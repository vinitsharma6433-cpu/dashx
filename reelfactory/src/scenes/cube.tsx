import {Txt, makeScene2D} from '@revideo/2d';
import {all, createRef, linear} from '@revideo/core';

import {Cube} from '../components/Cube';

/**
 * Idea: "A glowing 3D-looking cube rotating slowly with the text
 * 'Hello, Vinit!' above it, dark blue background, 8 seconds."
 */
export default makeScene2D('cube', function* (view) {
  view.fill('#0a1230');

  const title = createRef<Txt>();
  const cube = createRef<Cube>();

  view.add(
    <>
      <Txt
        ref={title}
        text={'Hello, Vinit!'}
        fontFamily={'sans-serif'}
        fontSize={120}
        fontWeight={800}
        fill={'#e0f2fe'}
        shadowColor={'#38bdf8'}
        shadowBlur={30}
        y={-450}
        opacity={0}
      />
      <Cube ref={cube} edge={380} y={260} />
    </>,
  );

  // 0s - 8s: one slow full turn; title fades in during the first second.
  yield* all(title().opacity(1, 1), cube().angle(Math.PI * 2, 8, linear));
});
