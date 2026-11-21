# Upgrade or roll back a project-local copy

Use this procedure for a Codex project where Skills CLI installed Git FlowKit
with `--copy` into `.agents/skills/git-flowkit/`. The installer replaces the
contents of that directory. Keep team policy in `.git-flowkit.json` and point
it at project-owned templates such as `.git-flowkit/templates/pr.md`.
Both revisions in the example below read configuration version 1.

## Record the working installation

From the consuming project's root, inspect the source and full commit in its lock entry.

```sh
python -c "import json; print(json.load(open('skills-lock.json', encoding='utf-8'))['skills']['git-flowkit'])"
git status --short --untracked-files=all
```

Confirm the source is `whale-devx/git-flowkit-skills`. Save the working 40-character
commit and back up the installed folder and lockfile outside the agent's discovery
directories. Include any local edits and ignored files in that backup. If the lock
entry has no commit, retain a complete working copy and identify its source before
following the pinned reinstall procedure.

## Install and check the upgrade

Choose a reviewed upstream commit and inspect its configuration and template changes.
Replace `FULL_COMMIT` in the URL with its 40-character SHA. Run from the same
project root using the same agent and copy mode. Skills CLI 1.9.0 supports
fetching a full commit from a GitHub tree URL. [Installer source](https://github.com/vercel-labs/skills/blob/v1.9.0/src/git.ts)

```sh
npx --yes skills@1.9.0 add "https://github.com/whale-devx/git-flowkit-skills/tree/FULL_COMMIT" --skill git-flowkit --agent codex --copy --yes
python -B .agents/skills/git-flowkit/scripts/flowkit.py --repo . config
python -B .agents/skills/git-flowkit/scripts/flowkit.py --repo . branch feat "check upgrade" --ticket DEV-42
```

Read the lock entry again. Its `commit` must equal the requested SHA. Check the
effective policy, the branch suggestion and one familiar template. Review the
project diff before accepting the upgrade. If validation fails or installation
stops partway through, stop using that copy and follow the recovery steps.

## Restore the working copy

Repeat the same `skills add` command using the **original recorded SHA**.
Verify the lock entry, compare the installed folder to the saved copy and repeat
the helper checks. Reconcile intentional local customizations from the backup.
Project templates and policy live outside the installed folder. If you changed
them during a schema migration, restore their compatible versions separately.
Inspect the lockfile diff to preserve entries for other skills added since the
backup. Start a fresh agent session to load the restored instructions.

## Reproduce the historical check

From a full checkout of the **Git FlowKit source repository**, run
`python tools/upgrade_smoke.py` with Python 3.11+, Git, Node.js and npx.
It uses temporary project and home directories and needs access to GitHub and
the npm registry. The sequence installs `724bb8b`, upgrades to `a15e6e0`, then
reinstalls `724bb8b`. Each step checks every installed file against the requested
Git tree, checks the lock entry, and exercises a custom branch rule and template.
An untracked note placed inside the managed skill folder before upgrading is
removed by the installer. A sibling skill and the team files retain their
original bytes. The final Git status must match the original project checkpoint.
