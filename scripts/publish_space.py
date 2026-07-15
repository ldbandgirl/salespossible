"""Publish this app to a Hugging Face Space so the Reachy Mini app store can install it.

Usage (from the repo root, any OS):

    pip install -U huggingface_hub
    python scripts/publish_space.py

The script asks for your Hugging Face WRITE token (or reads the HF_TOKEN
environment variable), creates the Space <your-username>/hermes_mini if
needed, and uploads the app. Nothing sensitive is uploaded: .env and
settings.json are excluded.
"""

from __future__ import annotations

import os
import re
import sys
from getpass import getpass
from pathlib import Path

try:
    from huggingface_hub import HfApi
except ImportError:
    sys.exit("huggingface_hub is not installed. Run: pip install -U huggingface_hub")

SPACE_NAME = "hermes_mini"
IGNORE = [
    ".git*",
    "**/__pycache__/**",
    "*.pyc",
    ".env",
    "settings.json",
    ".venv/**",
    "venv/**",
    ".pytest_cache/**",
    "*.egg-info/**",
]


def _normalize_readme_emoji(repo_root: Path) -> None:
    """Hugging Face requires a pictographic emoji in the Space metadata.

    Older copies of this repo shipped the caduceus symbol (U+2624), which the
    validator rejects — rewrite whatever is there to a safe emoji.
    """
    readme = repo_root / "README.md"
    text = readme.read_text(encoding="utf-8")
    fixed = re.sub(r"(?m)^emoji:.*$", "emoji: \U0001F916", text, count=1)
    if fixed != text:
        readme.write_text(fixed, encoding="utf-8")
        print("Normalized Space emoji in README.md metadata -> \U0001F916")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    if not (repo_root / "pyproject.toml").exists():
        sys.exit(f"Could not find pyproject.toml in {repo_root} — run from the repo.")

    _normalize_readme_emoji(repo_root)

    token = os.environ.get("HF_TOKEN") or getpass(
        "Hugging Face WRITE token (from hf.co/settings/tokens, input hidden): "
    ).strip()
    if not token:
        sys.exit("No token provided.")

    api = HfApi(token=token)
    user = api.whoami()["name"]
    repo_id = f"{user}/{SPACE_NAME}"

    print(f"Publishing {repo_root} -> https://huggingface.co/spaces/{repo_id}")
    api.create_repo(
        repo_id=repo_id,
        repo_type="space",
        space_sdk="static",
        private=False,
        exist_ok=True,
    )
    api.upload_folder(
        folder_path=str(repo_root),
        repo_id=repo_id,
        repo_type="space",
        ignore_patterns=IGNORE,
        commit_message="Publish hermes_mini",
    )
    print("\nDone! The app is live at:")
    print(f"  https://huggingface.co/spaces/{repo_id}")
    print(
        "\nOn the robot: open the dashboard app store, search 'hermes_mini' and "
        "install it (indexing can take a minute or two)."
    )
    print(
        "\nSecurity reminder: if you shared this token anywhere (chat, docs), "
        "revoke it at https://huggingface.co/settings/tokens and create a new one."
    )


if __name__ == "__main__":
    main()
