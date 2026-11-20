"""Read untrusted PR metadata as JSON, never interpolate it into a shell command."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/git-flowkit/scripts"))
from flowkit_core import FlowkitError, load_config, load_json
from flowkit_release import parse_commit


if __name__ == "__main__":
    try:
        event = load_json(Path(os.environ["GITHUB_EVENT_PATH"]))
        pr = event.get("pull_request")
        if not isinstance(pr, dict):
            raise FlowkitError("Expected a pull_request event")
        title = pr.get("title", "")
        body = pr.get("body") or ""
        config, _ = load_config(ROOT)
        parse_commit(title + "\n\n" + body, config)
        print("PR title and breaking-change footer syntax validated.")
    except (FlowkitError, KeyError, TypeError) as exc:
        print(f"PR policy failed: {exc}", file=sys.stderr)
        sys.exit(1)
