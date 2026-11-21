// Optional comparison for the repository's pinned Release Please engine.
const assert = require('node:assert/strict');
const { Manifest } = require('release-please');
const { GitHubApi } = require('release-please/build/src/github-api');
const { RequestError } = require('@octokit/request-error');

async function exercise(config, plan, failedOperation) {
  const repository = { owner: 'example', repo: 'fixture' };
  const number = 12;
  const mergeSha = 'a'.repeat(40);
  const releaseUrl = 'https://example.invalid/fixture/releases/tag/v0.1.0';
  const labels = new Set([...plan.labels, 'maintainer-reviewed-fixture']);
  const calls = [];
  let merged = false;
  let published;
  // Only these four in-memory Octokit endpoints are available to the native GitHub adapter.
  const octokit = {
    repos: {
      async createRelease(request) {
        calls.push('release');
        assert.deepEqual(request, {
          ...repository, name: 'v0.1.0', tag_name: 'v0.1.0', target_commitish: mergeSha,
          body: plan.body.releaseData[0].notes, draft: false, prerelease: false,
        });
        if (published) {
          throw new RequestError('Validation Failed', 422, {
            request: { method: 'POST', url: releaseUrl, headers: {} },
            response: { headers: {}, data: { errors: [{ resource: 'Release', code: 'already_exists', field: 'tag_name' }] } },
          });
        }
        published = { ...request, id: 1, html_url: releaseUrl };
        return { data: published };
      },
    },
    issues: {
      async createComment(request) {
        calls.push('comment');
        assert.equal(request.issue_number, number);
        assert.ok(request.body.includes(releaseUrl));
        if (failedOperation === 'comment') throw new Error('fixture comment write failed');
        return { data: { html_url: 'https://example.invalid/fixture/comment/1' } };
      },
      async removeLabel(request) {
        calls.push('remove pending');
        assert.equal(request.issue_number, number);
        assert.equal(request.name, 'autorelease: pending');
        assert.ok(labels.delete(request.name));
      },
      async addLabels(request) {
        calls.push('add tagged');
        assert.equal(request.issue_number, number);
        assert.deepEqual(request.labels, ['autorelease: tagged']);
        if (failedOperation === 'label') throw new Error('fixture label write failed');
        labels.add(request.labels[0]);
      },
    },
  };
  const api = new GitHubApi({ repository, octokitAPIs: { octokit } });
  const github = {
    repository,
    createRelease: api.createRelease,
    commentOnIssue: api.commentOnIssue,
    removeIssueLabels: api.removeIssueLabels,
    addIssueLabels: api.addIssueLabels,
    async getFileJson(file) {
      if (file === 'release-please-config.json') return config;
      assert.equal(file, '.release-please-manifest.json');
      return { '.': merged ? plan.version.toString() : '0.0.0' };
    },
    async *pullRequestIterator(branch, state) {
      assert.equal(branch, 'main');
      assert.equal(state, 'MERGED');
      if (merged) yield {
        number, title: plan.title.toString(), body: plan.body.toString(), labels: [...labels],
        headBranchName: plan.headRefName, baseBranchName: branch, sha: mergeSha,
        files: plan.updates.map(update => update.path),
      };
    },
  };
  // Each run loads the repository again, as a fresh hosted invocation would.
  async function run() {
    const manifest = await Manifest.fromManifest(github, 'main');
    return manifest.createReleases();
  }
  assert.deepEqual(await run(), []);
  assert.deepEqual(calls, []);
  merged = true;
  if (failedOperation === 'comment') {
    await assert.rejects(run(), /fixture comment write failed/);
    assert.deepEqual(calls, ['release', 'comment']);
    assert.ok(labels.has('autorelease: pending'));
    await assert.rejects(run(), { name: 'DuplicateReleaseError' });
    assert.deepEqual(calls, ['release', 'comment', 'release', 'remove pending', 'add tagged']);
    assert.deepEqual([...labels].sort(), ['autorelease: tagged', 'maintainer-reviewed-fixture']);
  } else if (failedOperation === 'label') {
    await assert.rejects(run(), /fixture label write failed/);
    assert.deepEqual([...labels], ['maintainer-reviewed-fixture']);
  } else {
    const releases = await run();
    assert.deepEqual(releases.map(release => [release.tagName, release.sha, release.prNumber]),
      [['v0.1.0', mergeSha, number]]);
    assert.deepEqual([...labels].sort(), ['autorelease: tagged', 'maintainer-reviewed-fixture']);
  }
  if (failedOperation !== 'comment') assert.deepEqual(calls, ['release', 'comment', 'remove pending', 'add tagged']);
  assert.equal(published.target_commitish, mergeSha);
  const previousCalls = [...calls];
  assert.deepEqual(await run(), []);
  assert.deepEqual(calls, previousCalls, 'a rerun must not request another release or label update');
}

async function verifyReleaseCycle(config, plan) {
  assert.ok(plan, 'a first release PR must exist');
  for (const failedOperation of [undefined, 'comment', 'label']) {
    await exercise(config, plan, failedOperation);
  }
  console.log('First release, rerun and recovery after comment or label write failures verified.');
}

module.exports = { verifyReleaseCycle };
