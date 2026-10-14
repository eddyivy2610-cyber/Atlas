"""Git repository onboarding and cloning service for UMLdoc / ATLAS."""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_REPOS_DIR = REPO_ROOT / "data" / "repos"


def is_git_url(raw: Optional[str]) -> bool:
    """Return True if string represents a remote Git URL."""
    if not raw or not isinstance(raw, str):
        return False
    trimmed = raw.strip()
    if not trimmed:
        return False

    # Standard git protocols
    if (
        trimmed.startswith("http://")
        or trimmed.startswith("https://")
        or trimmed.startswith("git@")
        or trimmed.startswith("ssh://")
        or trimmed.startswith("git://")
    ):
        return True

    # Common git hosts or suffixes
    if trimmed.endswith(".git"):
        return True
    if any(host in trimmed.lower() for host in ("github.com", "gitlab.com", "bitbucket.org")):
        return True

    return False


def parse_git_url(raw_url: str, default_branch: Optional[str] = None) -> Dict[str, Any]:
    """Parse Git URL, extracting clean repository name, branch (if present in URL), and clean clone URL.
    
    Handles direct clone URLs as well as GitHub web URLs like:
      - https://github.com/psf/requests
      - https://github.com/psf/requests.git
      - https://github.com/psf/requests/tree/main
      - https://github.com/psf/requests/tree/v2.31.0
      - git@github.com:psf/requests.git
    """
    trimmed = raw_url.strip()
    extracted_branch = default_branch.strip() if default_branch and default_branch.strip() else None

    # Handle SSH git@github.com:owner/repo.git
    if trimmed.startswith("git@"):
        parts = trimmed.split(":", 1)
        path_part = parts[1] if len(parts) > 1 else ""
        repo_name = path_part.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", repo_name) or "cloned_repo"
        return {
            "raw_url": trimmed,
            "clone_url": trimmed,
            "repo_name": safe_name,
            "branch": extracted_branch,
        }

    # Handle HTTP/HTTPS URLs
    try:
        parsed = urlparse(trimmed)
    except Exception:
        parsed = None

    if not parsed or not parsed.netloc:
        # Fallback simple extraction
        repo_name = trimmed.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", repo_name) or "cloned_repo"
        return {
            "raw_url": trimmed,
            "clone_url": trimmed,
            "repo_name": safe_name,
            "branch": extracted_branch,
        }

    # Check for /tree/<branch> or /blob/<branch> in path
    path_segments = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_segments) >= 4 and path_segments[2] in ("tree", "blob"):
        # e.g. ["psf", "requests", "tree", "main"] or subpaths
        owner = path_segments[0]
        repo = path_segments[1]
        branch_from_url = path_segments[3]
        if not extracted_branch:
            extracted_branch = branch_from_url
        clean_path = f"/{owner}/{repo}.git"
    elif len(path_segments) >= 2:
        owner = path_segments[0]
        repo = path_segments[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        clean_path = f"/{owner}/{repo}.git"
    elif len(path_segments) == 1:
        repo = path_segments[0]
        if repo.endswith(".git"):
            repo = repo[:-4]
        clean_path = f"/{repo}.git"
    else:
        repo = "cloned_repo"
        clean_path = parsed.path

    if repo.endswith(".git"):
        repo = repo[:-4]

    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", repo) or "cloned_repo"
    clean_clone_url = urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))

    return {
        "raw_url": trimmed,
        "clone_url": clean_clone_url,
        "repo_name": safe_name,
        "branch": extracted_branch,
    }


def build_authenticated_url(clone_url: str, token: Optional[str] = None) -> str:
    """Inject personal access token into HTTPS Git URL if provided."""
    if not token or not token.strip():
        return clone_url
    tok = token.strip()
    if clone_url.startswith("https://"):
        return f"https://{tok}@" + clone_url[len("https://"):]
    elif clone_url.startswith("http://"):
        return f"http://{tok}@" + clone_url[len("http://"):]
    return clone_url


def mask_token_in_url(text: str) -> str:
    """Mask credentials and tokens in URL strings or error output."""
    if not text:
        return text
    # Mask https://token@github.com -> https://***@github.com
    pattern = r"(https?://)[^@\s/]+@([^\s]+)"
    return re.sub(pattern, r"\1***@\2", text)


def check_remote_git_repo(
    url: str,
    token: Optional[str] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Check connectivity to remote Git repository via git ls-remote without downloading files."""
    parsed = parse_git_url(url)
    authed_url = build_authenticated_url(parsed["clone_url"], token)

    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--heads", authed_url],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "accessible": False,
            "repo_name": parsed["repo_name"],
            "error": "Git connection timed out (server unreachable).",
        }
    except FileNotFoundError:
        return {
            "accessible": False,
            "repo_name": parsed["repo_name"],
            "error": "Git executable is not installed or not in system PATH.",
        }
    except Exception as exc:
        return {
            "accessible": False,
            "repo_name": parsed["repo_name"],
            "error": mask_token_in_url(str(exc)),
        }

    if proc.returncode != 0:
        err_msg = mask_token_in_url(proc.stderr.strip() or proc.stdout.strip() or "Repository access failed.")
        return {
            "accessible": False,
            "repo_name": parsed["repo_name"],
            "error": err_msg,
        }

    # Parse branches
    branches: List[str] = []
    for line in proc.stdout.splitlines():
        # format: <hash>\trefs/heads/<branch>
        if "\trefs/heads/" in line:
            branch_name = line.split("\trefs/heads/", 1)[1].strip()
            if branch_name and branch_name not in branches:
                branches.append(branch_name)

    # Determine recommended default branch
    default_branch = "main"
    if "main" in branches:
        default_branch = "main"
    elif "master" in branches:
        default_branch = "master"
    elif branches:
        default_branch = branches[0]

    return {
        "accessible": True,
        "repo_name": parsed["repo_name"],
        "branches": branches,
        "default_branch": default_branch,
    }


def clone_or_update_repo(
    repo_url: str,
    branch: Optional[str] = None,
    token: Optional[str] = None,
    target_dir: Optional[Path] = None,
    repos_root: Optional[Path] = None,
    timeout: int = 120,
) -> Path:
    """Clone or update a remote Git repository using fast shallow clone (--depth 1).
    
    Returns the resolved Path of the local directory containing the repository.
    """
    parsed = parse_git_url(repo_url, default_branch=branch)
    repo_name = parsed["repo_name"]
    target_branch = parsed.get("branch") or branch

    if target_dir is None:
        base_dir = repos_root or DEFAULT_REPOS_DIR
        target_dir = (base_dir / repo_name).resolve()
    else:
        target_dir = Path(target_dir).resolve()

    authed_url = build_authenticated_url(parsed["clone_url"], token)

    # If already cloned and contains .git
    git_dir = target_dir / ".git"
    if git_dir.exists() and git_dir.is_dir():
        logger.info(f"Existing Git repository found at {target_dir}. Updating/verifying branch...")
        try:
            if target_branch:
                # Try checkout requested branch
                subprocess.run(
                    ["git", "-C", str(target_dir), "checkout", target_branch],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            return target_dir
        except Exception:
            return target_dir

    # If directory exists but is empty or corrupt, clean it up before cloning
    if target_dir.exists():
        try:
            if not any(target_dir.iterdir()):
                target_dir.rmdir()
            else:
                # Existing folder with files - return it if not git
                return target_dir
        except Exception:
            pass

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # Construct clone command
    clone_cmd = ["git", "clone", "--depth", "1"]
    if target_branch:
        clone_cmd.extend(["--branch", target_branch])
    clone_cmd.extend([authed_url, str(target_dir)])

    logger.info(f"Cloning {mask_token_in_url(parsed['clone_url'])} to {target_dir}...")
    proc = subprocess.run(
        clone_cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    if proc.returncode != 0:
        # If branch was specified and failed (e.g. branch main doesn't exist on older repos), retry with default branch
        if target_branch:
            logger.warning(
                f"Clone with branch '{target_branch}' failed. Retrying with default branch..."
            )
            retry_cmd = ["git", "clone", "--depth", "1", authed_url, str(target_dir)]
            retry_proc = subprocess.run(
                retry_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if retry_proc.returncode == 0 and target_dir.exists():
                return target_dir

        err_clean = mask_token_in_url(proc.stderr.strip() or proc.stdout.strip() or "Clone failed.")
        raise ValueError(f"Git clone failed: {err_clean}")

    if not target_dir.exists() or not target_dir.is_dir():
        raise ValueError(f"Target repository directory was not created: {target_dir}")

    return target_dir
