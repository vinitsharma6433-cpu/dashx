import {Circle, Gradient, Node, Rect} from '@revideo/2d';

/** One flat house: body, roof edge, windows, door. Bottom sits on the wall (y = -80). */
function house(x: number, w: number, top: number, color: string, roof: string, door: string) {
  const bottom = -80;
  const h = bottom - top;
  const cols = w > 300 ? 3 : 2;
  const gap = w / (cols + 1);
  const windows = [];
  for (let r = 0; r < 2; r++) {
    for (let c = 0; c < cols; c++) {
      windows.push(
        <Rect
          x={-w / 2 + gap * (c + 1)}
          y={-h / 2 + 90 + r * 140}
          width={52}
          height={74}
          radius={8}
          fill={'#fde68a'}
          stroke={'#78350f'}
          lineWidth={6}
        />,
      );
    }
  }
  return (
    <Node x={x} y={(top + bottom) / 2}>
      <Rect width={w} height={h} fill={color} />
      <Rect y={-h / 2 + 12} width={w + 16} height={26} fill={roof} />
      {windows}
      <Rect x={w * 0.22} y={h / 2 - 55} width={64} height={110} radius={[28, 28, 0, 0]} fill={door} />
    </Node>
  );
}

/**
 * The gali: sky, sun, clouds, houses, a brick wall with a chalk wicket on it
 * (x = -300), and the dirt lane in front. `sunset` warms the sky for the last scene.
 */
export function makeBackground(sunset = false): Node {
  const sky = new Gradient({
    type: 'linear',
    from: [0, -960],
    to: [0, -100],
    stops: [
      {offset: 0, color: sunset ? '#f97316' : '#38bdf8'},
      {offset: 1, color: sunset ? '#fde68a' : '#cdeefe'},
    ],
  });
  const lane = new Gradient({
    type: 'linear',
    from: [0, 200],
    to: [0, 960],
    stops: [
      {offset: 0, color: '#d9b57f'},
      {offset: 1, color: '#b98b52'},
    ],
  });

  const bricks = [];
  for (let i = 0; i < 6; i++) {
    bricks.push(<Rect y={-50 + i * 44} width={1080} height={4} fill={'#7c4a2a'} opacity={0.35} />);
  }
  const stones = [
    [-380, 640, 46],
    [300, 760, 34],
    [-120, 860, 52],
    [440, 560, 28],
    [-470, 480, 30],
  ].map(([x, y, s]) => (
    <Circle x={x} y={y} size={[s * 1.6, s]} fill={'#9a7442'} opacity={0.55} />
  ));

  return (
    <Node>
      <Rect size={[1080, 1920]} fill={sky} />
      <Circle x={300} y={-740} size={190} fill={sunset ? '#fff3b0' : '#fde047'} opacity={0.95} />
      <Circle x={-300} y={-800} size={[210, 80]} fill={'#ffffff'} opacity={0.85} />
      <Circle x={-220} y={-830} size={[150, 70]} fill={'#ffffff'} opacity={0.85} />
      <Circle x={-30} y={-640} size={[170, 64]} fill={'#ffffff'} opacity={0.7} />
      {house(-365, 350, -520, '#f4b183', '#c0392b', '#7a4a21')}
      {house(0, 360, -430, '#f1948a', '#8e44ad', '#5d4037')}
      {house(365, 350, -490, '#90caf9', '#1e88e5', '#5d4037')}
      <Rect x={-390} y={-565} width={90} height={60} radius={10} fill={'#64748b'} />
      <Rect y={60} width={1080} height={280} fill={'#c98a5e'} />
      {bricks}
      <Rect y={-80} width={1080} height={24} fill={'#9a6240'} />
      <Rect x={-330} y={105} width={14} height={190} radius={6} fill={'#fffbe6'} opacity={0.95} />
      <Rect x={-300} y={105} width={14} height={190} radius={6} fill={'#fffbe6'} opacity={0.95} />
      <Rect x={-270} y={105} width={14} height={190} radius={6} fill={'#fffbe6'} opacity={0.95} />
      <Rect x={-315} y={8} width={40} height={8} radius={4} fill={'#fffbe6'} />
      <Rect x={-285} y={8} width={40} height={8} radius={4} fill={'#fffbe6'} />
      <Rect y={580} width={1080} height={760} fill={lane} />
      <Rect y={214} width={1080} height={36} fill={'#7a5230'} opacity={0.28} />
      {stones}
      {sunset ? <Rect size={[1080, 1920]} fill={'#f97316'} opacity={0.16} /> : null}
    </Node>
  );
}
