# Primary references

Consulted for the initial implementation, 2026-11-20. These are upstream documentation,
not evidence that this project has tested every described integration.

- [Agent Skills specification](https://agentskills.io/specification): directory, metadata, portability boundaries.
- [Skills CLI](https://github.com/vercel-labs/skills): installation and agent discovery.
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/): types, breaking markers, SemVer relationship.
- [Semantic Versioning 2.0.0](https://semver.org/): version grammar and immutable releases.
- [Release Please action](https://github.com/googleapis/release-please-action): manifest mode, permissions, simple strategy.
- [Release Please configuration schema](https://github.com/googleapis/release-please/blob/main/schemas/config.json): bootstrap and pre-1.0 options.
- [GitHub workflow triggering](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow): current GITHUB_TOKEN event exceptions and approval requirements.
- [GITHUB_TOKEN security](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token): least-privilege job permissions.
- [semantic-release](https://github.com/semantic-release/semantic-release): native release-engine integration.
- [Changesets](https://github.com/changesets/changesets): native package/dependency versioning.

When docs disagree about token-triggered workflows, check GitHub's current triggering
documentation rather than relying on an older third-party action README.
