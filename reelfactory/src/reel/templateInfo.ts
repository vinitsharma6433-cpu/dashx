// The list of templates and their parameters. Plain data + checks only (no drawing code),
// so both the render script (src/reel.ts) and the scene code can use it.

// Main cast: sachin, surya, dadaji. Everyone else is an original character of the gali (no real people):
// aunty (neighbour), pintu (umpire), golu (small fielder), meena (girl batter), coach (coach uncle), bruno (dog).
export const CHARACTERS = ['sachin', 'surya', 'dadaji', 'aunty', 'pintu', 'golu', 'meena', 'coach', 'bruno'] as const;
export type Who = (typeof CHARACTERS)[number];

/**
 * Parameter kinds:  'who' = one character name, 'who[2]' = list of 2 names, 'text' = a string.
 * `min` = shortest duration (seconds) the template needs to finish its animation.
 */
export const TEMPLATES = {
  'face-off': {
    min: 3.5,
    params: {left: 'who', right: 'who', boardText: 'text', sunset: 'bool'},
  },
  'run-up': {
    min: 4.05,
    params: {batter: 'who', bowler: 'who', sunset: 'bool', near: 'bool'},
  },
  shot: {
    min: 4.05,
    params: {batter: 'who', watcher: 'who', sunset: 'bool'},
  },
  catch: {
    min: 3.2,
    params: {catcher: 'who', watchers: 'who[2]', sunset: 'bool'},
  },
  'hero-end': {
    min: 5,
    params: {cast: 'who[3]'},
  },
  // the closing card of a reel: one short spoken line, at most 5 s, the DASHX name shown once
  'end-card': {min: 4.5, max: 5, params: {}},
} as const;

export type TemplateName = keyof typeof TEMPLATES;
export const TEMPLATE_NAMES = Object.keys(TEMPLATES) as TemplateName[];

const isWho = (v: unknown): boolean =>
  typeof v === 'string' && (CHARACTERS as readonly string[]).includes(v);

/** Return a list of human-readable problems with one scene of script.json (empty = fine). */
export function checkScene(scene: any, index: number): {errors: string[]; warnings: string[]} {
  const errors: string[] = [];
  const warnings: string[] = [];
  const at = `scene ${scene?.id ?? index + 1}`;
  const name = scene?.template;
  if (!name || !(name in TEMPLATES)) {
    errors.push(`${at}: template "${name}" is not one of: ${TEMPLATE_NAMES.join(', ')}`);
    return {errors, warnings};
  }
  const spec = TEMPLATES[name as TemplateName];
  const params = scene.params ?? {};
  for (const [key, value] of Object.entries(params)) {
    const kind = (spec.params as Record<string, string>)[key];
    if (!kind) {
      errors.push(`${at}: template "${name}" has no parameter "${key}" (has: ${Object.keys(spec.params).join(', ')})`);
    } else if (kind === 'who' && !isWho(value)) {
      errors.push(`${at}: params.${key} must be one of ${CHARACTERS.join(', ')}`);
    } else if (kind.startsWith('who[')) {
      const n = Number(kind.slice(4, -1));
      if (!Array.isArray(value) || value.length !== n || !value.every(isWho)) {
        errors.push(`${at}: params.${key} must be a list of ${n} names from ${CHARACTERS.join(', ')}`);
      }
    } else if (kind === 'bool' && typeof value !== 'boolean') {
      errors.push(`${at}: params.${key} must be true or false`);
    } else if (kind === 'text' && typeof value !== 'string') {
      errors.push(`${at}: params.${key} must be text`);
    }
  }
  if (typeof scene.duration !== 'number') {
    errors.push(`${at}: duration must be a number`);
  } else if (scene.duration < spec.min - 0.15) {
    warnings.push(`${at}: duration ${scene.duration}s is shorter than the ${spec.min}s template "${name}" needs`);
  }
  const max = (spec as {max?: number}).max;
  if (typeof scene.duration === 'number' && max !== undefined && scene.duration > max + 0.001) {
    errors.push(`${at}: template "${name}" may last at most ${max}s (got ${scene.duration}s)`);
  }
  return {errors, warnings};
}
