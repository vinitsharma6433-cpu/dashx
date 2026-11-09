import {renderVideo} from '@revideo/renderer';

import {checkScene} from './reel/templateInfo';

// No @types/node installed, so declare what we use (same trick as render.ts).
declare const require: any;
declare const process: any;
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');

const LEAD = 0.25; // seconds of silence before each voice line

/** Pick the first existing file from a list, else undefined. */
function firstExisting(files: string[]): string | undefined {
  return files.find(f => fs.existsSync(f));
}

/**
 * Usage: npm run reel -- <reel-name>
 * Reads reels/<name>/script.json (+ audio/) and writes
 * output/reels/<name>.mp4  (1080x1920, voice-over mixed in).
 */
async function reel() {
  const name: string | undefined = process.argv[2];
  if (!name || !/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(name)) {
    console.error('Usage: npm run reel -- <reel-name>   (e.g. last-ball)');
    process.exit(1);
  }
  const dir = path.join('reels', name);
  const scriptFile = path.join(dir, 'script.json');
  if (!fs.existsSync(scriptFile)) {
    console.error(`Missing ${scriptFile}`);
    process.exit(1);
  }
  const script = JSON.parse(fs.readFileSync(scriptFile, 'utf-8'));

  // Check every scene (template name, parameters, duration) before the slow render starts.
  const problems = (script.scenes as any[]).map((sc, i) => checkScene(sc, i));
  problems.forEach(p => p.warnings.forEach(w => console.warn(`Warning: ${w}`)));
  const errors = problems.flatMap(p => p.errors);
  if (errors.length > 0) {
    errors.forEach(e => console.error(`Error: ${e}`));
    process.exit(1);
  }

  // 1. Copy the brand files into public/ so the renderer can serve them (scenes are drawn in code).
  const pub = path.join('public', '_reel', name);
  fs.mkdirSync(pub, {recursive: true});
  // Real files (assets/dashx-logo.jpg|png, assets/hero-ball.jpg|png) win over placeholders.
  const brandFile = (base: string) =>
    firstExisting([
      path.join('assets', `${base}.jpg`),
      path.join('assets', `${base}.jpeg`),
      path.join('assets', `${base}.png`),
      path.join('assets', `${base}.placeholder.png`),
    ]);
  const brandUrl = (base: string) => {
    const f = brandFile(base);
    if (!f) {
      console.error(`Missing brand file for ${base} in assets/`);
      process.exit(1);
    }
    const out = `${base}${path.extname(f)}`;
    fs.copyFileSync(f, path.join(pub, out));
    console.log(`${base}: using ${f}`);
    return `/_reel/${name}/${out}`;
  };
  const logo = brandUrl('dashx-logo');
  const ball = brandUrl('hero-ball');

  // 2. Render the silent video with revideo.
  const outDir = path.join('output', 'reels');
  fs.mkdirSync(outDir, {recursive: true});
  console.log(`Rendering reel "${name}"...`);
  const videoFile: string = await renderVideo({
    projectFile: './src/reel/project.tsx',
    variables: {name, script, logo, ball},
    settings: {
      outFile: `${name}-video.mp4`,
      outDir: `./${outDir.split(path.sep).join('/')}`,
      logProgress: true,
      // GitHub Actions runners cannot start Chromium's sandbox
      ...(process.env.DASHX_CI ? {puppeteer: {args: ['--no-sandbox', '--disable-setuid-sandbox']}} : {}),
      projectSettings: {
        exporter: {name: '@revideo/core/ffmpeg', options: {format: 'mp4'}},
      },
    },
  });

  // 3. Mix the per-scene voice lines onto the video with ffmpeg.
  const ffmpeg: string = require('@ffmpeg-installer/ffmpeg').path;
  const finalFile = path.join(outDir, `${name}.mp4`);
  // Every scene gets one audio segment of exactly its duration: a short lead of
  // silence, the voice line, then silence. The segments are concatenated, so
  // the voice always lines up with its scene (works on old ffmpeg builds too).
  const voices: {file: string; duration: number}[] = [];
  for (const sc of script.scenes) {
    const wav = path.join(dir, 'audio', `scene-${sc.id}.wav`);
    if (!fs.existsSync(wav)) {
      console.warn(`No voice for scene ${sc.id} (${wav})`);
      continue;
    }
    voices.push({file: wav, duration: sc.duration});
  }
  if (voices.length !== script.scenes.length) {
    // Missing voice lines: keep the video silent rather than mis-timed.
    fs.copyFileSync(videoFile, finalFile);
  } else {
    const args = ['-v', 'error', '-y', '-i', videoFile];
    voices.forEach(v => args.push('-i', v.file));
    const segments = voices.map(
      (v, i) =>
        `[${i + 1}:a]adelay=${Math.round(LEAD * 1000)}|${Math.round(LEAD * 1000)},` +
        `apad,atrim=0:${v.duration},asetpts=N/SR/TB[a${i}]`,
    );
    const mix =
      voices.map((_, i) => `[a${i}]`).join('') +
      `concat=n=${voices.length}:v=0:a=1,loudnorm=I=-16:TP=-1.5:LRA=11[aout]`;
    args.push(
      '-filter_complex',
      [...segments, mix].join(';'),
      '-map',
      '0:v',
      '-map',
      '[aout]',
      '-c:v',
      'copy',
      '-c:a',
      'aac',
      '-b:a',
      '160k',
      '-shortest',
      finalFile,
    );
    execFileSync(ffmpeg, args, {stdio: 'inherit'});
  }
  fs.rmSync(videoFile, {force: true});
  console.log(`Reel ready: ${finalFile}`);
}

reel();
