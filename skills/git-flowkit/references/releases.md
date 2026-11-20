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
It never overwrites existing files. Bootstrap starts after the current HEAD; only
subsequent conventional changes are included. Review this boundary for existing code.
`--initial-version` is the baseline, not a promise to publish that exact version.

The generic scaffold cannot know the target project's test commands. Before enabling,
connect the project's required tests and protections. The scaffold is not evidence that
application tests have passed. Use the repo's existing engine for a migration or monorepo.

## This repository's release activation

The repository starts at **0.0.0, unreleased**. Its manifest uses the inspected initial
commit as the bootstrap boundary. With the current feature implementation and pre-1.0
policy, the intended first normal release is 0.1.0; the engine computes the actual result.

1. PR #1 merged with a merge commit. After bootstrap `c35420a`, the retained non-merge
   commits include feature `724bb8b` and fix `2a252fa`. Inspect the native release PR
   against this history before approving a version. Native output remains unverified.
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
