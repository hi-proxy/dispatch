import subprocess

from fungis_node.git_context import inspect_git_context, is_verified_commit


def git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


def test_git_context_reports_verified_branch_head_and_dirty_state(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "feature/fungis-tracks")
    git(repo, "config", "user.email", "fungis@example.invalid")
    git(repo, "config", "user.name", "Fungis Test")
    (repo / "tracked.txt").write_text("first\n")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "initial")

    clean = inspect_git_context(str(repo))
    assert clean is not None
    assert clean["repo_root"] == str(repo)
    assert clean["branch"] == "feature/fungis-tracks"
    assert clean["branches"] == ["feature/fungis-tracks"]
    assert len(clean["head"]) == 12
    assert clean["dirty"] is False
    assert clean["verified"] is True
    assert is_verified_commit(str(repo), clean["head"], clean["head"][:7]) is True
    assert is_verified_commit(str(repo), clean["head"], "deadbee") is False

    (repo / "tracked.txt").write_text("changed\n")
    assert inspect_git_context(str(repo))["dirty"] is True


def test_git_context_is_absent_outside_repository(tmp_path):
    assert inspect_git_context(str(tmp_path)) is None
    assert inspect_git_context(None) is None
