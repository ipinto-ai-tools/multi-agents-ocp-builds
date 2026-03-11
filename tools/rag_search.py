"""RAG (Retrieval-Augmented Generation) search tool for documentation generation.

This module provides utilities for searching and retrieving relevant context:
- Shipwright documentation search
- Similar code implementations in the repository
- API usage patterns
- Code example extraction

These tools enhance documentation generation by providing relevant examples
and context from the codebase and existing documentation.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any

from tools.repo_search import RepoSearch, SearchResult, RepositorySearchError


@dataclass(frozen=True, slots=True)
class CodeExample:
    """Represents a code example extracted from the repository."""

    file_path: str
    start_line: int
    end_line: int
    code: str
    language: str
    context: str  # Surrounding context or description


@dataclass(frozen=True, slots=True)
class APIPattern:
    """Represents an API usage pattern found in the codebase."""

    api_name: str
    file_path: str
    line_number: int
    usage_code: str
    pattern_type: str  # "initialization", "method_call", "field_access", etc.


@dataclass(frozen=True, slots=True)
class DocumentationMatch:
    """Represents a documentation search result."""

    file_path: str
    section_title: str
    content: str
    relevance_score: float


class RAGSearchError(Exception):
    """Base exception for RAG search errors."""


class RAGSearch:
    """RAG search utility for documentation enhancement."""

    def __init__(self, repo_path: str | Path):
        """Initialize RAG search.

        Args:
            repo_path: Path to the repository root

        Raises:
            RAGSearchError: If repository is invalid
        """
        try:
            self.repo_search = RepoSearch(repo_path)
            self.repo_path = self.repo_search.repo_path
        except RepositorySearchError as e:
            raise RAGSearchError(f"Failed to initialize RAG search: {e}") from e

    def search_shipwright_docs(
        self,
        query: str,
        doc_paths: Optional[List[str]] = None,
        max_results: int = 5
    ) -> List[DocumentationMatch]:
        """Search Shipwright documentation for relevant content.

        Args:
            query: Search query (keywords or phrases)
            doc_paths: Optional list of documentation paths to search
            max_results: Maximum number of results to return

        Returns:
            List of DocumentationMatch objects sorted by relevance
        """
        if doc_paths is None:
            doc_paths = ["docs/**/*.md", "README.md", "*.md"]

        matches: List[DocumentationMatch] = []

        # Search across all doc patterns
        for pattern in doc_paths:
            doc_files = self.repo_search.search_files(pattern)

            for doc_file in doc_files:
                file_path = self.repo_path / doc_file.file_path

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract sections and score relevance
                    sections = self._extract_markdown_sections(content)

                    for section_title, section_content in sections.items():
                        relevance = self._calculate_relevance(
                            query, section_title, section_content
                        )

                        if relevance > 0:
                            matches.append(DocumentationMatch(
                                file_path=str(doc_file.file_path),
                                section_title=section_title,
                                content=section_content,
                                relevance_score=relevance
                            ))

                except (IOError, UnicodeDecodeError):
                    continue

        # Sort by relevance and return top matches
        matches.sort(key=lambda m: m.relevance_score, reverse=True)
        return matches[:max_results]

    def search_similar_code(
        self,
        reference_files: List[str],
        file_pattern: str = "**/*.go",
        max_results: int = 10
    ) -> List[SearchResult]:
        """Find similar code implementations in the repository.

        Args:
            reference_files: List of file paths to use as reference
            file_pattern: Glob pattern for files to search
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects for similar implementations
        """
        # Extract key identifiers from reference files
        identifiers = self._extract_identifiers_from_files(reference_files)

        if not identifiers:
            return []

        # Search for similar patterns in the codebase
        similar_results: List[SearchResult] = []

        for identifier in identifiers[:5]:  # Top 5 most relevant identifiers
            results = self.repo_search.search_content(
                pattern=identifier,
                file_pattern=file_pattern,
                case_sensitive=True,
                regex=False
            )
            similar_results.extend(results)

        # Deduplicate by file path
        seen_files = set()
        unique_results = []
        for result in similar_results:
            if result.file_path not in seen_files:
                seen_files.add(result.file_path)
                unique_results.append(result)

        return unique_results[:max_results]

    def search_api_patterns(
        self,
        api_names: List[str],
        file_pattern: str = "**/*.go"
    ) -> List[APIPattern]:
        """Find API usage patterns in the codebase.

        Args:
            api_names: List of API type/function names to search for
            file_pattern: Glob pattern for files to search

        Returns:
            List of APIPattern objects showing how APIs are used
        """
        patterns: List[APIPattern] = []

        for api_name in api_names:
            # Search for different usage patterns
            search_patterns = [
                (f"{api_name}{{", "initialization"),  # Struct initialization
                (f"New{api_name}", "constructor"),  # Constructor pattern
                (f".{api_name}(", "method_call"),  # Method call
                (f"*{api_name}", "pointer_usage"),  # Pointer usage
            ]

            for pattern, pattern_type in search_patterns:
                results = self.repo_search.search_content(
                    pattern=pattern,
                    file_pattern=file_pattern,
                    case_sensitive=True,
                    regex=False
                )

                for result in results[:3]:  # Top 3 per pattern type
                    # Get surrounding context (3 lines before and after)
                    usage_code = self._get_code_context(
                        result.file_path,
                        result.line_number,
                        context_lines=3
                    )

                    patterns.append(APIPattern(
                        api_name=api_name,
                        file_path=result.file_path,
                        line_number=result.line_number,
                        usage_code=usage_code,
                        pattern_type=pattern_type
                    ))

        return patterns

    def extract_code_examples(
        self,
        input_files: List[str],
        example_types: Optional[List[str]] = None
    ) -> List[CodeExample]:
        """Extract relevant code examples from input files.

        Args:
            input_files: List of file paths to extract examples from
            example_types: Optional list of example types to extract
                          ("test", "example", "sample", "demo")

        Returns:
            List of CodeExample objects
        """
        if example_types is None:
            example_types = ["test", "example", "sample"]

        examples: List[CodeExample] = []

        for file_path in input_files:
            full_path = self.repo_path / file_path

            if not full_path.exists():
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                # Detect language
                language = self._detect_language(file_path)

                # Extract examples based on patterns
                if language == "go":
                    examples.extend(self._extract_go_examples(
                        file_path, lines, example_types
                    ))
                elif language == "yaml":
                    examples.extend(self._extract_yaml_examples(
                        file_path, lines, example_types
                    ))
                elif language == "python":
                    examples.extend(self._extract_python_examples(
                        file_path, lines, example_types
                    ))

            except (IOError, UnicodeDecodeError):
                continue

        return examples

    def get_related_documentation(
        self,
        changed_files: List[str]
    ) -> List[str]:
        """Find documentation files related to changed code files.

        Args:
            changed_files: List of code file paths that changed

        Returns:
            List of related documentation file paths
        """
        related_docs = set()

        for file_path in changed_files:
            # Extract component/package name
            parts = Path(file_path).parts

            # Look for docs in similar paths
            for i in range(len(parts)):
                partial_path = "/".join(parts[:i+1])

                # Search for docs mentioning this path or component
                doc_results = self.search_shipwright_docs(
                    query=partial_path,
                    max_results=3
                )

                for doc_match in doc_results:
                    related_docs.add(doc_match.file_path)

        return sorted(list(related_docs))

    # Helper methods

    def _extract_markdown_sections(self, content: str) -> Dict[str, str]:
        """Extract sections from markdown content.

        Args:
            content: Markdown file content

        Returns:
            Dictionary mapping section titles to content
        """
        sections = {}
        current_section = "Introduction"
        current_content = []

        for line in content.split("\n"):
            # Match markdown headers (# Header or ## Header)
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if header_match:
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                # Start new section
                current_section = header_match.group(2).strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _calculate_relevance(
        self,
        query: str,
        title: str,
        content: str
    ) -> float:
        """Calculate relevance score for a documentation section.

        Args:
            query: Search query
            title: Section title
            content: Section content

        Returns:
            Relevance score (0.0 to 1.0)
        """
        query_lower = query.lower()
        title_lower = title.lower()
        content_lower = content.lower()

        score = 0.0

        # Exact match in title (highest weight)
        if query_lower in title_lower:
            score += 0.5

        # Word matches in title
        query_words = query_lower.split()
        title_words = title_lower.split()
        title_matches = sum(1 for word in query_words if word in title_words)
        score += (title_matches / len(query_words)) * 0.3

        # Content matches (lower weight)
        content_matches = content_lower.count(query_lower)
        score += min(content_matches * 0.05, 0.2)

        return min(score, 1.0)

    def _extract_identifiers_from_files(
        self,
        file_paths: List[str]
    ) -> List[str]:
        """Extract key identifiers (types, functions) from files.

        Args:
            file_paths: List of file paths

        Returns:
            List of identifier names
        """
        identifiers = set()

        for file_path in file_paths:
            full_path = self.repo_path / file_path

            if not full_path.exists():
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Extract Go type definitions
                type_matches = re.findall(r"type\s+([A-Z][a-zA-Z0-9_]*)\s+", content)
                identifiers.update(type_matches)

                # Extract Go function names
                func_matches = re.findall(r"func\s+([A-Z][a-zA-Z0-9_]*)\s*\(", content)
                identifiers.update(func_matches)

            except (IOError, UnicodeDecodeError):
                continue

        return sorted(list(identifiers))

    def _get_code_context(
        self,
        file_path: str,
        line_number: int,
        context_lines: int = 3
    ) -> str:
        """Get code with surrounding context lines.

        Args:
            file_path: File path
            line_number: Target line number
            context_lines: Number of context lines before/after

        Returns:
            Code snippet with context
        """
        return self.repo_search.get_file_content(
            file_path=file_path,
            start_line=max(1, line_number - context_lines),
            end_line=line_number + context_lines,
            show_line_numbers=True
        )

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension.

        Args:
            file_path: File path

        Returns:
            Language identifier ("go", "python", "yaml", "unknown")
        """
        ext = Path(file_path).suffix.lower()

        language_map = {
            ".go": "go",
            ".py": "python",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".md": "markdown",
        }

        return language_map.get(ext, "unknown")

    def _extract_go_examples(
        self,
        file_path: str,
        lines: List[str],
        example_types: List[str]
    ) -> List[CodeExample]:
        """Extract Go code examples (tests, examples).

        Args:
            file_path: File path
            lines: File lines
            example_types: Types of examples to extract

        Returns:
            List of CodeExample objects
        """
        examples = []

        for i, line in enumerate(lines, start=1):
            # Look for test functions or example functions
            if "test" in example_types and line.startswith("func Test"):
                example = self._extract_go_function(file_path, lines, i)
                if example:
                    examples.append(example)
            elif "example" in example_types and line.startswith("func Example"):
                example = self._extract_go_function(file_path, lines, i)
                if example:
                    examples.append(example)

        return examples

    def _extract_go_function(
        self,
        file_path: str,
        lines: List[str],
        start_line: int
    ) -> Optional[CodeExample]:
        """Extract a complete Go function.

        Args:
            file_path: File path
            lines: File lines
            start_line: Starting line number (1-indexed)

        Returns:
            CodeExample or None
        """
        # Find function end by tracking braces
        brace_count = 0
        end_line = start_line
        function_started = False

        for i in range(start_line - 1, len(lines)):
            line = lines[i]

            if "{" in line:
                function_started = True
                brace_count += line.count("{")

            if "}" in line:
                brace_count -= line.count("}")

            if function_started and brace_count == 0:
                end_line = i + 1
                break

        if end_line > start_line:
            code = "".join(lines[start_line - 1:end_line])
            # Extract function name for context
            first_line = lines[start_line - 1]
            func_match = re.search(r"func\s+(\w+)", first_line)
            context = func_match.group(1) if func_match else "Go function"

            return CodeExample(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                code=code,
                language="go",
                context=context
            )

        return None

    def _extract_yaml_examples(
        self,
        file_path: str,
        lines: List[str],
        example_types: List[str]
    ) -> List[CodeExample]:
        """Extract YAML examples (complete documents).

        Args:
            file_path: File path
            lines: File lines
            example_types: Types of examples to extract

        Returns:
            List of CodeExample objects
        """
        # For YAML files, treat the entire file as an example if it's in examples/samples dir
        if any(pattern in file_path for pattern in ["example", "sample"]):
            code = "".join(lines)
            return [CodeExample(
                file_path=file_path,
                start_line=1,
                end_line=len(lines),
                code=code,
                language="yaml",
                context=f"YAML example from {Path(file_path).name}"
            )]

        return []

    def _extract_python_examples(
        self,
        file_path: str,
        lines: List[str],
        example_types: List[str]
    ) -> List[CodeExample]:
        """Extract Python code examples (tests, docstring examples).

        Args:
            file_path: File path
            lines: File lines
            example_types: Types of examples to extract

        Returns:
            List of CodeExample objects
        """
        examples = []

        for i, line in enumerate(lines, start=1):
            # Look for test functions
            if "test" in example_types and line.strip().startswith("def test_"):
                example = self._extract_python_function(file_path, lines, i)
                if example:
                    examples.append(example)

        return examples

    def _extract_python_function(
        self,
        file_path: str,
        lines: List[str],
        start_line: int
    ) -> Optional[CodeExample]:
        """Extract a complete Python function.

        Args:
            file_path: File path
            lines: File lines
            start_line: Starting line number (1-indexed)

        Returns:
            CodeExample or None
        """
        # Find function end by tracking indentation
        base_indent = len(lines[start_line - 1]) - len(lines[start_line - 1].lstrip())
        end_line = start_line

        for i in range(start_line, len(lines)):
            line = lines[i]

            # Skip empty lines
            if not line.strip():
                continue

            current_indent = len(line) - len(line.lstrip())

            # Function ends when we return to base indentation or less
            if current_indent <= base_indent and i > start_line:
                break

            end_line = i + 1

        if end_line > start_line:
            code = "".join(lines[start_line - 1:end_line])
            # Extract function name for context
            first_line = lines[start_line - 1]
            func_match = re.search(r"def\s+(\w+)", first_line)
            context = func_match.group(1) if func_match else "Python function"

            return CodeExample(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                code=code,
                language="python",
                context=context
            )

        return None


# Convenience functions

def search_docs(
    repo_path: str | Path,
    query: str,
    max_results: int = 5
) -> List[DocumentationMatch]:
    """Convenience function for documentation search.

    Args:
        repo_path: Path to repository
        query: Search query
        max_results: Maximum results to return

    Returns:
        List of DocumentationMatch objects
    """
    searcher = RAGSearch(repo_path)
    return searcher.search_shipwright_docs(query, max_results=max_results)


def find_api_usage(
    repo_path: str | Path,
    api_names: List[str]
) -> List[APIPattern]:
    """Convenience function for API usage pattern search.

    Args:
        repo_path: Path to repository
        api_names: API names to search for

    Returns:
        List of APIPattern objects
    """
    searcher = RAGSearch(repo_path)
    return searcher.search_api_patterns(api_names)
