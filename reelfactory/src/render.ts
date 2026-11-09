import {renderVideo} from '@revideo/renderer';

// No @types/node installed (we install nothing extra), so declare what we use.
declare const require: any;
declare const process: any;
const fs = require('fs');
const path = require('path');

/**
 * Usage: npm run render -- <scene-name>
 * Renders only src/scenes/<scene-name>.tsx to output/<scene-name>.mp4
 */
async function render() {
  const scenesDir = path.join('src', 'scenes');
  const available: string[] = fs
    .readdirSync(scenesDir)
    .filter((f: string) => f.endsWith('.tsx'))
    .map((f: string) => f.replace(/\.tsx$/, ''));

  const name: string | undefined = process.argv[2];
  if (!name || !/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(name) || !available.includes(name)) {
    console.error(`Usage: npm run render -- <scene-name>`);
    console.error(`Available scenes: ${available.join(', ')}`);
    process.exit(1);
  }

  // Temporary project that contains only the chosen scene.
  const tmpDir = path.join('src', '_render');
  const projectFile = path.join(tmpDir, `${name}.project.tsx`);
  fs.mkdirSync(tmpDir, {recursive: true});
  fs.writeFileSync(
    projectFile,
    [
      `import {makeProject} from '@revideo/core';`,
      `import scene from '../scenes/${name}';`,
      `import {videoSize} from '../settings';`,
      `export default makeProject({scenes: [scene], settings: {shared: {size: videoSize}}});`,
      ``,
    ].join('\n'),
  );

  console.log(`Rendering scene "${name}"...`);
  try {
    const file = await renderVideo({
      projectFile: `./${projectFile.split(path.sep).join('/')}`,
      settings: {
        outFile: `${name}.mp4`,
        outDir: './output',
        logProgress: true,
        projectSettings: {
          exporter: {
            name: '@revideo/core/ffmpeg',
            options: {format: 'mp4'},
          },
        },
      },
    });
    console.log(`Rendered video to ${file}`);
  } finally {
    fs.rmSync(projectFile, {force: true});
  }
}

render();
