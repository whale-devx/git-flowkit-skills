# Release integration

## Authority and supported scope

Git FlowKit does not replace release engines. A helper preview is explicitly advisory.
It analyzes the supplied single-package Conventional Commits with `.git-flowkit.json`
rules, not every option of a native engine. Native configuration and the native engine's
own plan are authoritative. Never apply a preview number as a forced override.

Detected engine signals: Release Please config/manifest, semantic-release config or
package.json declaration, Changesets config, Python Semantic Release's pyproject section,
release-plz TOML, GoReleaser YAML, and JReleaser config. Multiple detected tools require
an explicit version owner, even when one is intentionally only a packaging tool.
No detected file means no engine; it does not imply no release automation exists.

The built-in preview rejects recognized monorepos, reverts, shallow Git history, malformed
commits, an existing local target tag, and continuation/promotion of an existing prerelease.
It reads non-merge commits after a verified ancestor. Under squash workflows the squash
subject/footer must be conventional. Under merge/rebase workflows the individual commits
must carry the correct release impact. Supply the actual last-release boundary, not an
arbitrary recent commit. Remote tag collisions are not checked by this offline CLI.

## New repositories: Release Please scaffold

```text
python <skill>/scripts/flowkit.py --repo <repo> release-setup
python <skill>/scripts/flowkit.py --repo <repo> release-setup --apply
```

This creates a `simple` strategy config, manifest, version.txt, changelog, and an opt-in
GitHub Actions workflow. It refuses existing engines or tags, recognized workspaces,
inconsistent version.txt, and custom rules/tag prefixes it cannot safely translate.
Setup reads local Git history. Fetch full history, tags and the release branch before
running it in a clone. `--branch` defaults to `main`. Its tip sets the bootstrap
boundary, push trigger and Release Please target. You can prepare the files on a
feature branch and squash the setup PR. Older features on the release branch stay
outside the first release plan.

The branch must exist locally or as `origin/<branch>`. When both refs exist they
must agree. For a differently named remote, create or update the local release
branch from the intended remote before setup. Shallow history, a missing branch
or conflicting tips stop both preview and apply before any files are written.
`--initial-version` writes the baseline to `.release-please-manifest.json` and
`version.txt`. Choose the starting point before applying the scaffold.

| Intended start | Setup | First candidate in the tagless fixture |
| --- | --- | --- |
| New project using native defaults | Keep the default baseline of `0.0.0`. | A `feat:` produced `1.0.0`. A docs-only change produced no candidate. |
| New project targeting `0.1.0` | Keep the baseline at `0.0.0`. In `release-please-config.json`, add `"initial-version": "0.1.0"` inside `packages["."]`. | A `fix:` produced `0.1.0`. |
| Project already at `1.4.2` | Pass `--initial-version 1.4.2`. | A `fix:` produced `1.4.3`. |

These examples used Release Please 17.3.0 from the generated workflow's
pinned action. They apply to ordinary commits after the bootstrap boundary.

The generic scaffold cannot know the target project's test commands. Before enabling,
connect the project's required tests and protections. The scaffold is not evidence that
application tests have passed. Use the repo's existing engine for a migration or monorepo.

## This repository's release activation

The repository starts at **0.0.0, unreleased**. Its manifest uses the inspected initial
commit as the bootstrap boundary. The root package explicitly sets its native
`initial-version` to `0.1.0`. With a tagless `0.0.0` manifest, Release
Please 17.6.0 otherwise proposed `1.0.0` for a feature in an offline comparison.
A docs-only fixture produced no candidate. After an existing `0.1.0` release,
a fix proposed `0.1.1`. The advisory helper still computes from its supplied
baseline, so a fix against `0.0.0` yields `0.0.1` in the helper.

1. Check the native release plan against the current branch history using the dry runs below.
2. Verify the six OS/Python test jobs, installation job and policy job. Configure required checks and
   review protection on the default branch; these settings are not changed by this PR.
3. Permit Actions to create pull requests where repository/organization policy requires it.
4. Explicitly set repository variable `FLOWKIT_RELEASE_ENABLED` to `true`.
5. Run the `CI` workflow manually on `main`, or push the next approved change to `main`.
   The release job depends on the full test matrix, installation and policy jobs.
6. Review the generated release PR and its CI, then merge it. Release Please creates
   the Git tag/GitHub Release. No npm/PyPI or other registry publish step is installed.

The workflow uses pinned action commit SHAs and a separate narrowly-permissioned release
job. Fork PR code has no access to that job. There is no auto-merge or review bypass.

### Preview the first release against repository history

With Release Please 17.6.0 and a credential that can read the repository,
run both dry runs against the branch under review. Replace the token file
path with an existing local credential file.

```sh
release-please release-pr --repo-url whale-devx/git-flowkit-skills --target-branch main --token /path/to/read-token --dry-run --trace
release-please github-release --repo-url whale-devx/git-flowkit-skills --target-branch main --token /path/to/read-token --dry-run
```

On 2026-11-21 the planner read 15 commits after bootstrap on
[`a15e6e0`](https://github.com/whale-devx/git-flowkit-skills/commit/a15e6e024d39c93592f655d5a903c15342d5c45f).
The live configuration proposed `1.0.0`. Replaying the same GitHub responses
with only the proposed first-version setting yielded `0.1.0`. Both plans
updated the changelog, version file and manifest. The tag dry run found
zero releases eligible for publication.

Review the entries as well as the version. The first plan listed the same
foundation feature under its merge commit `76d1a4a` and implementation
commit `724bb8b`. When reviewing the generated release PR, keep one entry
for that feature and check the overlapping template fixes against their
diffs. Compare the release PR body with the changelog before approval.
[Merge commit](https://github.com/whale-devx/git-flowkit-skills/commit/76d1a4a397821da5d71a82280f2113e2c9e60bc2)
and [implementation commit](https://github.com/whale-devx/git-flowkit-skills/commit/724bb8b0d077142fc22f2274d342656cb50a9bbb).

### Recover a release after an interrupted run

Release Please requests the GitHub Release at the merged release PR's commit before
posting the PR comment and changing its labels. A later error can leave a published
release behind. Compare the merged PR, tag and release before retrying. Set `pr` to
the release PR number and `tag` to its expected tag, then run these read-only checks
in the repository checkout.

```sh
gh pr view "$pr" --json mergeCommit,mergedAt,labels,url
git ls-remote --exit-code origin "refs/tags/$tag" "refs/tags/$tag^{}"
gh release view "$tag" --json tagName,targetCommitish,isDraft,isPrerelease,url
```

For an annotated tag, compare the peeled `^{}` commit with the PR's merge commit.
For a lightweight tag, compare the tag's only SHA. If either read fails, establish
access and check the exact tag before taking action. If the commits differ, stop
and investigate with the maintainer.

For a published example, the three reads for upstream Release Please PR #2752
returned merge commit `712fcf0`, the same commit for the lightweight `v17.6.0`
tag and release target, and the PR label `autorelease: tagged`.
[Merged upstream PR](https://github.com/googleapis/release-please/pull/2752) · [Upstream release](https://github.com/googleapis/release-please/releases/tag/v17.6.0)

The pinned v5.0.0 action produced these results against a local GitHub API fixture
with the repository's `0.1.0` release plan.

| First run | State after the run | What the next run did |
| --- | --- | --- |
| Successful run | One release at the merge commit, PR labeled `autorelease: tagged` | Made no release or label requests. |
| PR comment failed after release creation | One release, PR still labeled `autorelease: pending` | Received a duplicate-release error, switched the PR to `autorelease: tagged` and exited with an error. The following run made no release or label requests. |
| Adding `autorelease: tagged` failed after removing `autorelease: pending` | One release, PR missing both release labels | Exited successfully without repairing the label. A maintainer can restore it after verifying the release and tag. |

These checks used an isolated service and fixture credentials. A hosted rehearsal
still requires maintainer approval. [Pinned release action](https://github.com/googleapis/release-please-action/blob/45996ed1f6d02564a971a2fa1b5860e934307cf7/src/index.ts) · [Release Please 17.6.0 implementation](https://github.com/googleapis/release-please/blob/712fcf01effd08d7b0e7b1fd3861f2cb388bc8d1/src/manifest.ts)

## Token behavior

The default is `GITHUB_TOKEN`. GitHub's current documentation says automation-created
`pull_request` opened/synchronize/reopened events may require a maintainer to approve
workflow runs. Other token-created events, including tag/release events, generally do
not start follow-on workflows; workflow_dispatch/repository_dispatch are exceptions.
Do not assume a downstream publishing workflow has run. For unattended chaining, design
a least-privilege GitHub App installation-token flow separately. No token is requested
or stored by the offline helpers. See the [primary sources](sources.md).

## Adopting other engines

| Existing engine | Integration rule |
| --- | --- |
| semantic-release | Preserve branches, presets, parser options, releaseRules and plugins. Use its own documented dry run; even a dry run may access the network/verify permissions. |
| Changesets | Preserve changeset files, fixed/linked groups and dependency bump policies. Use its native status/version workflow, not commit-only arithmetic. |
| Python Semantic Release | Preserve pyproject configuration and package metadata; use the installed version's documented preview. |
| release-plz | Preserve workspace configuration and Cargo dependencies; delegate package version propagation. |
| GoReleaser / JReleaser | Establish which tool owns version assignment versus packaging/publishing. Do not infer that packaging computes SemVer. |

These are adoption instructions and detection support, not implemented execution adapters.
Do not install a second version owner for the same package. Prerelease continuation,
maintenance branches, signing, provenance, registries, and rollback procedures belong
to a reviewed native pipeline. Never fix a released artifact by moving its immutable tag.
