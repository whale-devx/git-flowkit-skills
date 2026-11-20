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
const cli = path.join(root, 'skills/git-flowkit/scripts/flowkit.py');
function readJson(dir, file) {
  return JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
}

function flowkit(dir, ...args) {
  return execFileSync(process.env.PYTHON || 'python', [cli, '--repo', dir, ...args], {
    encoding: 'utf8', env: { ...process.env, GIT_FLOWKIT_NO_GLOBAL: '1', PYTHONDONTWRITEBYTECODE: '1' },
  });
}

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

async function nativePlan(dir, previous, messages, history) {
  const config = readJson(dir, configFile);
  const initialManifest = previous ? { '.': previous } : readJson(dir, manifestFile);
  // Supply only read operations. The planner cannot create a PR, tag or release.
  const github = {
    repository: { owner: 'example', repo: 'fixture' },
    async getFileJson(file) {
      if (file === configFile) return config;
      assert.equal(file, manifestFile);
      return initialManifest;
    },
    async *releaseIterator() {
      if (previous) yield { name: previous, tagName: 'v' + previous, sha: lastSha };
    },
    async *tagIterator() {},
    async *mergeCommitIterator() {
      if (history) {
        yield* history;
        return;
      }
      for (const [i, message] of messages.entries()) {
        yield { sha: (i + 3).toString(16).padStart(40, '0'), message, files: ['example.txt'] };
      }
      yield { sha: previous ? lastSha : config['bootstrap-sha'], message: 'feat: excluded boundary', files: [] };
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
  const before = previous ?? fs.readFileSync(path.join(dir, 'version.txt'), 'utf8').trim();
  assert.equal(before, initialManifest['.']);
  assert.equal(updates.get('version.txt').updateContent(before).trim(), version);
  const manifestContent = updates.get(manifestFile).updateContent(JSON.stringify(initialManifest));
  assert.equal(JSON.parse(manifestContent)['.'], version);
  const notes = updates.get('CHANGELOG.md').updateContent(fs.readFileSync(path.join(dir, 'CHANGELOG.md'), 'utf8'));
  assert.ok(notes.includes(version));
  assert.ok(!notes.includes('excluded boundary'));
  if (messages.length) assert.ok(notes.includes(messages[0].split(': ')[1]));
  assert.ok(!plan.body.toString().includes('excluded boundary'));
  return version;
}

async function checkSquashBootstrap(tempDir) {
  const dir = path.join(tempDir, 'squash');
  fs.mkdirSync(dir);
  function git(...args) {
    return execFileSync('git', ['-C', dir, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
      '-c', 'core.hooksPath=', '-c', 'commit.gpgsign=false', ...args], { encoding: 'utf8' }).trim();
  }
  function commitsOnMain() {
    return git('log', 'main', '--format=%H%x00%s').split('\n').map(line => {
      const [sha, message] = line.trim().split('\0');
      const changes = git('diff-tree', '--root', '--no-commit-id', '-r', '--name-only', sha);
      return { sha, message, files: changes ? changes.split(/\r?\n/) : [] };
    });
  }
  git('init', '-q', '-b', 'main');
  fs.writeFileSync(path.join(dir, 'project.txt'), 'initial feature\n');
  git('add', 'project.txt');
  git('commit', '-qm', 'feat: excluded boundary');
  git('commit', '--allow-empty', '-qm', 'docs: describe initial feature');
  git('switch', '-q', '-c', 'chore/setup');
  git('commit', '--allow-empty', '-qm', 'chore: prepare release tooling');
  flowkit(dir, 'release-setup', '--apply');
  git('add', '.');
  git('commit', '-qm', 'chore: add release configuration');
  git('switch', '-q', 'main');
  git('merge', '--squash', 'chore/setup');
  git('commit', '-qm', 'chore: configure release tooling');
  const before = await nativePlan(dir, null, [], commitsOnMain());
  assert.equal(before, null, 'squashed setup should exclude historical features, got ' + before);
  fs.appendFileSync(path.join(dir, 'project.txt'), 'team rules\n');
  git('commit', '-qam', feature);
  const after = await nativePlan(dir, null, [feature], commitsOnMain());
  assert.equal(after, '1.0.0');
  console.log('squash setup: native=' + before + ', after feature=' + after);
}

async function checkScaffold(tempDir) {
  // Each case starts in its own tagless repository with the shipped CLI's files.
  for (const test of [
    { name: 'default', args: [], message: feature, expected: '1.0.0' },
    { name: 'docs-only', args: [], message: 'docs: clarify usage', expected: null },
    { name: 'seeded', args: ['--initial-version', '1.4.2'], message: fix, expected: '1.4.3' },
    { name: 'explicit-first', args: [], first: '0.1.0', message: fix, expected: '0.1.0' },
  ]) {
    const dir = path.join(tempDir, test.name);
    execFileSync('git', ['init', '--quiet', '-b', 'main', dir]);
    execFileSync('git', ['-C', dir, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
      '-c', 'core.hooksPath=', 'commit', '--no-gpg-sign', '--allow-empty', '-qm', 'chore: initialize']);
    flowkit(dir, 'release-setup', ...test.args, '--apply');
    const config = readJson(dir, configFile);
    const head = execFileSync('git', ['-C', dir, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    assert.equal(config['bootstrap-sha'], head);
    if (test.first) {
      config.packages['.']['initial-version'] = test.first;
      fs.writeFileSync(path.join(dir, configFile), JSON.stringify(config));
    }
    const native = await nativePlan(dir, null, [test.message]);
    assert.equal(native, test.expected, test.name);
    console.log(test.name + ': native=' + native);
  }
  await checkSquashBootstrap(tempDir);
}

async function main() {
  const args = process.argv.slice(2);
  assert.ok(args.length === 0 || (args.length === 1 && args[0] === '--scaffold'),
    'Usage: node tools/compare_release.cjs [--scaffold]');
  const scaffold = args[0] === '--scaffold';
  const [workflow, action, engine] = scaffold
    ? ['skills/git-flowkit/assets/release-please/workflow.yml', '5c625bfb5d1ff62eadeeb3772007f7f66fdcf071', '17.3.0']
    : ['.github/workflows/ci.yml', '45996ed1f6d02564a971a2fa1b5860e934307cf7', '17.6.0'];
  assert.ok(fs.readFileSync(path.join(root, workflow), 'utf8').includes('uses: googleapis/release-please-action@' + action),
    'Workflow pin changed. Check the action lockfile and update the comparison.');
  assert.equal(require('release-please/package.json').version, engine, 'Use the dependencies from ' + workflow);
  const fileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'flowkit-release-'));
  try {
    if (scaffold) {
      await checkScaffold(fileDir);
      return;
    }
    execFileSync('git', ['init', '--quiet', fileDir]);
    fs.copyFileSync(path.join(root, '.git-flowkit.json'), path.join(fileDir, '.git-flowkit.json'));
    const commitsFile = path.join(fileDir, 'commits.json');
    for (const test of cases) {
      fs.writeFileSync(commitsFile, JSON.stringify(test.messages));
      const output = flowkit(fileDir, 'release-preview', '--current', test.previous ?? '0.0.0', '--commits', commitsFile);
      const preview = JSON.parse(output).next;
      const native = await nativePlan(root, test.previous, test.messages);
      assert.equal(preview, test.preview, test.name + ': advisory preview');
      assert.equal(native, test.native, test.name + ': native plan');
      console.log(test.name + ': native=' + native + ', advisory=' + preview);
    }
  } finally {
    fs.rmSync(fileDir, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
