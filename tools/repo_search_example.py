#!/usr/bin/env python3
"""Example usage of the repo_search tool."""

from pathlib import Path
from repo_search import RepoSearch, search_repository

# Example repository path (adjust as needed)
REPO_PATH = Path(__file__).parent.parent


def main() -> None:
    """Demonstrate repo_search capabilities."""
    print("Repository Search Tool - Examples\n")
    print("=" * 60)

    searcher = RepoSearch(REPO_PATH)

    # Example 1: Search for Go files
    print("\n1. Finding all Go files:")
    go_files = searcher.search_files("**/*.go")
    for result in go_files[:5]:  # Show first 5
        print(f"   {result.file_path}")
    print(f"   ... ({len(go_files)} total)")

    # Example 2: Search for specific content
    print("\n2. Searching for 'func main' in Go files:")
    main_funcs = searcher.search_content("func main", file_pattern="**/*.go")
    for result in main_funcs[:3]:
        print(f"   {result}")

    # Example 3: Find Go functions
    print("\n3. Finding exported Go functions:")
    functions = searcher.find_go_functions()
    for result in functions[:5]:
        print(f"   {result}")

    # Example 4: Find Go structs
    print("\n4. Finding Go struct definitions:")
    structs = searcher.find_go_structs()
    for result in structs[:5]:
        print(f"   {result}")

    # Example 5: Find Kubernetes CRDs
    print("\n5. Finding Kubernetes CRDs:")
    crds = searcher.find_kubernetes_crds()
    for result in crds[:5]:
        print(f"   {result.file_path} ({result.match_type})")

    # Example 6: Analyze Go packages
    print("\n6. Analyzing Go package structure:")
    packages = searcher.analyze_go_packages()
    for pkg in packages[:3]:
        print(f"   Package: {pkg.name} ({pkg.path})")
        print(f"     Files: {len(pkg.files)}, Subpackages: {len(pkg.subpackages)}")

    # Example 7: Get file content with line numbers
    if go_files:
        first_file = go_files[0].file_path
        print(f"\n7. Reading file with line numbers: {first_file}")
        content = searcher.get_file_content(first_file, start_line=1, end_line=10)
        print(content)

    # Example 8: Using convenience function
    print("\n8. Using convenience function for content search:")
    results = search_repository(
        REPO_PATH,
        "import",
        search_type="content",
        file_pattern="**/*.go",
        case_sensitive=True
    )
    print(f"   Found {len(results)} import statements")

    print("\n" + "=" * 60)
    print("Examples complete!")


if __name__ == "__main__":
    main()
