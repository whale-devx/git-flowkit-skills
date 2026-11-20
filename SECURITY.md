# Security policy

This is an initial implementation, not a guarantee of safe autonomous publishing.
No public stable release is supported yet. Report vulnerabilities against the current
source revision, with the affected command and trust boundary.

Use GitHub private vulnerability reporting when enabled. Otherwise open a minimal issue
requesting a private reporting channel; do not post credentials, private code, or an
exploitable payload in a public issue. Never include real tokens in test fixtures.

Threat boundaries include prompt injection in repository content, path traversal,
symlink escapes, overwritten user configuration, stale merge evidence, release engine
conflicts, tag collisions, untrusted PR execution, and credential overreach.

The offline CLI does not authenticate provider evidence or execute release engines.
Its filesystem checks are not a sandbox against concurrent hostile local filesystem
changes. Review installed skills/scripts before running them. Setup writes are exclusive
per file and can be partially completed after an interruption; no global transaction
or rollback guarantee is implied.

GitHub Actions permissions are read-only by default. A separate release job is explicitly
gated, runs only on the default branch after tests, and requests the permissions required
by Release Please. A maintainer must review repository protections, token behavior and
workflow changes before enabling it. Never use privileged fork-PR triggers for this code.
