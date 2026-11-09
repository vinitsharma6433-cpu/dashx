import {makeProject} from '@revideo/core';

import {videoSize} from './settings';

// Register every scene here (this is what `npm start` / the editor plays).
import intro from './scenes/intro';
import cube from './scenes/cube';
import sphere from './scenes/sphere';

export default makeProject({
  scenes: [intro, cube, sphere],
  settings: {
    shared: {
      size: videoSize,
    },
  },
});
