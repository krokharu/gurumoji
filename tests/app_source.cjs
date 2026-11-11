const fs = require('node:fs'), path = require('node:path');
const names = ['app-transcription.js', 'app-progress.js', 'app-results.js', 'app-analysis.js', 'app-library.js', 'app-speakers.js', 'app.js'];
module.exports = (file, encoding) => path.basename(file) === 'app.js' ? names.map(name => fs.readFileSync(path.join(path.dirname(file), name), encoding)).join('\n') : fs.readFileSync(file, encoding);
