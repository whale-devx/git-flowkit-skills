# Roadmap and acceptance gates

| Milestone | Dependency and acceptance evidence |
| --- | --- |
| M1 Installable foundation | Run both [installer journeys](tools/install_smoke.py), the offline suite and current-head CI. The Windows CRLF regression requires the candidate fix. |
| M2 Public alpha | M1 plus one agent passing the [recorded scenarios](skills/git-flowkit/references/compatibility.md), safety regressions and reviewed support limits. |
| M3 Reliable beta | M2 plus a second independent agent, native Release Please comparisons and an authorized rehearsal covering version, changelog, tag, GitHub Release and repeat run. |
| M4 Stable scoped release | M3 plus migration instructions, security review, repeated real-project use and closure of critical safety/release issues. |
| M5 Demand-led expansion | Add fixture-driven native semantic-release and Changesets behavior, package selection, prerelease and maintenance channels, then read-only provider evidence with pagination, permissions, review semantics, queues and HEAD races. Design publishing/signing separately. |

Use reproducible setup reports, repeat use, policy errors and reported defects to
prioritize changes. Keep telemetry opt-in. Distribution candidates include project
documentation and community tutorials when maintainers approve publication.

## Reproduce the native version comparison

The [maintainer comparison](tools/compare_release.cjs) invokes the Python CLI
from the source tree and the native Release Please
manifest planner. Its GitHub fixture supplies configuration, releases, tags and
commit history in memory. It checks the proposed version and the content that
the native engine would write to the version file, manifest and changelog.
This exercises the planning gate for M3. Publishing and repeated hosted release
runs require the separate rehearsal.

From a Git FlowKit checkout, fetch the manifest and lockfile from the same
action revision pinned in CI into a temporary directory. These commands require
GitHub CLI and npm for setup. The comparison itself uses the local files.

```sh
deps=$(mktemp -d)
action_ref=45996ed1f6d02564a971a2fa1b5860e934307cf7
for file in package.json package-lock.json; do
  gh api -H 'Accept: application/vnd.github.raw+json' \
    "repos/googleapis/release-please-action/contents/$file?ref=$action_ref" > "$deps/$file" || exit 1
done
npm ci --prefix "$deps" --omit=dev --ignore-scripts --no-audit --no-fund
NODE_PATH="$deps/node_modules" node tools/compare_release.cjs
```

On Windows, set `NODE_PATH` to the same absolute `node_modules` directory.
The 2026-11-21 run used Node 24.19.0 and Release Please 17.6.0. All seven
cases passed, including a fix-only bootstrap where native and advisory
versions intentionally differ. No hosted release workflow was dispatched.
