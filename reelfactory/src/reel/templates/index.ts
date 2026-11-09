import type {TemplateName} from '../templateInfo';
import {catchBall} from './catchBall';
import {endCard} from './endCard';
import {faceOff} from './faceOff';
import {heroEnd} from './heroEnd';
import {runUp} from './runUp';
import {shot} from './shot';
import type {Template} from './types';

/** script.json scene.template  ->  the function that draws it. */
export const TEMPLATE_FUNCTIONS: Record<TemplateName, Template> = {
  'face-off': faceOff,
  'run-up': runUp,
  shot,
  catch: catchBall,
  'hero-end': heroEnd,
  'end-card': endCard,
};
