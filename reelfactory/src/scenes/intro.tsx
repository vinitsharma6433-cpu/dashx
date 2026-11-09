import {Circle, Rect, Txt, makeScene2D} from '@revideo/2d';
import {all, chain, createRef, easeInOutCubic, waitFor} from '@revideo/core';

/**
 * 15 second vertical scene:
 *  - title fades in and moves up
 *  - a coloured shape scales in, pulses, then scales out
 */
export default makeScene2D('intro', function* (view) {
  view.fill('#0f172a');

  const title = createRef<Txt>();
  const box = createRef<Rect>();
  const dot = createRef<Circle>();

  view.add(
    <>
      <Txt
        ref={title}
        text={'Hello, Vinit!'}
        fontFamily={'sans-serif'}
        fontSize={110}
        fontWeight={800}
        fill={'#f8fafc'}
        y={300}
        opacity={0}
      />
      <Rect
        ref={box}
        width={420}
        height={420}
        radius={60}
        fill={'#ef4444'}
        y={300}
        scale={0}
      />
      <Circle ref={dot} size={160} fill={'#38bdf8'} y={700} scale={0} />
    </>,
  );

  // 0s - 2s: title fades in while moving up, shape scales in
  yield* all(
    title().opacity(1, 2),
    title().y(-500, 2, easeInOutCubic),
    box().scale(1, 2, easeInOutCubic),
    box().rotation(90, 2, easeInOutCubic),
  );

  // 2s - 4s: small circle pops in
  yield* dot().scale(1, 1, easeInOutCubic);
  yield* waitFor(1);

  // 4s - 12s: shape pulses (scale up and down) four times
  for (let i = 0; i < 4; i++) {
    yield* chain(
      all(box().scale(1.5, 1, easeInOutCubic), dot().scale(0.5, 1)),
      all(box().scale(1, 1, easeInOutCubic), dot().scale(1, 1)),
    );
  }

  // 12s - 14s: everything scales out and title fades away
  yield* all(
    box().scale(0, 2, easeInOutCubic),
    dot().scale(0, 2, easeInOutCubic),
    title().opacity(0, 2),
  );

  // 14s - 15s: hold on empty background
  yield* waitFor(1);
});
