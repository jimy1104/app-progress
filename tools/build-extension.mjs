// Copies the shared engines from the web app into the extension.
// Run after changing js/*.js:  node tools/build-extension.mjs
import { copyFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
for (const f of ['subtitles.js', 'grammar.js', 'game.js', 'translate.js', 'dictionary.js', 'i18n.js']) {
  copyFileSync(join(root, 'js', f), join(root, 'extension', 'lib', f));
  console.log('copied', f);
}
console.log('Now re-create englishpro-extension.zip (zip -r englishpro-extension.zip extension).');
