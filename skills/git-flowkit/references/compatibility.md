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

## Project installation by host

From the project root, replace TARGET with one of the IDs below.

```sh
npx skills add whale-devx/git-flowkit-skills --skill git-flowkit --agent TARGET
```

| Host | Target ID | Skill path under the project |
| --- | --- | --- |
| Codex | codex | .agents/skills/git-flowkit |
| Cursor | cursor | .agents/skills/git-flowkit |
| Gemini CLI | gemini-cli | .agents/skills/git-flowkit |
| Claude Code | claude-code | .claude/skills/git-flowkit |
| Kiro CLI | kiro-cli | .kiro/skills/git-flowkit |

On 2026-11-21, Skills CLI 1.9.0 on Windows discovered one skill from the public repository. A project-local installation selected all five targets together in copy mode. Running the installed branch helper from each of the three resulting directories with the default configuration produced the same branch suggestion:

```sh
python .agents/skills/git-flowkit/scripts/flowkit.py branch feat "Add team templates" --ticket DEV-42
# feat/DEV-42-add-team-templates
```

Replace .agents with .claude or .kiro for those installations. This exercises packaged helper execution. Agent activation, Kiro IDE discovery and live model sessions require separate verification.

## API-key clients and other agents

An API client can load the installed SKILL.md as instructions and supply the user's Git task and relevant repository policies separately. Keep provider credentials in the client environment. Resolve referenced files relative to the installed skill. To run helpers, the host needs a permitted Python 3.11+ process and access to the target Git checkout. For a text-only session, supply the policies and commit data explicitly and request a draft for review. Keep write, push, merge and release decisions under the user's control.
