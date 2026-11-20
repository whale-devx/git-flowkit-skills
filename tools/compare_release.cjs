// Optional maintainer check. Use the Release Please library from the pinned action.
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { Manifest } = require('release-please');

const root = path.resolve(__dirname, '..');
const configFile = 'release-please-config.json';
const manifestFile = '.release-please-manifest.json';
const config = JSON.parse(fs.readFileSync(path.join(root, configFile), 'utf8'));
const baseSha = config['bootstrap-sha'];
const lastSha = '2'.repeat(40);
const feature = 'feat: support team rules';
const fix = 'fix: retain the selected template';
const cases = [
  { name: 'bootstrap feature', previous: null, messages: [feature], native: '0.1.0', preview: '0.1.0' },
  { name: 'bootstrap fix', previous: null, messages: [fix], native: '0.1.0', preview: '0.0.1' },
  { name: 'bootstrap docs only', previous: null, messages: ['docs: clarify usage'], native: null, preview: null },
  { name: 'released patch', previous: '0.1.0', messages: [fix], native: '0.1.1', preview: '0.1.1' },
  { name: 'pre-major breaking', previous: '0.1.0', messages: ['feat!: rename settings'], native: '0.2.0', preview: '0.2.0' },
  { name: 'stable breaking', previous: '1.2.3', messages: ['fix!: change settings'], native: '2.0.0', preview: '2.0.0' },
  { name: 'no later commits', previous: '0.1.0', messages: [], native: null, preview: null },
];

async function nativePlan(previous, messages) {
  // Supply only read operations. The planner cannot create a PR, tag or release.
  const github = {
    repository: { owner: 'example', repo: 'fixture' },
    async getFileJson(file) {
      if (file === configFile) return config;
      assert.equal(file, manifestFile);
      return { '.': previous ?? '0.0.0' };
    },
    async *releaseIterator() {
      if (previous) yield { name: previous, tagName: 'v' + previous, sha: lastSha };
    },
    async *tagIterator() {},
    async *mergeCommitIterator() {
      for (const [i, message] of messages.entries()) {
        yield { sha: (i + 3).toString(16).padStart(40, '0'), message, files: ['example.txt'] };
      }
      yield { sha: previous ? lastSha : baseSha, message: 'feat: excluded boundary', files: [] };
    },
  };
  const manifest = await Manifest.fromManifest(github, 'main');
  const plans = await manifest.buildPullRequests();
  assert.ok(plans.length <= 1);
  if (!plans.length) return null;
  const [plan] = plans;
  const version = plan.version.toString();
  const updates = new Map(plan.updates.map(update => [update.path, update.updater]));
  assert.deepEqual([...updates.keys()].sort(), [manifestFile, 'CHANGELOG.md', 'version.txt'].sort());
  assert.equal(updates.get('version.txt').updateContent(previous ?? '0.0.0').trim(), version);
  const manifestContent = updates.get(manifestFile).updateContent(JSON.stringify({ '.': previous ?? '0.0.0' }));
  assert.equal(JSON.parse(manifestContent)['.'], version);
  const notes = updates.get('CHANGELOG.md').updateContent('# Changelog\n');
  assert.ok(notes.includes(version) && notes.includes(messages[0].split(': ')[1]));
  assert.ok(!plan.body.toString().includes('excluded boundary'));
  return version;
}

async function main() {
  const fileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'flowkit-release-'));
  try {
    execFileSync('git', ['init', '--quiet', fileDir]);
    fs.copyFileSync(path.join(root, '.git-flowkit.json'), path.join(fileDir, '.git-flowkit.json'));
    const commitsFile = path.join(fileDir, 'commits.json');
    const cli = path.join(root, 'skills/git-flowkit/scripts/flowkit.py');
    for (const test of cases) {
      fs.writeFileSync(commitsFile, JSON.stringify(test.messages));
      const output = execFileSync(process.env.PYTHON || 'python', [
        cli, '--repo', fileDir, 'release-preview', '--current', test.previous ?? '0.0.0', '--commits', commitsFile,
      ], { encoding: 'utf8', env: { ...process.env, GIT_FLOWKIT_NO_GLOBAL: '1', PYTHONDONTWRITEBYTECODE: '1' } });
      const preview = JSON.parse(output).next;
      const native = await nativePlan(test.previous, test.messages);
      assert.equal(preview, test.preview, test.name + ': advisory preview');
      assert.equal(native, test.native, test.name + ': native plan');
      console.log(test.name + ': native=' + native + ', advisory=' + preview);
    }
  } finally {
    fs.rmSync(fileDir, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
