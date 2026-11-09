import {makeProject} from '@revideo/core';

import './fonts.css';
import reelScene from './reelScene';
import {videoSize} from '../settings';

// One generic scene; the script, images and brand files come in as variables
// (see src/reel.ts).
export default makeProject({
  scenes: [reelScene],
  settings: {
    shared: {
      size: videoSize,
    },
  },
});
