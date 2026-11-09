import {Node, initial, signal} from '@revideo/2d';
import type {NodeProps} from '@revideo/2d';
import type {SignalValue, SimpleSignal} from '@revideo/core';

export interface CubeProps extends NodeProps {
  /** Rotation around the vertical axis, in radians. */
  angle?: SignalValue<number>;
  /** Edge length of the cube in pixels. */
  edge?: SignalValue<number>;
}

type Vec3 = [number, number, number];

// Each face: its outward normal and two in-plane axes (u, v).
const FACES: {n: Vec3; u: Vec3; v: Vec3}[] = [
  {n: [0, 0, 1], u: [1, 0, 0], v: [0, 1, 0]},
  {n: [0, 0, -1], u: [1, 0, 0], v: [0, 1, 0]},
  {n: [1, 0, 0], u: [0, 0, 1], v: [0, 1, 0]},
  {n: [-1, 0, 0], u: [0, 0, 1], v: [0, 1, 0]},
  {n: [0, 1, 0], u: [1, 0, 0], v: [0, 0, 1]},
  {n: [0, -1, 0], u: [1, 0, 0], v: [0, 0, 1]},
];

const CORNERS: [number, number][] = [
  [-1, -1],
  [1, -1],
  [1, 1],
  [-1, 1],
];

// Negative tilt (screen y points down) = camera looks from above, so the
// TOP face is visible and the bottom face is always hidden.
const TILT = -0.5;
const CAMERA = 1400; // camera distance for perspective
// Light comes from the upper left, in front of the cube.
const LIGHT: Vec3 = [-0.6, -0.8, 0.5];
const AMBIENT = 0.22;

/**
 * A glowing cube drawn with a custom draw(): simple 3D rotation,
 * perspective projection, painter's sort and flat shading on a 2D canvas.
 */
export class Cube extends Node {
  @initial(0)
  @signal()
  public declare readonly angle: SimpleSignal<number, this>;

  @initial(380)
  @signal()
  public declare readonly edge: SimpleSignal<number, this>;

  public constructor(props?: CubeProps) {
    super({...props});
  }

  // Rotate around Y by `ry`, then around X by TILT.
  private rotate([x, y, z]: Vec3, ry: number): Vec3 {
    const x1 = x * Math.cos(ry) + z * Math.sin(ry);
    const z1 = -x * Math.sin(ry) + z * Math.cos(ry);
    const y2 = y * Math.cos(TILT) - z1 * Math.sin(TILT);
    const z2 = y * Math.sin(TILT) + z1 * Math.cos(TILT);
    return [x1, y2, z2];
  }

  protected override async draw(context: CanvasRenderingContext2D) {
    const half = this.edge() / 2;
    const ry = this.angle();
    const len = Math.hypot(...LIGHT);

    const project = ([x, y, z]: Vec3): [number, number] => {
      const s = CAMERA / (CAMERA - z);
      return [x * s, y * s];
    };

    // Soft halo behind the cube.
    const halo = context.createRadialGradient(0, 0, 0, 0, 0, half * 2.6);
    halo.addColorStop(0, 'rgba(56, 189, 248, 0.35)');
    halo.addColorStop(1, 'rgba(56, 189, 248, 0)');
    context.fillStyle = halo;
    context.fillRect(-half * 3, -half * 3, half * 6, half * 6);

    const faces = FACES.map(({n, u, v}) => {
      const normal = this.rotate(n, ry);
      const pts = CORNERS.map(([su, sv]) =>
        this.rotate(
          [
            half * (n[0] + su * u[0] + sv * v[0]),
            half * (n[1] + su * u[1] + sv * v[1]),
            half * (n[2] + su * u[2] + sv * v[2]),
          ],
          ry,
        ),
      );
      const depth = pts.reduce((sum, p) => sum + p[2], 0) / 4;
      return {normal, pts, depth};
    })
      .filter(face => face.normal[2] > 0) // keep only faces looking at us
      .sort((a, b) => a.depth - b.depth); // far to near

    context.lineJoin = 'round';
    for (const {normal, pts} of faces) {
      const light =
        (normal[0] * LIGHT[0] + normal[1] * LIGHT[1] + normal[2] * LIGHT[2]) /
        len;
      // Ambient + diffuse: each face gets its own brightness.
      const lum = AMBIENT + (1 - AMBIENT) * Math.max(0, light);
      const [r, g, b] = [56, 189, 248].map(c => Math.round(c * lum));

      context.beginPath();
      pts.map(project).forEach(([x, y], i) => {
        if (i === 0) {
          context.moveTo(x, y);
        } else {
          context.lineTo(x, y);
        }
      });
      context.closePath();

      // Glow: shadow of the same colour around every face.
      context.shadowColor = 'rgba(56, 189, 248, 0.9)';
      context.shadowBlur = 60;
      context.fillStyle = `rgba(${r}, ${g}, ${b}, 0.92)`;
      context.fill();

      context.shadowBlur = 0;
      context.strokeStyle = '#e0f2fe';
      context.lineWidth = 5;
      context.stroke();
    }
  }
}
