# Roadmap and acceptance gates

| Milestone | Dependency and acceptance evidence |
| --- | --- |
| M1 Installable foundation | Run both [installer journeys](tools/install_smoke.py), the offline suite and current-head CI. The Windows CRLF regression requires the candidate fix. |
| M2 Public alpha | M1 plus one agent passing the [recorded scenarios](skills/git-flowkit/references/compatibility.md), safety regressions and reviewed support limits. |
| M3 Reliable beta | M2 plus a second independent agent, native Release Please comparisons and an authorized rehearsal covering version, changelog, tag, GitHub Release and repeat run. |
| M4 Stable scoped release | M3 plus [project-local upgrade and rollback](skills/git-flowkit/references/upgrading.md), security review, repeated real-project use and closure of critical safety/release issues. |
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

Run each comparison with the dependencies of the workflow it tests. The
repository CI and the installer template pin different action revisions.
These commands require GitHub CLI and npm for setup. The comparisons use the
local files and a read-only GitHub fixture.

```sh
compare_release() (
  set -e
  action_ref=$1
  shift
  deps=$(mktemp -d)
  for file in package.json package-lock.json; do
    gh api -H 'Accept: application/vnd.github.raw+json' \
      "repos/googleapis/release-please-action/contents/$file?ref=$action_ref" > "$deps/$file"
  done
  npm ci --prefix "$deps" --omit=dev --ignore-scripts --no-audit --no-fund
  NODE_PATH="$deps/node_modules" node tools/compare_release.cjs "$@"
)
compare_release 45996ed1f6d02564a971a2fa1b5860e934307cf7
compare_release 5c625bfb5d1ff62eadeeb3772007f7f66fdcf071 --scaffold
```

On Windows, set `NODE_PATH` to the corresponding absolute `node_modules`
directory before each run. On 2026-11-21, the seven repository cases passed
with Release Please 17.6.0. All four scaffold cases passed with 17.3.0.
Each scaffold case applied the shipped CLI in a new tagless repository and
passed the generated files to the native manifest planner. See the
[release setup examples](skills/git-flowkit/references/releases.md#new-repositories-release-please-scaffold)
for the observed candidates.
