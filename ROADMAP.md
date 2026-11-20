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
