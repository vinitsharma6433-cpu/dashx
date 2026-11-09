import {Node, Rect, Txt} from '@revideo/2d';
import {all, chain, createRef, easeInQuad, easeOutBack, waitFor} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import {makeBackground} from '../art/background';
import {makeChar} from '../art/characters';
import {FONT} from '../art/helpers';
import {GROUND, S, breathe, lookAt, pickText, pickWho, place, pickBool} from './common';
import type {Template} from './types';

/**
 * face-off: two characters face each other, a scoreboard pops in.
 * params: left (who, default sachin), right (who, default surya), boardText (text, default "TIE"; "" = no board)
 */
export const faceOff: Template = function* (world, d, params): ThreadGenerator {
  const leftWho = pickWho(params, 'left', 'sachin');
  const rightWho = pickWho(params, 'right', 'surya');
  const boardText = pickText(params, 'boardText', 'TIE');

  world.add(makeBackground(pickBool(params, 'sunset', false)));
  const left = makeChar(leftWho);
  const right = makeChar(rightWho);
  place(world, left, -250, GROUND, S, false);
  place(world, right, 250, GROUND, S, true);
  lookAt(left, 6, 0);
  lookAt(right, 6, 0);

  const board = createRef<Node>();
  const drop = createRef<Node>();
  world.add(
    <>
      <Node ref={board} y={-560} scale={0}>
        <Rect size={[660, 230]} radius={34} fill={'#111827'} stroke={'#fbbf24'} lineWidth={10} />
        <Txt
          text={boardText}
          fontFamily={FONT}
          fontWeight={900}
          fontSize={/[ऀ-ॿ]/.test(boardText) ? (boardText.length <= 3 ? 150 : boardText.length <= 5 ? 120 : 92) : boardText.length > 5 ? 90 : 150}
          fill={'#fde047'}
          y={6}
        />
      </Node>
      <Node ref={drop} x={-150} y={-40} opacity={0}>
        <Rect y={-14} size={14} rotation={45} fill={'#7dd3fc'} />
        <Rect y={4} size={[20, 20]} radius={10} fill={'#7dd3fc'} />
      </Node>
    </>,
  );

  yield* all(
    breathe(left, d),
    breathe(right, d),
    boardText === '' ? waitFor(0) : chain(waitFor(0.9), board().scale(1, 0.55, easeOutBack)),
    chain(
      waitFor(1.4),
      all(drop().opacity(1, 0.2), drop().y(60, 1.4, easeInQuad)),
      drop().opacity(0, 0.3),
    ),
    waitFor(d),
  );
};
