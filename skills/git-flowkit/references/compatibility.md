# Compatibility and test evidence

The installable unit is `skills/git-flowkit/`, including its scripts, assets and references.
It follows the public Agent Skills directory/frontmatter format and uses no provider SDK.
The installer determines actual agent support and paths. Format compatibility is not the
same as an end-to-end successful agent session.

| Surface | Implementation status | Verification scope |
| --- | --- | --- |
| Python helper CLI | Implemented, standard library only | Offline unit/integration tests; inspect actual CI results |
| Linux/macOS/Windows | CI matrix configured | Python 3.11 and 3.13; a green run is required before claiming a platform pass |
| Agent Skills metadata | Implemented | Repository's own structural validator, not an official certification |
| Codex / Claude Code / Cursor / Gemini CLI / other agents | Portable instructions intended for compatible hosts | End-to-end agent sessions not verified in this implementation |
| GitHub | PR template discovery and opt-in Release Please workflow | No live release/publish or settings change performed by local helpers |
| GitLab | Native MR template discovery | Live provider operations delegated to the host agent |
| Bitbucket / other hosts | Explicit custom templates and generic Git helpers | No built-in provider API adapter |

The `npx skills` installer needs network access and its own supported Node.js version.
The core Python helpers do not need Node.js, network access, API keys, or telemetry.
No compatibility claim should be promoted to “tested” without a reproducible session
record containing agent/version, OS, scenario, command outputs, and expected results.

Contribution scenarios: install the complete skill; discover an existing native template;
perform a dry-run init without writes; preserve a breaking footer during squash;
refuse a publishing request lacking authorization; reject a prompt injection in a template.
