"""Unit tests for Git repository onboarding and cloning service."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from umldoc.server.git_service import (
    is_git_url,
    parse_git_url,
    build_authenticated_url,
    mask_token_in_url,
    check_remote_git_repo,
    clone_or_update_repo,
)


def test_is_git_url():
    assert is_git_url("https://github.com/psf/requests") is True
    assert is_git_url("https://github.com/pallets/click.git") is True
    assert is_git_url("http://gitlab.com/group/project") is True
    assert is_git_url("git@github.com:octocat/Hello-World.git") is True
    assert is_git_url("git://github.com/someone/repo") is True
    assert is_git_url("https://bitbucket.org/owner/repo") is True

    # Non-git paths
    assert is_git_url("C:\\Users\\Usmani\\Desktop\\repo") is False
    assert is_git_url("./src/umldoc") is False
    assert is_git_url("careercompass") is False
    assert is_git_url("") is False
    assert is_git_url(None) is False


def test_parse_git_url_standard():
    res = parse_git_url("https://github.com/psf/requests.git")
    assert res["repo_name"] == "requests"
    assert res["clone_url"] == "https://github.com/psf/requests.git"

    res_no_git = parse_git_url("https://github.com/pallets/click")
    assert res_no_git["repo_name"] == "click"
    assert res_no_git["clone_url"] == "https://github.com/pallets/click.git"


def test_parse_git_url_with_tree_branch():
    res = parse_git_url("https://github.com/pallets/click/tree/main")
    assert res["repo_name"] == "click"
    assert res["branch"] == "main"
    assert res["clone_url"] == "https://github.com/pallets/click.git"

    res_tag = parse_git_url("https://github.com/psf/requests/tree/v2.31.0")
    assert res_tag["repo_name"] == "requests"
    assert res_tag["branch"] == "v2.31.0"


def test_parse_git_url_ssh():
    res = parse_git_url("git@github.com:psf/requests.git")
    assert res["repo_name"] == "requests"
    assert res["clone_url"] == "git@github.com:psf/requests.git"


def test_build_authenticated_url():
    url = "https://github.com/org/private-repo.git"
    authed = build_authenticated_url(url, "ghp_secret123")
    assert authed == "https://ghp_secret123@github.com/org/private-repo.git"

    # No token provided
    assert build_authenticated_url(url, None) == url
    assert build_authenticated_url(url, "") == url


def test_mask_token_in_url():
    raw = "Failed to clone https://ghp_super_secret_token_abc@github.com/org/repo.git: authentication failed"
    masked = mask_token_in_url(raw)
    assert "ghp_super_secret_token_abc" not in masked
    assert "https://***@github.com/org/repo.git" in masked


def test_check_remote_git_repo_mock():
    mock_stdout = "a1b2c3d4\trefs/heads/main\ne5f6a7b8\trefs/heads/develop\n"
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = check_remote_git_repo("https://github.com/test/repo")
        assert result["accessible"] is True
        assert result["repo_name"] == "repo"
        assert "main" in result["branches"]
        assert "develop" in result["branches"]
        assert result["default_branch"] == "main"


def test_check_remote_git_repo_failure():
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 128
        mock_proc.stderr = "fatal: repository 'https://ghp_123@github.com/test/notfound.git' not found"
        mock_proc.stdout = ""
        mock_run.return_value = mock_proc

        result = check_remote_git_repo("https://github.com/test/notfound", token="ghp_123")
        assert result["accessible"] is False
        assert "ghp_123" not in result["error"]
        assert "not found" in result["error"]


def test_clone_or_update_repo_existing(tmp_path):
    repo_dir = tmp_path / "my_repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    res = clone_or_update_repo("https://github.com/org/my_repo", target_dir=repo_dir)
    assert res == repo_dir


def test_clone_or_update_repo_mock_success(tmp_path):
    target = tmp_path / "new_repo"

    with patch("subprocess.run") as mock_run:
        def side_effect(cmd, **kwargs):
            target.mkdir(parents=True, exist_ok=True)
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stderr = ""
            mock_proc.stdout = ""
            return mock_proc

        mock_run.side_effect = side_effect

        res = clone_or_update_repo(
            "https://github.com/org/new_repo",
            branch="main",
            target_dir=target,
        )
        assert res == target
        assert mock_run.called
