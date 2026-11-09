import {Node, initial, signal} from '@revideo/2d';
import type {NodeProps} from '@revideo/2d';
import type {SignalValue, SimpleSignal} from '@revideo/core';

export interface DotSphereProps extends NodeProps {
  /** Rotation around the vertical axis, in radians. */
  angle?: SignalValue<number>;
  /** Sphere radius in pixels. */
  radius?: SignalValue<number>;
}

const DOTS = 700;
const TILT = -0.35; // look slightly from above
const CAMERA = 1500;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

/**
 * A sphere made of dots (Fibonacci sphere), drawn with a custom draw():
 * rotate, perspective-project, sort far-to-near, fade far dots.
 */
export class DotSphere extends Node {
  @initial(0)
  @signal()
  public declare readonly angle: SimpleSignal<number, this>;

  @initial(300)
  @signal()
  public declare readonly radius: SimpleSignal<number, this>;

  public constructor(props?: DotSphereProps) {
    super({...props});
  }

  protected override async draw(context: CanvasRenderingContext2D) {
    const R = this.radius();
    const ry = this.angle();

    const dots: {x: number; y: number; z: number}[] = [];
    for (let i = 0; i < DOTS; i++) {
      const y = 1 - (2 * (i + 0.5)) / DOTS;
      const r = Math.sqrt(1 - y * y);
      const theta = i * GOLDEN_ANGLE;
      const px = Math.cos(theta) * r;
      const pz = Math.sin(theta) * r;

      // Rotate around Y, then tilt around X.
      const x1 = px * Math.cos(ry) + pz * Math.sin(ry);
      const z1 = -px * Math.sin(ry) + pz * Math.cos(ry);
      const y2 = y * Math.cos(TILT) - z1 * Math.sin(TILT);
      const z2 = y * Math.sin(TILT) + z1 * Math.cos(TILT);
      dots.push({x: x1, y: y2, z: z2});
    }
    dots.sort((a, b) => a.z - b.z); // far to near

    // Soft halo behind the sphere.
    const halo = context.createRadialGradient(0, 0, R * 0.6, 0, 0, R * 1.7);
    halo.addColorStop(0, 'rgba(34, 211, 238, 0.22)');
    halo.addColorStop(1, 'rgba(34, 211, 238, 0)');
    context.fillStyle = halo;
    context.fillRect(-R * 2, -R * 2, R * 4, R * 4);

    context.shadowColor = 'rgba(34, 211, 238, 0.9)';
    context.shadowBlur = 14;
    for (const d of dots) {
      const near = (d.z + 1) / 2; // 0 (far) .. 1 (near)
      const scale = CAMERA / (CAMERA - d.z * R);
      const size = (2 + 5 * near) * scale;
      context.globalAlpha = 0.2 + 0.8 * near;
      context.fillStyle = '#22d3ee';
      context.beginPath();
      context.arc(d.x * R * scale, d.y * R * scale, size, 0, Math.PI * 2);
      context.fill();
    }
    context.globalAlpha = 1;
    context.shadowBlur = 0;
  }
}
