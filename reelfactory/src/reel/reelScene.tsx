import {Img, Node, Rect, Txt, makeScene2D} from '@revideo/2d';
import {all, chain, createRef, linear, useScene, waitFor} from '@revideo/core';
import type {ThreadGenerator} from '@revideo/core';

import {FONT} from './art/helpers';
import type {Char} from './art/characters';
import {LIVE} from './templates/common';
import {TEMPLATE_FUNCTIONS} from './templates';
import type {TemplateName} from './templateInfo';

type CameraSpec = {move: string; from?: number; to?: number; zoom?: number};
/** One spoken line of a dialogue scene. start/end (seconds from the scene start), lines and width are set by scripts/fit_reel.py. */
type DialogueLine = {speaker: string; line: string; start?: number; end?: number; lines?: number; width?: number; mouth?: [number, string][]};
type SceneSpec = {
  id: number;
  template: TemplateName; // which template draws this scene
  params?: Record<string, unknown>; // characters, texts ... for that template
  duration: number;
  subtitle: string;
  camera: CameraSpec;
  endCard?: boolean; // end card over the last seconds (default: only for hero-end)
  subtitleWidth?: number; // wrap width of the subtitle in px (default 900); set by scripts/fit_reel.py
  dialogue?: DialogueLine[]; // dialogue format: who says what, and when
};
type Script = {scenes: SceneSpec[]; brand?: {line?: string}; story?: {card?: string}};

const W = 1080;
const H = 1920;
const FADE = 0.3; // crossfade between scenes (seconds)
const END_CARD = 2.5; // end card length at the end of the last scene (seconds)
const SUB_Y = 470; // centre of the subtitle box
const SUB_Y_END = 400; // the end card's call to action is long (up to 3 lines), so its subtitle sits higher: it must stay above the Reels/Shorts bottom UI (factory/qc.py SUB_Y_END)
const LINE_H = 88; // subtitle line height (px)
// On-screen hook card (story `card:`, 3-5 Hindi words): top of the frame, first 1.5 s. Position and size are mirrored in factory/qc.py (hook_card).
const CARD_Y = -660; // centre of the card (px above the frame centre): the box stays below the top safe area (150 px)
const CARD_W = 900;
const CARD_FONT = 76;
const CARD_HOLD = 1.5; // seconds on screen

// The coloured name tag above each speaker's subtitle: one colour per character, every colour has a contrast of at least 5:1 with the white text.
const TAG: Record<string, {name: string; color: string}> = {
  sachin: {name: 'सचिन', color: '#c62828'},
  surya: {name: 'सूर्या', color: '#15803d'},
  dadaji: {name: 'दादाजी', color: '#7c4a14'},
  aunty: {name: 'आंटी', color: '#a21062'},
  pintu: {name: 'पिंटू', color: '#334155'},
  golu: {name: 'गोलू', color: '#b45309'},
  meena: {name: 'मीना', color: '#0f766e'},
  coach: {name: 'कोच', color: '#1d4ed8'},
  bruno: {name: 'ब्रूनो', color: '#7c2d12'},
  pappu: {name: 'पप्पू भैया', color: '#c2410c'},
  chhotu: {name: 'छोटू', color: '#0369a1'},
  mintu: {name: 'मिंटू', color: '#6d28d9'},
};

/** Turn a camera spec into start/end values for scale and position (Ken Burns). */
function camera(c: CameraSpec) {
  const zoom = c.zoom ?? 1.12;
  const maxX = (W * (zoom - 1)) / 2;
  const maxY = (H * (zoom - 1)) / 2;
  switch (c.move) {
    case 'zoom-in':
      return {s0: c.from ?? 1, s1: c.to ?? 1.12, x0: 0, x1: 0, y0: 0, y1: 0};
    case 'zoom-out':
      return {s0: c.from ?? 1.12, s1: c.to ?? 1, x0: 0, x1: 0, y0: 0, y1: 0};
    case 'pan-left': // camera moves left, picture moves right
      return {s0: zoom, s1: zoom, x0: -maxX, x1: maxX, y0: 0, y1: 0};
    case 'pan-right':
      return {s0: zoom, s1: zoom, x0: maxX, x1: -maxX, y0: 0, y1: 0};
    case 'tilt-up': // camera tilts up, picture moves down
      return {s0: zoom, s1: zoom, x0: 0, x1: 0, y0: -maxY, y1: maxY};
    case 'tilt-down':
      return {s0: zoom, s1: zoom, x0: 0, x1: 0, y0: maxY, y1: -maxY};
    default:
      return {s0: 1, s1: 1, x0: 0, x1: 0, y0: 0, y1: 0};
  }
}

/** Mouth size (width, height scale of the drawn mouth) for each Rhubarb mouth shape; A = closed, D = wide open, E/F = rounded/pursed, X = rest. */
const MOUTH: Record<string, [number, number]> = {
  A: [1.0, 0.35], B: [1.0, 0.75], C: [1.12, 1.3], D: [1.2, 1.9], E: [0.85, 1.35], F: [0.7, 1.0], G: [1.1, 0.6], H: [1.15, 1.5], X: [1.0, 0.7],
};

/**
 * The speaker's mouth moves and the head bobs a little while the line is spoken.
 * With `cues` (made by scripts/lipsync.py from the real voice: [seconds since the line started, mouth shape]) the mouth follows the sound;
 * without cues it opens and closes in a fixed beat, as before.
 */
function* speak(c: Char | undefined, seconds: number, cues?: [number, string][]): ThreadGenerator {
  if (!c) {
    yield* waitFor(seconds);
    return;
  }
  const y0 = c.head.y();
  if (cues && cues.length > 0) {
    const mouth = function* (): ThreadGenerator {
      let t = 0;
      for (let k = 0; k < cues.length; k++) {
        const at = Math.min(seconds, Math.max(t, cues[k][0]));
        if (at > t) yield* waitFor(at - t);
        t = at;
        c.mouth.scale(MOUTH[cues[k][1]] ?? [1, 1]);
      }
      if (seconds > t) yield* waitFor(seconds - t);
    };
    const bob = function* (): ThreadGenerator {
      const beats = Math.max(1, Math.round(seconds / 0.3));
      for (let k = 0; k < beats; k++) {
        yield* c.head.y(y0 - 4, 0.15);
        yield* c.head.y(y0, 0.15);
      }
    };
    yield* all(mouth(), bob());
    c.mouth.scale([1, 1]);
    c.head.y(y0);
    return;
  }
  const beats = Math.max(1, Math.round(seconds / 0.22));
  for (let k = 0; k < beats; k++) {
    yield* all(c.mouth.scale([1.15, 1.9], 0.11), c.head.y(y0 - 6, 0.11));
    yield* all(c.mouth.scale([1, 0.8], 0.11), c.head.y(y0, 0.11));
  }
  c.mouth.scale([1, 1]);
  c.head.y(y0);
}

export default makeScene2D('reel', function* (view) {
  const vars = useScene().variables;
  const script = vars.get('script', {scenes: []} as Script)();
  const logo = vars.get('logo', '')();
  const ball = vars.get('ball', '')();
  const endLogo = vars.get('endLogo', '')() || undefined;
  const endPack = vars.get('endPack', '')() || undefined;
  const line = script.brand?.line ?? 'DASHX by Nav Durga Sports, Meerut';

  view.fill('#000000');

  // Make sure the Devanagari font is ready before the first subtitle is drawn.
  yield document.fonts.load("700 64px 'Noto Sans Devanagari'");

  let prevStage: Node | undefined;
  let prevSubs: Node[] = [];

  for (let i = 0; i < script.scenes.length; i++) {
    const sc = script.scenes[i];
    const showEndCard = sc.endCard ?? sc.template === 'hero-end';
    const cam = camera(sc.camera);
    const dialogue = sc.dialogue && sc.dialogue.length > 0 ? sc.dialogue : undefined;

    // stage = camera (zoom/pan), world = the drawn scene (also shaken in scene 3)
    const stage = createRef<Node>();
    const world = createRef<Node>();
    view.add(
      <Node ref={stage} scale={cam.s0} x={cam.x0} y={cam.y0} opacity={i === 0 ? 1 : 0}>
        <Node ref={world} />
      </Node>,
    );

    const subs: Node[] = [];
    const tasks: ThreadGenerator[] = [];

    if (dialogue) {
      // ---- dialogue scene: one subtitle per spoken line, a name tag, a speech-bubble tail, a talking mouth ----
      for (const key of Object.keys(LIVE)) delete LIVE[key];
      dialogue.forEach((e, k) => {
        const g = createRef<Node>();
        const tail = createRef<Rect>();
        const w = e.width ?? sc.subtitleWidth ?? 900;
        const n = e.lines ?? 2;
        const boxW = w + 80;
        const boxH = n * LINE_H + 44;
        const top = SUB_Y - boxH / 2;
        const tag = TAG[e.speaker] ?? {name: '', color: '#334155'};
        view.add(
          <Node ref={g} opacity={0}>
            <Rect
              y={SUB_Y}
              fill={'#0f172aee'}
              radius={36}
              padding={[22, 40]}
              layout
            >
              <Txt
                text={e.line}
                fontFamily={FONT}
                fontWeight={700}
                fontSize={56}
                lineHeight={LINE_H}
                fill={'#ffffff'}
                width={w}
                textWrap
                textAlign={'center'}
              />
            </Rect>
            <Rect ref={tail} y={top} size={36} rotation={45} fill={'#0f172aee'} />
            <Rect
                offset={[-1, 0]}
                x={-boxW / 2 + 30}
                y={top - 30}
                fill={tag.color}
                stroke={'#ffffff'}
                lineWidth={6}
                radius={34}
                padding={[8, 34]}
                layout
              >
                <Txt text={tag.name} fontFamily={FONT} fontWeight={900} fontSize={62} fill={'#ffffff'} />
            </Rect>
          </Node>,
        );
        subs.push(g());
        const start = e.start ?? 0.25;
        const stop = e.end ?? start + 1.5;
        const nextStart = dialogue[k + 1]?.start;
        tasks.push(
          (function* (): ThreadGenerator {
            yield* waitFor(start);
            const c = LIVE[e.speaker];
            if (c) {
              // the tail points at the speaker (position on screen = world x scaled and moved by the camera)
              const sx = c.node.x() * stage().scale.x() + stage().x();
              tail().x(Math.min(boxW / 2 - 60, Math.max(-boxW / 2 + 330, sx)));
            }
            yield* all(
              g().opacity(1, 0.08),
              speak(c, Math.max(0.2, stop - start), e.mouth),
              nextStart !== undefined ? chain(waitFor(Math.max(0.1, nextStart - start - 0.08)), g().opacity(0, 0.08)) : waitFor(0),
            );
          })(),
        );
      });
    } else {
      // ---- plain subtitle (end card, and reels made before the dialogue format) ----
      const sub = createRef<Rect>();
      // Subtitle: white on a dark rounded box, kept clear of the Reels/Shorts bottom UI.
      view.add(
        <Rect
          ref={sub}
          y={sc.template === 'end-card' ? SUB_Y_END : SUB_Y}
          fill={'#000000b8'}
          radius={36}
          padding={[22, 40]}
          layout
          opacity={i === 0 ? 1 : 0}
        >
          <Txt
            text={sc.subtitle}
            fontFamily={FONT}
            fontWeight={700}
            fontSize={56}
            lineHeight={LINE_H}
            fill={'#ffffff'}
            width={sc.subtitleWidth ?? 900}
            textWrap
            textAlign={'center'}
          />
        </Rect>,
      );
      subs.push(sub());
      if (i > 0) {
        tasks.push(chain(waitFor(0.2), sub().opacity(1, 0.25)));
      }
    }

    if (i === 0 && script.story?.card) {
      // hook card: pops in with the very first frame and leaves after CARD_HOLD seconds (added to the view, so the camera does not move it)
      const cardBox = createRef<Rect>();
      view.add(
        <Rect ref={cardBox} y={CARD_Y} fill={'#000000d8'} radius={30} padding={[20, 44]} layout opacity={0} scale={0.88}>
          <Txt
            text={script.story.card}
            fontFamily={FONT}
            fontWeight={800}
            fontSize={CARD_FONT}
            lineHeight={CARD_FONT * 1.25}
            fill={'#fde047'}
            width={CARD_W}
            textWrap
            textAlign={'center'}
          />
        </Rect>,
      );
      tasks.push(
        (function* (): ThreadGenerator {
          yield* all(cardBox().opacity(1, 0.12), cardBox().scale(1, 0.22));
          yield* waitFor(CARD_HOLD - 0.34);
          yield* cardBox().opacity(0, 0.2);
          cardBox().remove();
        })(),
      );
    }

    tasks.push(
      TEMPLATE_FUNCTIONS[sc.template](world(), sc.duration, sc.params ?? {}, {logo, ball, endLogo, endPack}),
      stage().scale(cam.s1, sc.duration, linear),
      stage().position([cam.x1, cam.y1], sc.duration, linear),
    );
    if (i > 0) {
      // later scenes cross-fade over the previous one; the very first frame is never faded from black
      tasks.push(stage().opacity(1, FADE));
    }
    for (const p of prevSubs) {
      tasks.push(p.opacity(0, 0.2));
    }

    // End card over the final seconds (hero-end scenes).
    if (showEndCard) {
      const endCard = createRef<Rect>();
      view.add(
        <Rect ref={endCard} size={[W, H]} fill={'#0b1220'} opacity={0}>
          <Img src={logo} width={760} y={-380} />
          <Img src={ball} width={380} y={40} />
          <Txt
            text={line}
            fontFamily={FONT}
            fontWeight={700}
            fontSize={54}
            fill={'#ffffff'}
            width={900}
            textWrap
            textAlign={'center'}
            y={430}
          />
          <Txt
            text={'Cricket Tennis Ball'}
            fontFamily={FONT}
            fontWeight={500}
            fontSize={44}
            fill={'#fbbf24'}
            y={540}
          />
        </Rect>,
      );
      tasks.push(chain(waitFor(sc.duration - END_CARD), endCard().opacity(1, 0.5)));
    }

    yield* all(...tasks);

    // The old scene is fully covered now; drop it.
    prevStage?.remove();
    prevSubs.forEach(p => p.remove());
    prevStage = stage();
    prevSubs = subs;
  }
});
