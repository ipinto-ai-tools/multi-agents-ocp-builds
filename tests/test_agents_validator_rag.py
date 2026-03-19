"""Comprehensive tests for the RAG search tool.

This module tests RAG search capabilities including:
- Documentation search
- Code example extraction
- API pattern discovery
- Similar code finding
"""

from pathlib import Path

import pytest

from tools.rag_search import (
    RAGSearch,
    RAGSearchError,
    CodeExample,
    APIPattern,
    DocumentationMatch,
    search_docs,
    find_api_usage,
)


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary repository with sample files."""
    # Create directory structure
    (tmp_path / "docs").mkdir()
    (tmp_path / "pkg" / "api").mkdir(parents=True)
    (tmp_path / "pkg" / "controller").mkdir(parents=True)
    (tmp_path / "examples").mkdir()
    (tmp_path / "test").mkdir()

    # Create sample documentation
    (tmp_path / "README.md").write_text("""# Sample Project

This is a sample Kubernetes project with BuildRun API.

## Features

- BuildRun timeout support
- Resource management
- Status tracking
""")

    (tmp_path / "docs" / "buildrun.md").write_text("""# BuildRun API

## Overview

The BuildRun API allows you to execute builds.

## Timeout Configuration

You can configure timeout for builds using the `timeout` field:

```yaml
apiVersion: shipwright.io/v1beta1
kind: BuildRun
spec:
  timeout: 30m
```

## Status

The BuildRun status shows execution state.
""")

    # Create sample Go code
    (tmp_path / "pkg" / "api" / "types.go").write_text("""package api

import "time"

// BuildRun represents a build execution
type BuildRun struct {
    Name    string
    Timeout *time.Duration
    Status  BuildRunStatus
}

// BuildRunStatus represents the status
type BuildRunStatus struct {
    Phase string
}

// NewBuildRun creates a new BuildRun
func NewBuildRun(name string) *BuildRun {
    return &BuildRun{
        Name: name,
    }
}
""")

    (tmp_path / "pkg" / "controller" / "buildrun.go").write_text("""package controller

import (
    "github.com/example/pkg/api"
)

// BuildRunController manages BuildRuns
type BuildRunController struct {
    // fields
}

// Reconcile reconciles a BuildRun
func (c *BuildRunController) Reconcile(br *api.BuildRun) error {
    // Implementation
    return nil
}
""")

    # Create sample test
    (tmp_path / "test" / "buildrun_test.go").write_text("""package test

import (
    "testing"
    "github.com/example/pkg/api"
)

func TestBuildRun(t *testing.T) {
    br := api.NewBuildRun("test-build")
    if br.Name != "test-build" {
        t.Error("unexpected name")
    }
}

func ExampleBuildRun() {
    br := api.NewBuildRun("example")
    // Use the buildrun
}
""")

    # Create sample YAML example
    (tmp_path / "examples" / "buildrun.yaml").write_text("""apiVersion: shipwright.io/v1beta1
kind: BuildRun
metadata:
  name: sample-buildrun
spec:
  timeout: 30m
  build:
    name: sample-build
""")

    return tmp_path


class TestRAGSearch:
    """Test suite for RAG search functionality."""

    def test_initialization(self, temp_repo: Path):
        """Test RAG search initialization."""
        rag = RAGSearch(temp_repo)
        assert rag.repo_path == temp_repo

    def test_initialization_invalid_path(self):
        """Test initialization with invalid path."""
        with pytest.raises(RAGSearchError):
            RAGSearch("/nonexistent/path")

    def test_search_shipwright_docs(self, temp_repo: Path):
        """Test documentation search."""
        rag = RAGSearch(temp_repo)

        results = rag.search_shipwright_docs(
            query="BuildRun timeout",
            max_results=5
        )

        assert len(results) > 0
        assert isinstance(results[0], DocumentationMatch)

        # Should find the timeout section
        found_timeout = any(
            "timeout" in match.section_title.lower() or
            "timeout" in match.content.lower()
            for match in results
        )
        assert found_timeout

    def test_search_shipwright_docs_no_results(self, temp_repo: Path):
        """Test documentation search with no matches."""
        rag = RAGSearch(temp_repo)

        results = rag.search_shipwright_docs(
            query="nonexistent feature xyz123",
            max_results=5
        )

        assert len(results) == 0

    def test_search_similar_code(self, temp_repo: Path):
        """Test similar code search."""
        rag = RAGSearch(temp_repo)

        results = rag.search_similar_code(
            reference_files=["pkg/api/types.go"],
            file_pattern="**/*.go",
            max_results=10
        )

        assert len(results) > 0
        # Should find references to BuildRun
        assert any("buildrun" in res.file_path.lower() for res in results)

    def test_search_api_patterns(self, temp_repo: Path):
        """Test API usage pattern search."""
        rag = RAGSearch(temp_repo)

        patterns = rag.search_api_patterns(
            api_names=["BuildRun"],
            file_pattern="**/*.go"
        )

        assert len(patterns) > 0
        assert isinstance(patterns[0], APIPattern)

        # Should find NewBuildRun constructor
        found_constructor = any(
            p.pattern_type == "constructor" and "NewBuildRun" in p.usage_code
            for p in patterns
        )
        assert found_constructor

    def test_extract_code_examples_go(self, temp_repo: Path):
        """Test Go code example extraction."""
        rag = RAGSearch(temp_repo)

        examples = rag.extract_code_examples(
            input_files=["test/buildrun_test.go"],
            example_types=["test", "example"]
        )

        assert len(examples) > 0
        assert isinstance(examples[0], CodeExample)

        # Should find test functions
        test_examples = [ex for ex in examples if "test" in ex.context.lower()]
        assert len(test_examples) > 0

        # Check example has proper structure
        example = examples[0]
        assert example.language == "go"
        assert len(example.code) > 0
        assert example.start_line > 0

    def test_extract_code_examples_yaml(self, temp_repo: Path):
        """Test YAML example extraction."""
        rag = RAGSearch(temp_repo)

        examples = rag.extract_code_examples(
            input_files=["examples/buildrun.yaml"],
            example_types=["example"]
        )

        assert len(examples) > 0
        example = examples[0]
        assert example.language == "yaml"
        assert "BuildRun" in example.code

    def test_get_related_documentation(self, temp_repo: Path):
        """Test finding related documentation."""
        rag = RAGSearch(temp_repo)

        related = rag.get_related_documentation(
            changed_files=["pkg/api/types.go", "pkg/controller/buildrun.go"]
        )

        # Related docs may be empty if search doesn't find matches
        # This is acceptable - the function should not error
        assert isinstance(related, list)

    def test_extract_markdown_sections(self, temp_repo: Path):
        """Test markdown section extraction."""
        rag = RAGSearch(temp_repo)

        content = (temp_repo / "docs" / "buildrun.md").read_text()
        sections = rag._extract_markdown_sections(content)

        assert len(sections) > 0
        assert "Overview" in sections
        assert "Timeout Configuration" in sections
        assert "Status" in sections

    def test_calculate_relevance(self, temp_repo: Path):
        """Test relevance score calculation."""
        rag = RAGSearch(temp_repo)

        # Exact match in title should score high
        score1 = rag._calculate_relevance(
            query="timeout",
            title="Timeout Configuration",
            content="Some content about other things"
        )
        assert score1 > 0.5

        # Word matches should score medium
        score2 = rag._calculate_relevance(
            query="build timeout",
            title="Build Configuration",
            content="Content with timeout mentioned"
        )
        assert 0 < score2 < score1

        # No matches should score zero
        score3 = rag._calculate_relevance(
            query="xyz123",
            title="Something Else",
            content="No relevant content"
        )
        assert score3 == 0

    def test_extract_identifiers_from_files(self, temp_repo: Path):
        """Test identifier extraction from Go files."""
        rag = RAGSearch(temp_repo)

        identifiers = rag._extract_identifiers_from_files(
            ["pkg/api/types.go"]
        )

        assert len(identifiers) > 0
        assert "BuildRun" in identifiers
        assert "BuildRunStatus" in identifiers
        assert "NewBuildRun" in identifiers

    def test_detect_language(self, temp_repo: Path):
        """Test language detection."""
        rag = RAGSearch(temp_repo)

        assert rag._detect_language("file.go") == "go"
        assert rag._detect_language("file.py") == "python"
        assert rag._detect_language("file.yaml") == "yaml"
        assert rag._detect_language("file.yml") == "yaml"
        assert rag._detect_language("file.md") == "markdown"
        assert rag._detect_language("file.txt") == "unknown"


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_search_docs(self, temp_repo: Path):
        """Test search_docs convenience function."""
        results = search_docs(
            repo_path=temp_repo,
            query="BuildRun",
            max_results=3
        )

        assert len(results) > 0
        assert isinstance(results[0], DocumentationMatch)

    def test_find_api_usage(self, temp_repo: Path):
        """Test find_api_usage convenience function."""
        patterns = find_api_usage(
            repo_path=temp_repo,
            api_names=["BuildRun"]
        )

        assert len(patterns) > 0
        assert isinstance(patterns[0], APIPattern)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_search_empty_repo(self, tmp_path: Path):
        """Test search in empty repository."""
        rag = RAGSearch(tmp_path)

        results = rag.search_shipwright_docs(
            query="anything",
            max_results=5
        )

        assert len(results) == 0

    def test_search_with_invalid_files(self, temp_repo: Path):
        """Test search with nonexistent files."""
        rag = RAGSearch(temp_repo)

        # Should not raise error, just return empty results
        examples = rag.extract_code_examples(
            input_files=["nonexistent/file.go"],
            example_types=["test"]
        )

        assert len(examples) == 0

    def test_extract_code_examples_unsupported_language(self, temp_repo: Path):
        """Test code extraction for unsupported language."""
        # Create a text file
        (temp_repo / "test.txt").write_text("some text content")

        rag = RAGSearch(temp_repo)

        examples = rag.extract_code_examples(
            input_files=["test.txt"],
            example_types=["test"]
        )

        # Should return empty for unsupported languages
        assert len(examples) == 0

    def test_search_with_special_characters(self, temp_repo: Path):
        """Test search with special characters in query."""
        rag = RAGSearch(temp_repo)

        # Should not crash with regex special chars
        results = rag.search_shipwright_docs(
            query="Build*Run[timeout]",
            max_results=5
        )

        # Results may be empty but shouldn't error
        assert isinstance(results, list)


class TestPythonExampleExtraction:
    """Test Python code example extraction."""

    def test_extract_python_test(self, tmp_path: Path):
        """Test Python test function extraction."""
        # Create Python test file
        test_file = tmp_path / "test_sample.py"
        test_file.write_text("""
import pytest

def test_something():
    result = 1 + 1
    assert result == 2

def test_another_thing():
    x = "hello"
    assert len(x) == 5
""")

        rag = RAGSearch(tmp_path)
        examples = rag.extract_code_examples(
            input_files=["test_sample.py"],
            example_types=["test"]
        )

        assert len(examples) == 2
        assert all(ex.language == "python" for ex in examples)
        assert any("test_something" in ex.context for ex in examples)
        assert any("test_another_thing" in ex.context for ex in examples)


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_rag_workflow(self, temp_repo: Path):
        """Test complete RAG workflow."""
        rag = RAGSearch(temp_repo)

        # 1. Search documentation
        docs = rag.search_shipwright_docs(
            query="BuildRun timeout",
            max_results=3
        )
        assert len(docs) > 0

        # 2. Find API patterns
        patterns = rag.search_api_patterns(
            api_names=["BuildRun"],
            file_pattern="**/*.go"
        )
        assert len(patterns) > 0

        # 3. Extract code examples
        examples = rag.extract_code_examples(
            input_files=["test/buildrun_test.go"],
            example_types=["test", "example"]
        )
        assert len(examples) > 0

        # 4. Find related docs
        related = rag.get_related_documentation(
            changed_files=["pkg/api/types.go"]
        )
        # May or may not find related docs
        assert isinstance(related, list)

        # All operations should complete successfully


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
