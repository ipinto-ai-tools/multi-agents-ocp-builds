"""Git operations tool for repository management.

This module provides Git operations including cloning, branch management,
status checks, and repository cleanup using GitPython.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Self
import shutil
from git import Repo, GitCommandError, InvalidGitRepositoryError
from git.refs import Head


@dataclass(frozen=True, slots=True)
class GitOpResult:
    """Result of a Git operation."""

    success: bool
    message: str
    data: dict | None = None

    @classmethod
    def ok(cls, message: str, data: dict | None = None) -> Self:
        """Create a successful result."""
        return cls(success=True, message=message, data=data)

    @classmethod
    def error(cls, message: str) -> Self:
        """Create an error result."""
        return cls(success=False, message=message, data=None)


class GitOps:
    """Git operations handler using GitPython."""

    CLONE_BASE_DIR = Path("/tmp/claude")

    def __init__(self) -> None:
        """Initialize GitOps and ensure base directory exists."""
        self.CLONE_BASE_DIR.mkdir(parents=True, exist_ok=True)

    def clone_repository(
        self,
        repo_url: str,
        target_name: str | None = None,
        depth: int = 1,
        branch: str | None = None,
        sparse_checkout: list[str] | None = None,
    ) -> GitOpResult:
        """Clone a repository to /tmp/claude/.

        Args:
            repo_url: Git repository URL (HTTP/HTTPS/SSH)
            target_name: Optional custom directory name (defaults to repo name)
            depth: Clone depth (default: 1 for shallow clone)
            branch: Specific branch to clone (default: None for default branch)
            sparse_checkout: List of paths for sparse checkout (default: None for full)

        Returns:
            GitOpResult with clone path in data["path"] if successful
        """
        try:
            # Determine target directory
            if target_name:
                clone_path = self.CLONE_BASE_DIR / target_name
            else:
                # Extract repo name from URL
                repo_name = repo_url.rstrip("/").split("/")[-1]
                if repo_name.endswith(".git"):
                    repo_name = repo_name[:-4]
                clone_path = self.CLONE_BASE_DIR / repo_name

            # Check if already exists
            if clone_path.exists():
                return GitOpResult.error(
                    f"Directory already exists: {clone_path}. "
                    "Use cleanup_repository() first or choose a different name."
                )

            # Build clone options
            clone_kwargs = {
                "depth": depth if depth > 0 else None,
            }

            if branch:
                clone_kwargs["branch"] = branch

            # Handle sparse checkout
            if sparse_checkout:
                # GitPython doesn't support sparse checkout directly
                # Clone with --filter=blob:none --sparse then configure
                clone_kwargs["filter"] = "blob:none"
                clone_kwargs["no_checkout"] = True

                repo = Repo.clone_from(repo_url, str(clone_path), **clone_kwargs)

                # Configure sparse checkout
                with repo.config_writer() as config:
                    config.set_value("core", "sparseCheckout", "true")

                # Write sparse-checkout patterns
                sparse_file = Path(repo.git_dir) / "info" / "sparse-checkout"
                sparse_file.parent.mkdir(parents=True, exist_ok=True)
                sparse_file.write_text("\n".join(sparse_checkout) + "\n")

                # Checkout the files
                repo.git.checkout()

                return GitOpResult.ok(
                    f"Repository cloned with sparse checkout to {clone_path}",
                    data={
                        "path": str(clone_path),
                        "sparse_paths": sparse_checkout,
                        "depth": depth,
                    },
                )
            else:
                # Standard clone
                repo = Repo.clone_from(repo_url, str(clone_path), **clone_kwargs)

                return GitOpResult.ok(
                    f"Repository cloned to {clone_path}",
                    data={
                        "path": str(clone_path),
                        "depth": depth,
                        "branch": branch or repo.active_branch.name,
                    },
                )

        except GitCommandError as e:
            return GitOpResult.error(f"Git command failed: {e}")
        except Exception as e:
            return GitOpResult.error(f"Clone failed: {e}")

    def create_branch(
        self,
        repo_path: str | Path,
        branch_name: str,
        start_point: str | None = None,
        checkout: bool = True,
    ) -> GitOpResult:
        """Create a new branch in the repository.

        Args:
            repo_path: Path to the Git repository
            branch_name: Name of the new branch
            start_point: Commit/branch to start from (default: current HEAD)
            checkout: Whether to checkout the new branch (default: True)

        Returns:
            GitOpResult with branch info
        """
        try:
            repo = Repo(repo_path)

            # Check if branch already exists
            if branch_name in repo.heads:
                return GitOpResult.error(f"Branch '{branch_name}' already exists")

            # Create branch
            new_branch = repo.create_head(branch_name, start_point or "HEAD")

            if checkout:
                new_branch.checkout()
                message = f"Created and checked out branch '{branch_name}'"
            else:
                message = f"Created branch '{branch_name}'"

            return GitOpResult.ok(
                message,
                data={
                    "branch": branch_name,
                    "commit": str(new_branch.commit),
                    "active_branch": repo.active_branch.name,
                },
            )

        except InvalidGitRepositoryError:
            return GitOpResult.error(f"Not a valid Git repository: {repo_path}")
        except GitCommandError as e:
            return GitOpResult.error(f"Git command failed: {e}")
        except Exception as e:
            return GitOpResult.error(f"Branch creation failed: {e}")

    def get_status(self, repo_path: str | Path) -> GitOpResult:
        """Get repository status.

        Args:
            repo_path: Path to the Git repository

        Returns:
            GitOpResult with status information
        """
        try:
            repo = Repo(repo_path)

            # Check if repo is dirty
            is_dirty = repo.is_dirty(untracked_files=True)

            # Get current branch
            try:
                current_branch = repo.active_branch.name
            except TypeError:
                current_branch = "HEAD (detached)"

            # Get modified files
            modified_files = [item.a_path for item in repo.index.diff(None)]

            # Get staged files
            staged_files = [item.a_path for item in repo.index.diff("HEAD")]

            # Get untracked files
            untracked_files = repo.untracked_files

            return GitOpResult.ok(
                f"Status for {repo_path}",
                data={
                    "is_dirty": is_dirty,
                    "current_branch": current_branch,
                    "modified_files": modified_files,
                    "staged_files": staged_files,
                    "untracked_files": untracked_files,
                },
            )

        except InvalidGitRepositoryError:
            return GitOpResult.error(f"Not a valid Git repository: {repo_path}")
        except Exception as e:
            return GitOpResult.error(f"Status check failed: {e}")

    def get_diff(
        self,
        repo_path: str | Path,
        commit1: str | None = None,
        commit2: str | None = None,
        path: str | None = None,
    ) -> GitOpResult:
        """Get diff information.

        Args:
            repo_path: Path to the Git repository
            commit1: First commit (default: None for working tree)
            commit2: Second commit (default: None for staged/HEAD)
            path: Specific file path to diff (default: None for all)

        Returns:
            GitOpResult with diff text
        """
        try:
            repo = Repo(repo_path)

            if commit1 and commit2:
                # Diff between two commits
                diff_text = repo.git.diff(commit1, commit2, path or "")
                description = f"Diff between {commit1} and {commit2}"
            elif commit1:
                # Diff from commit to working tree
                diff_text = repo.git.diff(commit1, path or "")
                description = f"Diff from {commit1} to working tree"
            else:
                # Diff of unstaged changes
                diff_text = repo.git.diff(path or "")
                description = "Diff of unstaged changes"

            return GitOpResult.ok(
                description,
                data={
                    "diff": diff_text,
                    "commit1": commit1,
                    "commit2": commit2,
                    "path": path,
                },
            )

        except InvalidGitRepositoryError:
            return GitOpResult.error(f"Not a valid Git repository: {repo_path}")
        except GitCommandError as e:
            return GitOpResult.error(f"Git diff failed: {e}")
        except Exception as e:
            return GitOpResult.error(f"Diff failed: {e}")

    def list_commits(
        self,
        repo_path: str | Path,
        max_count: int = 10,
        branch: str | None = None,
    ) -> GitOpResult:
        """List recent commits.

        Args:
            repo_path: Path to the Git repository
            max_count: Maximum number of commits to retrieve (default: 10)
            branch: Specific branch to list commits from (default: current)

        Returns:
            GitOpResult with commit list
        """
        try:
            repo = Repo(repo_path)

            # Get commits
            if branch:
                commits = list(repo.iter_commits(branch, max_count=max_count))
            else:
                commits = list(repo.iter_commits(max_count=max_count))

            commit_list = [
                {
                    "sha": commit.hexsha[:7],
                    "full_sha": commit.hexsha,
                    "author": f"{commit.author.name} <{commit.author.email}>",
                    "date": commit.committed_datetime.isoformat(),
                    "message": commit.message.strip(),
                }
                for commit in commits
            ]

            return GitOpResult.ok(
                f"Retrieved {len(commit_list)} commits",
                data={
                    "commits": commit_list,
                    "branch": branch or repo.active_branch.name,
                },
            )

        except InvalidGitRepositoryError:
            return GitOpResult.error(f"Not a valid Git repository: {repo_path}")
        except GitCommandError as e:
            return GitOpResult.error(f"Git log failed: {e}")
        except Exception as e:
            return GitOpResult.error(f"List commits failed: {e}")

    def cleanup_repository(self, repo_path: str | Path) -> GitOpResult:
        """Remove a cloned repository.

        Args:
            repo_path: Path to the repository to remove

        Returns:
            GitOpResult indicating success or failure
        """
        try:
            path = Path(repo_path)

            # Safety check: only allow cleanup in /tmp/claude
            if not str(path.resolve()).startswith(str(self.CLONE_BASE_DIR.resolve())):
                return GitOpResult.error(
                    f"Safety check failed: Can only cleanup repos in {self.CLONE_BASE_DIR}"
                )

            if not path.exists():
                return GitOpResult.error(f"Path does not exist: {path}")

            # Remove directory
            shutil.rmtree(path)

            return GitOpResult.ok(
                f"Removed repository at {path}",
                data={"removed_path": str(path)},
            )

        except Exception as e:
            return GitOpResult.error(f"Cleanup failed: {e}")

    def list_branches(self, repo_path: str | Path) -> GitOpResult:
        """List all branches in the repository.

        Args:
            repo_path: Path to the Git repository

        Returns:
            GitOpResult with branch list
        """
        try:
            repo = Repo(repo_path)

            current_branch = repo.active_branch.name if not repo.head.is_detached else None

            branches = [
                {
                    "name": head.name,
                    "commit": head.commit.hexsha[:7],
                    "is_current": head.name == current_branch,
                }
                for head in repo.heads
            ]

            return GitOpResult.ok(
                f"Found {len(branches)} branches",
                data={
                    "branches": branches,
                    "current_branch": current_branch,
                },
            )

        except InvalidGitRepositoryError:
            return GitOpResult.error(f"Not a valid Git repository: {repo_path}")
        except Exception as e:
            return GitOpResult.error(f"List branches failed: {e}")


def main() -> None:
    """Example usage of GitOps."""
    ops = GitOps()

    # Example: Clone a repository
    result = ops.clone_repository(
        "https://github.com/octocat/Hello-World.git",
        target_name="hello-world-test",
        depth=1,
    )

    if result.success:
        print(f"✓ {result.message}")
        repo_path = result.data["path"]

        # Get status
        status = ops.get_status(repo_path)
        if status.success:
            print(f"✓ Branch: {status.data['current_branch']}")

        # List commits
        commits = ops.list_commits(repo_path, max_count=5)
        if commits.success:
            print(f"✓ Recent commits: {len(commits.data['commits'])}")

        # Cleanup
        cleanup = ops.cleanup_repository(repo_path)
        if cleanup.success:
            print(f"✓ {cleanup.message}")
    else:
        print(f"✗ {result.message}")


if __name__ == "__main__":
    main()
