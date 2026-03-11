"""Repository search and analysis tool.

This module provides utilities for analyzing code repositories including:
- File pattern searching (glob)
- Content searching (grep)
- Go-specific searches (functions, types, structs)
- Kubernetes CRD detection
- Package structure analysis
- File content retrieval with line numbers
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    from git import Repo, InvalidGitRepositoryError
except ImportError:
    Repo = None
    InvalidGitRepositoryError = Exception


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Represents a search result."""

    file_path: str
    line_number: Optional[int] = None
    content: Optional[str] = None
    match_type: Optional[str] = None

    def __str__(self) -> str:
        """Format search result for display."""
        if self.line_number and self.content:
            return f"{self.file_path}:{self.line_number}: {self.content.strip()}"
        return self.file_path


@dataclass(frozen=True, slots=True)
class PackageInfo:
    """Represents Go package information."""

    name: str
    path: str
    files: List[str]
    subpackages: List[str]


class RepositorySearchError(Exception):
    """Base exception for repository search errors."""
    pass


class RepoSearch:
    """Repository search and analysis utility."""

    def __init__(self, repo_path: str | Path):
        """Initialize repository search.

        Args:
            repo_path: Path to the repository root

        Raises:
            RepositorySearchError: If repository is invalid
        """
        self.repo_path = Path(repo_path).resolve()

        if not self.repo_path.exists():
            raise RepositorySearchError(f"Repository path does not exist: {self.repo_path}")

        if not self.repo_path.is_dir():
            raise RepositorySearchError(f"Repository path is not a directory: {self.repo_path}")

        # Try to initialize git repo if GitPython is available
        self.git_repo = None
        if Repo is not None:
            try:
                self.git_repo = Repo(self.repo_path)
            except InvalidGitRepositoryError:
                # Not a git repo, that's okay
                pass

    def search_files(self, pattern: str, exclude_dirs: Optional[List[str]] = None) -> List[SearchResult]:
        """Search for files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "*.go", "**/*.yaml")
            exclude_dirs: Directories to exclude (e.g., ["vendor", ".git"])

        Returns:
            List of matching file paths as SearchResult objects
        """
        exclude_dirs = exclude_dirs or [".git", "vendor", "node_modules", "__pycache__"]
        results = []

        # Use rglob for recursive patterns
        if "**" in pattern or "/" not in pattern:
            matches = self.repo_path.rglob(pattern.replace("**/", ""))
        else:
            matches = self.repo_path.glob(pattern)

        for match in matches:
            # Skip excluded directories
            if any(excl in match.parts for excl in exclude_dirs):
                continue

            if match.is_file():
                rel_path = match.relative_to(self.repo_path)
                results.append(SearchResult(file_path=str(rel_path)))

        return sorted(results, key=lambda x: x.file_path)

    def search_content(
        self,
        pattern: str,
        file_pattern: Optional[str] = None,
        case_sensitive: bool = True,
        regex: bool = False
    ) -> List[SearchResult]:
        """Search for content within files using git grep or fallback grep.

        Args:
            pattern: Search pattern (string or regex)
            file_pattern: Optional glob pattern to limit file search
            case_sensitive: Whether search is case-sensitive
            regex: Whether pattern is a regular expression

        Returns:
            List of SearchResult objects with file, line number, and content
        """
        results = []

        # Try git grep first if available
        if self.git_repo is not None:
            try:
                return self._git_grep(pattern, file_pattern, case_sensitive, regex)
            except subprocess.CalledProcessError:
                # Fall through to manual search
                pass

        # Fallback to manual search
        return self._manual_grep(pattern, file_pattern, case_sensitive, regex)

    def _git_grep(
        self,
        pattern: str,
        file_pattern: Optional[str],
        case_sensitive: bool,
        regex: bool
    ) -> List[SearchResult]:
        """Search using git grep command.

        Args:
            pattern: Search pattern
            file_pattern: Optional file pattern
            case_sensitive: Case sensitivity flag
            regex: Regex flag

        Returns:
            List of SearchResult objects
        """
        cmd = ["git", "grep", "-n"]  # -n for line numbers

        if not case_sensitive:
            cmd.append("-i")

        if not regex:
            cmd.append("-F")  # Fixed string search

        cmd.append(pattern)

        if file_pattern:
            cmd.append("--")
            cmd.append(file_pattern)

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            return self._parse_grep_output(result.stdout)
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:  # No matches found
                return []
            raise RepositorySearchError(f"Git grep failed: {e.stderr}") from e

    def _manual_grep(
        self,
        pattern: str,
        file_pattern: Optional[str],
        case_sensitive: bool,
        regex: bool
    ) -> List[SearchResult]:
        """Manual content search without git grep.

        Args:
            pattern: Search pattern
            file_pattern: Optional file pattern
            case_sensitive: Case sensitivity flag
            regex: Regex flag

        Returns:
            List of SearchResult objects
        """
        # Compile pattern
        flags = 0 if case_sensitive else re.IGNORECASE
        if regex:
            compiled_pattern = re.compile(pattern, flags)
        else:
            compiled_pattern = re.compile(re.escape(pattern), flags)

        # Get files to search
        if file_pattern:
            files = self.search_files(file_pattern)
            file_paths = [self.repo_path / f.file_path for f in files]
        else:
            file_paths = [
                f for f in self.repo_path.rglob("*")
                if f.is_file() and not any(
                    excl in f.parts
                    for excl in [".git", "vendor", "node_modules", "__pycache__"]
                )
            ]

        results = []
        for file_path in file_paths:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        if compiled_pattern.search(line):
                            rel_path = file_path.relative_to(self.repo_path)
                            results.append(SearchResult(
                                file_path=str(rel_path),
                                line_number=line_num,
                                content=line.rstrip("\n")
                            ))
            except (UnicodeDecodeError, PermissionError):
                # Skip files that can't be read
                continue

        return results

    def _parse_grep_output(self, output: str) -> List[SearchResult]:
        """Parse git grep output into SearchResult objects.

        Args:
            output: Raw git grep output

        Returns:
            List of SearchResult objects
        """
        results = []
        for line in output.splitlines():
            if not line.strip():
                continue

            # Format: file:line_number:content
            parts = line.split(":", 2)
            if len(parts) >= 3:
                results.append(SearchResult(
                    file_path=parts[0],
                    line_number=int(parts[1]),
                    content=parts[2]
                ))

        return results

    def find_go_functions(self, package_pattern: Optional[str] = None) -> List[SearchResult]:
        """Find Go function definitions.

        Args:
            package_pattern: Optional package path pattern to limit search

        Returns:
            List of SearchResult objects for function definitions
        """
        # Pattern matches: func FunctionName(...) or func (receiver) MethodName(...)
        pattern = r"^func\s+(\([^)]+\)\s+)?[A-Z][a-zA-Z0-9_]*\s*\("
        file_pattern = f"{package_pattern}/**/*.go" if package_pattern else "**/*.go"

        return self.search_content(pattern, file_pattern=file_pattern, regex=True)

    def find_go_types(self, package_pattern: Optional[str] = None) -> List[SearchResult]:
        """Find Go type definitions.

        Args:
            package_pattern: Optional package path pattern to limit search

        Returns:
            List of SearchResult objects for type definitions
        """
        # Pattern matches: type TypeName struct/interface/...
        pattern = r"^type\s+[A-Z][a-zA-Z0-9_]*\s+"
        file_pattern = f"{package_pattern}/**/*.go" if package_pattern else "**/*.go"

        return self.search_content(pattern, file_pattern=file_pattern, regex=True)

    def find_go_structs(self, package_pattern: Optional[str] = None) -> List[SearchResult]:
        """Find Go struct definitions.

        Args:
            package_pattern: Optional package path pattern to limit search

        Returns:
            List of SearchResult objects for struct definitions
        """
        pattern = r"^type\s+[A-Z][a-zA-Z0-9_]*\s+struct\s*\{"
        file_pattern = f"{package_pattern}/**/*.go" if package_pattern else "**/*.go"

        return self.search_content(pattern, file_pattern=file_pattern, regex=True)

    def find_kubernetes_crds(self) -> List[SearchResult]:
        """Find Kubernetes Custom Resource Definitions.

        Returns:
            List of SearchResult objects for CRD YAML files
        """
        results = []

        # Search for YAML files with CRD markers
        yaml_files = self.search_files("**/*.yaml")
        yaml_files.extend(self.search_files("**/*.yml"))

        for yaml_file in yaml_files:
            file_path = self.repo_path / yaml_file.file_path
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Look for CRD indicators
                    if "kind: CustomResourceDefinition" in content or \
                       "apiextensions.k8s.io" in content:
                        results.append(SearchResult(
                            file_path=yaml_file.file_path,
                            match_type="kubernetes_crd"
                        ))
            except (UnicodeDecodeError, PermissionError):
                continue

        return results

    def analyze_go_packages(self, base_path: Optional[str] = None) -> List[PackageInfo]:
        """Analyze Go package structure.

        Args:
            base_path: Base path to start analysis (relative to repo root)

        Returns:
            List of PackageInfo objects
        """
        search_path = self.repo_path / base_path if base_path else self.repo_path

        if not search_path.exists():
            raise RepositorySearchError(f"Path does not exist: {search_path}")

        packages: Dict[str, PackageInfo] = {}

        # Find all .go files
        go_files = list(search_path.rglob("*.go"))

        # Group by directory (package)
        package_dirs: Dict[Path, List[str]] = {}
        for go_file in go_files:
            # Skip vendor and hidden directories
            if any(part.startswith(".") or part == "vendor" for part in go_file.parts):
                continue

            pkg_dir = go_file.parent
            if pkg_dir not in package_dirs:
                package_dirs[pkg_dir] = []
            package_dirs[pkg_dir].append(go_file.name)

        # Extract package names and build structure
        for pkg_dir, files in sorted(package_dirs.items()):
            # Read package name from first .go file
            package_name = None
            for file_name in files:
                if file_name.endswith("_test.go"):
                    continue

                file_path = pkg_dir / file_name
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("package "):
                                package_name = line.split()[1].strip()
                                break
                        if package_name:
                            break
                except (UnicodeDecodeError, PermissionError):
                    continue

            if not package_name:
                continue

            rel_path = pkg_dir.relative_to(self.repo_path)

            # Find subpackages
            subpackages = []
            for other_dir in package_dirs.keys():
                if other_dir != pkg_dir and other_dir.is_relative_to(pkg_dir):
                    # Direct child only
                    try:
                        rel = other_dir.relative_to(pkg_dir)
                        if len(rel.parts) == 1:
                            subpackages.append(str(rel))
                    except ValueError:
                        pass

            packages[str(rel_path)] = PackageInfo(
                name=package_name,
                path=str(rel_path),
                files=sorted(files),
                subpackages=sorted(subpackages)
            )

        return list(packages.values())

    def get_file_content(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        show_line_numbers: bool = True
    ) -> str:
        """Get file content with optional line numbers.

        Args:
            file_path: Path to file (relative to repo root)
            start_line: Optional start line (1-indexed)
            end_line: Optional end line (inclusive)
            show_line_numbers: Whether to show line numbers

        Returns:
            File content as string

        Raises:
            RepositorySearchError: If file cannot be read
        """
        full_path = self.repo_path / file_path

        if not full_path.exists():
            raise RepositorySearchError(f"File does not exist: {file_path}")

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (UnicodeDecodeError, PermissionError) as e:
            raise RepositorySearchError(f"Cannot read file {file_path}: {e}") from e

        # Apply line range
        if start_line is not None:
            start_idx = max(0, start_line - 1)
        else:
            start_idx = 0

        if end_line is not None:
            end_idx = min(len(lines), end_line)
        else:
            end_idx = len(lines)

        selected_lines = lines[start_idx:end_idx]

        # Format with line numbers if requested
        if show_line_numbers:
            width = len(str(end_idx))
            formatted_lines = [
                f"{i + start_idx + 1:>{width}} | {line.rstrip()}"
                for i, line in enumerate(selected_lines)
            ]
            return "\n".join(formatted_lines)
        else:
            return "".join(selected_lines)


# Convenience functions
def search_repository(
    repo_path: str | Path,
    pattern: str,
    search_type: str = "content",
    **kwargs: Any
) -> List[SearchResult]:
    """Convenience function for repository searching.

    Args:
        repo_path: Path to repository
        pattern: Search pattern
        search_type: Type of search ("content", "files", "go_functions", "go_types", "go_structs", "crds")
        **kwargs: Additional arguments passed to specific search method

    Returns:
        List of SearchResult objects

    Raises:
        RepositorySearchError: If search type is invalid
    """
    searcher = RepoSearch(repo_path)

    search_methods = {
        "content": searcher.search_content,
        "files": searcher.search_files,
        "go_functions": searcher.find_go_functions,
        "go_types": searcher.find_go_types,
        "go_structs": searcher.find_go_structs,
        "crds": searcher.find_kubernetes_crds,
    }

    if search_type not in search_methods:
        raise RepositorySearchError(
            f"Invalid search type: {search_type}. "
            f"Valid types: {', '.join(search_methods.keys())}"
        )

    method = search_methods[search_type]

    # Handle methods that don't take pattern argument
    if search_type == "crds":
        return method()
    elif search_type in ("go_functions", "go_types", "go_structs"):
        return method(package_pattern=pattern if pattern else None)
    else:
        return method(pattern, **kwargs)
