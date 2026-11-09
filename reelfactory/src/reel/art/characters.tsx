import {Circle, Node, Rect} from '@revideo/2d';
import {createRef} from '@revideo/core';

import type {Who} from '../templateInfo';
export type {Who};

export interface Char {
  node: Node; // origin = feet, character grows upward (negative y)
  body: Node; // pivot at the hips
  head: Node;
  armL: Node; // pivots at the shoulders; rotation 0 = hanging down
  armR: Node;
  legL: Node; // pivots at the hips
  legR: Node;
  handL: Node;
  handR: Node;
  mouth: Circle;
  pupilL: Circle;
  pupilR: Circle;
  browL: Rect;
  browR: Rect;
  /** Overall size compared with a normal kid (Golu is small, the coach is big). Used when placing. */
  height: number;
  /** Which character this is (set by makeChar); the reel uses it to find the speaker. */
  who?: Who;
}

type NodeRef = ReturnType<typeof createRef<Node>>;

/** Everything that makes one person look different. All people share the same flat 2D shapes. */
interface Look {
  skin: string;
  shirt: string;
  /** 'shorts' = skin legs + coloured shorts; 'long' = one solid trouser colour. */
  lower: 'shorts' | 'long';
  lowerColor: string;
  legW: number;
  shoe: string;
  legLen: number;
  torsoW: number;
  torsoH: number;
  torsoY: number;
  shoulderY: number;
  armLen: number;
  armW: number;
  longSleeves: boolean;
  headY: number;
  headSize: number;
  earSize: number;
  eyeSize: number;
  browColor: string;
  noseColor: string;
  mouthY: number;
  mouthColor: string;
  collar: 'neck' | 'band';
  collarColor: string;
  collarY: number;
  hairBack?: string; // dark circle behind the head
  sideHair?: string; // white tufts at the sides (Dadaji)
  glasses?: {color: string; size: number};
  moustache?: {color: string; w: number; h: number};
  armband?: string;
  height: number;
  extra?: 'aunty' | 'pintu' | 'golu' | 'meena' | 'coach';
}

// The first three are the original cast and keep exactly their old numbers.
const LOOKS: Record<Exclude<Who, 'bruno'>, Look> = {
  sachin: {
    skin: '#f2b98d', shirt: '#e53935', lower: 'shorts', lowerColor: '#1e5bd7', legW: 36, shoe: '#3f2d1d',
    legLen: 125, torsoW: 124, torsoH: 140, torsoY: -62, shoulderY: -118, armLen: 118, armW: 30, longSleeves: false,
    headY: -184, headSize: 124, earSize: 28, eyeSize: 30, browColor: '#15151a', noseColor: '#dc9a6c', mouthY: 38,
    mouthColor: '#7f1d1d', collar: 'neck', collarColor: '#f2b98d', collarY: -128, hairBack: '#15151a', height: 1,
  },
  surya: {
    skin: '#f2b98d', shirt: '#2e9e4f', lower: 'long', lowerColor: '#35568a', legW: 42, shoe: '#f8fafc',
    legLen: 125, torsoW: 124, torsoH: 140, torsoY: -62, shoulderY: -118, armLen: 118, armW: 30, longSleeves: false,
    headY: -184, headSize: 124, earSize: 28, eyeSize: 30, browColor: '#15151a', noseColor: '#dc9a6c', mouthY: 38,
    mouthColor: '#7f1d1d', collar: 'neck', collarColor: '#f2b98d', collarY: -128, hairBack: '#15151a', height: 1,
  },
  dadaji: {
    skin: '#d9a47a', shirt: '#fafafa', lower: 'long', lowerColor: '#e5e7eb', legW: 46, shoe: '#3f2d1d',
    legLen: 110, torsoW: 150, torsoH: 190, torsoY: -75, shoulderY: -148, armLen: 125, armW: 34, longSleeves: true,
    headY: -232, headSize: 124, earSize: 28, eyeSize: 30, browColor: '#9ca3af', noseColor: '#dc9a6c', mouthY: 48,
    mouthColor: '#7f1d1d', collar: 'band', collarColor: '#d1d5db', collarY: -168, sideHair: '#f3f4f6',
    glasses: {color: '#111827', size: 40}, moustache: {color: '#f3f4f6', w: 60, h: 15}, height: 1,
  },
  // ---- new original characters (neighbours and friends from the gali) ----
  aunty: { // the neighbour: magenta kurta, mustard salwar, sky-blue scarf, hair bun, gold earrings
    skin: '#e3ac83', shirt: '#be185d', lower: 'long', lowerColor: '#facc15', legW: 48, shoe: '#7c2d12',
    legLen: 115, torsoW: 136, torsoH: 168, torsoY: -72, shoulderY: -128, armLen: 112, armW: 28, longSleeves: false,
    headY: -196, headSize: 122, earSize: 26, eyeSize: 30, browColor: '#3b2a1a', noseColor: '#d58f66', mouthY: 38,
    mouthColor: '#9f1239', collar: 'neck', collarColor: '#e3ac83', collarY: -138, hairBack: '#2b1b12', height: 1.04,
    extra: 'aunty',
  },
  pintu: { // the umpire: tall and thin, cream umpire hat, white shirt, black trousers, orange armband
    skin: '#c98c5a', shirt: '#f8fafc', lower: 'long', lowerColor: '#1f2937', legW: 36, shoe: '#111827',
    legLen: 138, torsoW: 104, torsoH: 150, torsoY: -66, shoulderY: -126, armLen: 124, armW: 26, longSleeves: false,
    headY: -196, headSize: 116, earSize: 26, eyeSize: 28, browColor: '#15151a', noseColor: '#b4764a', mouthY: 36,
    mouthColor: '#7f1d1d', collar: 'neck', collarColor: '#c98c5a', collarY: -134,
    moustache: {color: '#15151a', w: 34, h: 8}, armband: '#f97316', height: 1.02, extra: 'pintu',
  },
  golu: { // the small fielder: tiny, spiky hair, big red glasses, yellow T-shirt, red sneakers
    skin: '#e0a878', shirt: '#facc15', lower: 'shorts', lowerColor: '#92400e', legW: 34, shoe: '#ef4444',
    legLen: 105, torsoW: 118, torsoH: 130, torsoY: -58, shoulderY: -108, armLen: 108, armW: 28, longSleeves: false,
    headY: -176, headSize: 138, earSize: 36, eyeSize: 32, browColor: '#2b1b12', noseColor: '#c98d62', mouthY: 42,
    mouthColor: '#7f1d1d', collar: 'neck', collarColor: '#e0a878', collarY: -118, hairBack: '#2b1b12',
    glasses: {color: '#dc2626', size: 46}, height: 0.78, extra: 'golu',
  },
  meena: { // the girl batter: teal T-shirt, magenta leggings, two pigtails with pink hair ties
    skin: '#f0b48e', shirt: '#14b8a6', lower: 'long', lowerColor: '#be185d', legW: 36, shoe: '#f8fafc',
    legLen: 120, torsoW: 116, torsoH: 138, torsoY: -60, shoulderY: -114, armLen: 114, armW: 28, longSleeves: false,
    headY: -182, headSize: 124, earSize: 26, eyeSize: 32, browColor: '#15151a', noseColor: '#d9987a', mouthY: 38,
    mouthColor: '#be123c', collar: 'neck', collarColor: '#f0b48e', collarY: -124, hairBack: '#15151a', height: 0.96,
    extra: 'meena',
  },
  coach: { // the coach uncle: big, blue tracksuit, red cap, thick moustache, whistle
    skin: '#cf9a6e', shirt: '#2563eb', lower: 'long', lowerColor: '#1e3a8a', legW: 52, shoe: '#f8fafc',
    legLen: 122, torsoW: 168, torsoH: 178, torsoY: -80, shoulderY: -140, armLen: 124, armW: 34, longSleeves: true,
    headY: -226, headSize: 130, earSize: 30, eyeSize: 28, browColor: '#15151a', noseColor: '#b9805a', mouthY: 50,
    mouthColor: '#7f1d1d', collar: 'band', collarColor: '#f8fafc', collarY: -164,
    moustache: {color: '#15151a', w: 78, h: 18}, height: 1.08, extra: 'coach',
  },
};

/** Shapes drawn BEHIND the head: hair buns, pigtails, spikes. */
function behindHead(look: Look) {
  if (look.extra === 'aunty') {
    return <Circle y={-82} size={56} fill={'#2b1b12'} />;
  }
  if (look.extra === 'meena') {
    return (
      <>
        <Circle x={-84} y={26} size={50} fill={'#15151a'} />
        <Circle x={84} y={26} size={50} fill={'#15151a'} />
      </>
    );
  }
  if (look.extra === 'golu') {
    const spikes = [-56, -28, 0, 28, 56].map(r => (
      <Node y={-56} rotation={r}>
        <Rect y={-30} width={24} height={52} radius={10} fill={'#2b1b12'} />
      </Node>
    ));
    return <>{spikes}</>;
  }
  return null;
}

/** Shapes drawn ON the face and head: earrings, lashes, hats, hair ties. */
function onFace(look: Look) {
  if (look.extra === 'aunty') {
    return (
      <>
        <Circle x={-62} y={24} size={12} fill={'#facc15'} />
        <Circle x={62} y={24} size={12} fill={'#facc15'} />
      </>
    );
  }
  if (look.extra === 'pintu') {
    return (
      <>
        <Circle y={-66} size={[176, 40]} fill={'#f1e2c0'} />
        <Circle y={-90} size={[114, 68]} fill={'#f1e2c0'} />
        <Rect y={-74} width={112} height={11} fill={'#d97706'} />
      </>
    );
  }
  if (look.extra === 'meena') {
    return (
      <>
        <Circle x={-72} y={10} size={18} fill={'#ec4899'} />
        <Circle x={72} y={10} size={18} fill={'#ec4899'} />
        <Rect x={-40} y={-12} width={14} height={4} fill={'#15151a'} rotation={-20} />
        <Rect x={40} y={-12} width={14} height={4} fill={'#15151a'} rotation={20} />
      </>
    );
  }
  if (look.extra === 'coach') {
    return (
      <>
        <Circle y={-72} size={[134, 74]} fill={'#ef4444'} />
        <Rect x={36} y={-44} width={84} height={16} radius={8} fill={'#b91c1c'} />
      </>
    );
  }
  return null;
}

/** Shapes on the body, over the torso: scarf, belly, whistle. */
function onBody(look: Look) {
  if (look.extra === 'aunty') {
    return (
      <>
        <Rect x={10} y={-72} width={30} height={134} radius={10} fill={'#0ea5e9'} rotation={24} />
        <Rect x={-30} y={-110} width={14} height={60} radius={7} fill={'#0ea5e9'} rotation={24} />
      </>
    );
  }
  if (look.extra === 'coach') {
    return (
      <>
        <Circle y={-30} size={[150, 120]} fill={'#3b82f6'} />
        <Rect y={-80} width={5} height={150} fill={'#f8fafc'} />
        <Circle x={-34} y={-96} size={20} fill={'#fde047'} />
        <Rect x={-24} y={-120} width={3} height={40} fill={'#111827'} rotation={-30} />
      </>
    );
  }
  return null;
}

/** A person: shapes only, circles and rounded rectangles. Same look every time it is created. */
function makePerson(look: Look, legLenOverride?: number): Char {
  const legLen = legLenOverride ?? look.legLen;
  const hipY = -legLen;
  const {skin, shirt} = look;

  const root = createRef<Node>();
  const body = createRef<Node>();
  const head = createRef<Node>();
  const armL = createRef<Node>();
  const armR = createRef<Node>();
  const legL = createRef<Node>();
  const legR = createRef<Node>();
  const handL = createRef<Node>();
  const handR = createRef<Node>();
  const mouth = createRef<Circle>();
  const pupilL = createRef<Circle>();
  const pupilR = createRef<Circle>();
  const browL = createRef<Rect>();
  const browR = createRef<Rect>();

  const leg = (ref: NodeRef, x: number) => (
    <Node ref={ref} x={x} y={hipY}>
      {look.lower === 'shorts' ? (
        <>
          <Rect y={legLen / 2} width={look.legW} height={legLen} radius={12} fill={skin} />
          <Rect y={32} width={look.legW + 12} height={72} radius={10} fill={look.lowerColor} />
        </>
      ) : (
        <Rect y={legLen / 2} width={look.legW} height={legLen} radius={12} fill={look.lowerColor} />
      )}
      {look.extra === 'coach' ? (
        <Rect x={look.legW / 2 - 5} y={legLen / 2} width={6} height={legLen} fill={'#f8fafc'} />
      ) : null}
      <Rect x={9} y={legLen - 6} width={58} height={26} radius={13} fill={look.shoe} />
    </Node>
  );

  const arm = (ref: NodeRef, hand: NodeRef, side: number) => (
    <Node ref={ref} x={side * (look.torsoW / 2 + 2)} y={look.shoulderY}>
      <Rect
        y={look.armLen / 2}
        width={look.armW}
        height={look.armLen}
        radius={15}
        fill={look.longSleeves ? shirt : skin}
      />
      {look.longSleeves ? null : <Rect y={26} width={36} height={54} radius={12} fill={shirt} />}
      {look.armband && side < 0 ? <Rect y={74} width={look.armW + 6} height={12} fill={look.armband} /> : null}
      <Node ref={hand} y={look.armLen}>
        <Circle size={34} fill={skin} />
      </Node>
    </Node>
  );

  const eye = (x: number, pupil: typeof pupilL) => (
    <>
      <Circle x={x} y={-2} size={look.eyeSize} fill={'#ffffff'} />
      <Circle ref={pupil} x={x} y={-2} size={look.eyeSize / 2} fill={'#1f2937'} />
    </>
  );

  (
    <Node ref={root}>
      {leg(legL, -32)}
      {leg(legR, 32)}
      <Node ref={body} y={hipY}>
        <Rect y={look.torsoY} width={look.torsoW} height={look.torsoH} radius={28} fill={shirt} />
        {look.collar === 'band' ? (
          <Rect y={look.collarY} width={46} height={14} radius={7} fill={look.collarColor} />
        ) : (
          <Circle y={look.collarY} size={36} fill={look.collarColor} />
        )}
        {onBody(look)}
        {arm(armL, handL, -1)}
        {arm(armR, handR, 1)}
        <Node ref={head} y={look.headY}>
          {look.hairBack ? <Circle y={-12} size={134} fill={look.hairBack} /> : null}
          {behindHead(look)}
          <Circle x={-60} y={4} size={look.earSize} fill={skin} />
          <Circle x={60} y={4} size={look.earSize} fill={skin} />
          <Circle size={look.headSize} fill={skin} />
          {look.sideHair ? (
            <>
              <Circle x={-58} y={-20} size={30} fill={look.sideHair} />
              <Circle x={58} y={-20} size={30} fill={look.sideHair} />
            </>
          ) : null}
          {eye(-26, pupilL)}
          {eye(26, pupilR)}
          <Rect ref={browL} x={-26} y={-30} width={26} height={7} radius={4} fill={look.browColor} />
          <Rect ref={browR} x={26} y={-30} width={26} height={7} radius={4} fill={look.browColor} />
          <Circle y={14} size={14} fill={look.noseColor} />
          {look.glasses ? (
            <>
              <Circle x={-26} y={-2} size={look.glasses.size} stroke={look.glasses.color} lineWidth={5} />
              <Circle x={26} y={-2} size={look.glasses.size} stroke={look.glasses.color} lineWidth={5} />
              <Rect y={-2} width={14} height={5} fill={look.glasses.color} />
            </>
          ) : null}
          {look.moustache ? (
            <Rect y={27} width={look.moustache.w} height={look.moustache.h} radius={8} fill={look.moustache.color} />
          ) : null}
          {onFace(look)}
          <Circle ref={mouth} y={look.mouthY} size={[34, 9]} fill={look.mouthColor} />
        </Node>
      </Node>
    </Node>
  );

  return {
    node: root(),
    body: body(),
    head: head(),
    armL: armL(),
    armR: armR(),
    legL: legL(),
    legR: legR(),
    handL: handL(),
    handR: handR(),
    mouth: mouth(),
    pupilL: pupilL(),
    pupilR: pupilR(),
    browL: browL(),
    browR: browR(),
    height: look.height,
  };
}

/**
 * Bruno the dog (sitting, seen from the front): same flat style, same parts as a person so the templates
 * can use it (front paws = arms, back paws = legs). It only watches and reacts, it never bats or bowls.
 */
function makeDog(): Char {
  const root = createRef<Node>();
  const body = createRef<Node>();
  const head = createRef<Node>();
  const armL = createRef<Node>();
  const armR = createRef<Node>();
  const legL = createRef<Node>();
  const legR = createRef<Node>();
  const handL = createRef<Node>();
  const handR = createRef<Node>();
  const mouth = createRef<Circle>();
  const pupilL = createRef<Circle>();
  const pupilR = createRef<Circle>();
  const browL = createRef<Rect>();
  const browR = createRef<Rect>();
  const fur = '#d6a35c';
  const dark = '#7c4a1e';

  const hind = (ref: NodeRef, x: number) => (
    <Node ref={ref} x={x} y={-40}>
      <Circle y={22} size={[58, 44]} fill={fur} />
      <Circle x={6} y={34} size={[56, 26]} fill={'#f3e0b8'} />
    </Node>
  );
  const front = (ref: NodeRef, hand: NodeRef, x: number) => (
    <Node ref={ref} x={x} y={-96}>
      <Rect y={34} width={30} height={66} radius={15} fill={fur} />
      <Node ref={hand} y={66}>
        <Circle size={[38, 26]} fill={'#f3e0b8'} />
      </Node>
    </Node>
  );
  const eye = (x: number, pupil: typeof pupilL) => (
    <>
      <Circle x={x} y={-6} size={30} fill={'#ffffff'} />
      <Circle ref={pupil} x={x} y={-6} size={16} fill={'#1f2937'} />
    </>
  );

  (
    <Node ref={root}>
      <Circle x={86} y={-26} size={[26, 80]} fill={dark} rotation={-40} />
      {hind(legL, -40)}
      {hind(legR, 40)}
      <Node ref={body} y={-40}>
        <Circle y={-62} size={[150, 138]} fill={fur} />
        <Circle y={-48} size={[96, 96]} fill={'#f3e0b8'} />
        {front(armL, handL, -42)}
        {front(armR, handR, 42)}
        <Node ref={head} y={-152}>
          <Circle x={-66} y={0} size={[46, 84]} fill={dark} rotation={14} />
          <Circle x={66} y={0} size={[46, 84]} fill={dark} rotation={-14} />
          <Circle size={[122, 112]} fill={fur} />
          <Circle x={-24} y={-26} size={[34, 22]} fill={'#a8742f'} />
          {eye(-28, pupilL)}
          {eye(28, pupilR)}
          <Rect ref={browL} x={-28} y={-32} width={24} height={6} radius={3} fill={dark} />
          <Rect ref={browR} x={28} y={-32} width={24} height={6} radius={3} fill={dark} />
          <Circle y={24} size={[72, 54]} fill={'#f3e0b8'} />
          <Circle y={10} size={[28, 20]} fill={'#111827'} />
          <Circle y={58} size={[22, 30]} fill={'#f472b6'} />
          <Circle ref={mouth} y={40} size={[30, 8]} fill={'#7f1d1d'} />
        </Node>
      </Node>
    </Node>
  );

  return {
    node: root(),
    body: body(),
    head: head(),
    armL: armL(),
    armR: armR(),
    legL: legL(),
    legR: legR(),
    handL: handL(),
    handR: handR(),
    mouth: mouth(),
    pupilL: pupilL(),
    pupilR: pupilR(),
    browL: browL(),
    browR: browR(),
    height: 1.25,
  };
}

/** One person from the cast, or Bruno the dog. */
export function makeChar(who: Who, opts: {legLen?: number} = {}): Char {
  const c = who === 'bruno' ? makeDog() : makePerson(LOOKS[who], opts.legLen);
  c.who = who;
  return c;
}

/** Yellow tennis ball with two white seams. Origin = centre. */
export function makeBall(size = 46): Node {
  return (
    <Node>
      <Circle size={size} fill={'#dff31a'} stroke={'#9fb000'} lineWidth={2} clip>
        <Circle
          x={-size * 0.78}
          size={size * 1.1}
          startAngle={-50}
          endAngle={50}
          stroke={'#ffffff'}
          lineWidth={Math.max(2, size * 0.07)}
        />
        <Circle
          x={size * 0.78}
          size={size * 1.1}
          startAngle={130}
          endAngle={230}
          stroke={'#ffffff'}
          lineWidth={Math.max(2, size * 0.07)}
        />
      </Circle>
    </Node>
  );
}

/** Cricket bat. Origin = bottom of the handle, blade points up (negative y). */
export function makeBat(): Node {
  return (
    <Node>
      <Rect y={-40} width={15} height={80} radius={7} fill={'#7c2d12'} />
      <Rect y={-150} width={48} height={150} radius={18} fill={'#e0b36a'} stroke={'#a16207'} lineWidth={3} />
    </Node>
  );
}

/** Wooden chair, origin = ground between the legs, `seatH` = seat height above ground. */
export function makeChair(seatH: number): Node {
  return (
    <Node>
      <Rect y={-seatH - 120} width={190} height={250} radius={16} fill={'#a3703a'} />
      <Rect x={-96} y={-seatH / 2} width={16} height={seatH} fill={'#6b4423'} />
      <Rect x={96} y={-seatH / 2} width={16} height={seatH} fill={'#6b4423'} />
      <Rect y={-seatH} width={220} height={20} radius={8} fill={'#8b5a2b'} />
    </Node>
  );
}

/** Impact burst made of 8 rays. Origin = centre. Animate scale + opacity. */
export function makeBurst(): Node {
  const rays = [0, 45, 90, 135, 180, 225, 270, 315].map(a => (
    <Rect rotation={a} y={0} width={9} height={120} radius={4} fill={'#fff7ae'} offset={[0, 1]} />
  ));
  return <Node scale={0} opacity={0}>{rays}</Node>;
}
