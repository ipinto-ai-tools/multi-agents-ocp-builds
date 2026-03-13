#!/usr/bin/env python3
"""CLI tool for testing multi-agent system.

This script provides a comprehensive testing interface for the multi-agent system,
supporting individual agent testing, E2E workflows, and dashboard validation.

Features:
- Test individual agents (design, testing, docs)
- Test complete E2E workflow
- Test dashboard functionality
- Dry-run mode with mock responses (no API calls)
- Debug mode with verbose logging
- Local artifact storage
- Prepared for future MCP server integration (GitHub, Jira)

Usage:
    # Test design agent with dry-run
    python scripts/test_agents.py --agent design --dry-run --debug

    # Test E2E workflow with real API
    python scripts/test_agents.py --e2e

    # Test dashboard functionality
    python scripts/test_agents.py --dashboard

    # Test with custom output directory
    python scripts/test_agents.py --agent testing --output-dir /tmp/test-output
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.mock_responses import get_mock_response
from utils.logging_config import (
    setup_logging,
    get_agent_logger,
    log_agent_start,
    log_agent_complete,
    log_api_call,
    log_error,
    log_artifact_saved,
)


class AgentTester:
    """Test harness for multi-agent system."""

    def __init__(
        self,
        dry_run: bool = False,
        debug: bool = False,
        output_dir: Optional[Path] = None,
    ):
        """Initialize agent tester.

        Args:
            dry_run: Use mock responses instead of real API calls
            debug: Enable debug logging
            output_dir: Directory for storing artifacts (default: /tmp/claude/agent-tests)
        """
        self.dry_run = dry_run
        self.debug = debug
        self.output_dir = output_dir or Path("/tmp/claude/agent-tests")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.output_dir / f"test_{timestamp}.log"
        self.logger = setup_logging(debug=debug, log_file=log_file)

        self.logger.info("Agent Tester initialized")
        self.logger.info(f"Mode: {'DRY-RUN' if dry_run else 'LIVE'}")
        self.logger.info(f"Output directory: {self.output_dir}")

    def test_design_agent(self, title: str, description: str) -> Dict[str, Any]:
        """Test Design Agent.

        Args:
            title: Issue title
            description: Issue description

        Returns:
            Design agent output dictionary
        """
        logger = get_agent_logger("design")
        context = {"issue_title": title, "issue_description": description}

        log_agent_start(logger, "design", context)

        try:
            if self.dry_run:
                logger.info("Using mock response (dry-run mode)")
                output = get_mock_response("design")
                log_api_call(logger, "claude-sonnet-4", 8000, dry_run=True)
            else:
                logger.info("Calling real Design Agent")
                from agents.design_agent import run_design

                output = run_design(title=title, description=description)
                log_api_call(logger, "claude-sonnet-4", 8000, dry_run=False)

            log_agent_complete(logger, "design", output)
            self._save_artifact("design_output.json", output)

            return output

        except Exception as e:
            log_error(logger, "design", e)
            raise

    def test_testing_agent(self, design_output: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test Testing Agent.

        Args:
            design_output: Output from design agent (if None, uses mock data)

        Returns:
            Testing agent output dictionary
        """
        logger = get_agent_logger("testing")

        # Use provided design output or load from previous run
        if design_output is None:
            if self.dry_run:
                design_output = get_mock_response("design")
            else:
                # Try to load from previous artifact
                artifact_path = self.output_dir / "design_output.json"
                if artifact_path.exists():
                    with open(artifact_path) as f:
                        design_output = json.load(f)
                else:
                    raise ValueError(
                        "No design output provided and no previous artifact found. "
                        "Run design agent first or use --e2e mode."
                    )

        context = {
            "design_analysis": design_output.get("design_analysis", ""),
            "impacted_components": design_output.get("impacted_components", []),
            "acceptance_criteria": design_output.get("acceptance_criteria", []),
            "risks": design_output.get("risks", []),
            "implementation_plan": design_output.get("implementation_plan", ""),
            "issue_title": "Test Issue",
            "issue_description": "Test Description",
            "issue_type": "feature",
        }

        log_agent_start(logger, "testing", context)

        try:
            if self.dry_run:
                logger.info("Using mock response (dry-run mode)")
                output = get_mock_response("testing")
                log_api_call(logger, "claude-sonnet-4", 8000, dry_run=True)
            else:
                logger.info("Calling real Testing Agent")
                from agents.testing_agent import run_testing

                output = run_testing(context)
                log_api_call(logger, "claude-sonnet-4", 8000, dry_run=False)

            log_agent_complete(logger, "testing", output)
            self._save_artifact("testing_output.json", output)

            return output

        except Exception as e:
            log_error(logger, "testing", e)
            raise

    def test_docs_agent(
        self,
        design_output: Optional[Dict[str, Any]] = None,
        testing_output: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Test Docs Agent.

        Args:
            design_output: Output from design agent (if None, uses mock/artifact)
            testing_output: Output from testing agent (if None, uses mock/artifact)

        Returns:
            Docs agent output dictionary
        """
        logger = get_agent_logger("docs")

        # Load design output if not provided
        if design_output is None:
            if self.dry_run:
                design_output = get_mock_response("design")
            else:
                artifact_path = self.output_dir / "design_output.json"
                if artifact_path.exists():
                    with open(artifact_path) as f:
                        design_output = json.load(f)
                else:
                    design_output = {}

        # Load testing output if not provided
        if testing_output is None:
            if self.dry_run:
                testing_output = get_mock_response("testing")
            else:
                artifact_path = self.output_dir / "testing_output.json"
                if artifact_path.exists():
                    with open(artifact_path) as f:
                        testing_output = json.load(f)
                else:
                    testing_output = {}

        context = {
            "design_analysis": design_output.get("design_analysis", ""),
            "implementation_plan": design_output.get("implementation_plan", ""),
            "impacted_components": design_output.get("impacted_components", []),
            "risks": design_output.get("risks", []),
            "acceptance_criteria": design_output.get("acceptance_criteria", []),
            "code_changes": {},
            "files_modified": [],
            "test_results": {},
            "test_summary": testing_output.get("test_summary", ""),
            "test_plan": testing_output.get("test_plan", ""),
            "test_specifications": testing_output.get("test_specifications", {}),
            "unit_tests": testing_output.get("unit_tests", {}),
            "integration_tests": testing_output.get("integration_tests", {}),
            "e2e_tests": testing_output.get("e2e_tests", {}),
            "coverage_analysis": testing_output.get("coverage_analysis", ""),
            "issue_title": "Test Issue",
            "issue_description": "Test Description",
            "issue_type": "feature",
        }

        log_agent_start(logger, "docs", context)

        try:
            if self.dry_run:
                logger.info("Using mock response (dry-run mode)")
                output = get_mock_response("docs")
                log_api_call(logger, "claude-sonnet-4", 8000, dry_run=True)
            else:
                logger.info("Calling real Docs Agent")
                from agents.docs_agent import run_docs

                output = run_docs(context)
                log_api_call(logger, "claude-sonnet-4", 8000, dry_run=False)

            log_agent_complete(logger, "docs", output)
            self._save_artifact("docs_output.json", output)

            return output

        except Exception as e:
            log_error(logger, "docs", e)
            raise

    def test_e2e_workflow(self, title: str, description: str) -> Dict[str, Any]:
        """Test complete E2E workflow.

        Args:
            title: Issue title
            description: Issue description

        Returns:
            Dictionary with all agent outputs
        """
        self.logger.info("=" * 80)
        self.logger.info("Starting E2E Workflow Test")
        self.logger.info("=" * 80)

        # Phase 1: Design
        self.logger.info("\nPhase 1: Design Agent")
        design_output = self.test_design_agent(title, description)

        # Phase 2: Testing
        self.logger.info("\nPhase 2: Testing Agent")
        testing_output = self.test_testing_agent(design_output)

        # Phase 3: Docs
        self.logger.info("\nPhase 3: Docs Agent")
        docs_output = self.test_docs_agent(design_output, testing_output)

        # Compile final result
        final_result = {
            "design": design_output,
            "testing": testing_output,
            "docs": docs_output,
            "metadata": {
                "issue_title": title,
                "issue_description": description,
                "dry_run": self.dry_run,
                "timestamp": datetime.now().isoformat(),
            },
        }

        self._save_artifact("e2e_result.json", final_result)

        self.logger.info("=" * 80)
        self.logger.info("E2E Workflow Complete")
        self.logger.info("=" * 80)

        return final_result

    def test_dashboard(self) -> Dict[str, Any]:
        """Test dashboard functionality.

        Returns:
            Dashboard test results
        """
        logger = get_agent_logger("dashboard")
        logger.info("=" * 80)
        logger.info("Testing Dashboard Functionality")
        logger.info("=" * 80)

        results = {"tests": [], "summary": {"passed": 0, "failed": 0, "skipped": 0}}

        # Test 1: Dashboard imports
        logger.info("\n[1/5] Testing dashboard module imports")
        try:
            from dashboard import backend, enrichers, heartbeat

            logger.info("✓ Dashboard modules import successfully")
            results["tests"].append({"name": "imports", "status": "passed"})
            results["summary"]["passed"] += 1
        except Exception as e:
            logger.error(f"✗ Dashboard import failed: {e}")
            results["tests"].append({"name": "imports", "status": "failed", "error": str(e)})
            results["summary"]["failed"] += 1

        # Test 2: Heartbeat emission (dry-run)
        logger.info("\n[2/5] Testing heartbeat emission")
        try:
            from dashboard.heartbeat import emit_heartbeat

            test_state = {
                "session_id": "test-session-123",
                "issue_title": "Test Issue",
                "current_phase": "testing",
            }

            if self.dry_run:
                logger.info("✓ Heartbeat emission (skipped in dry-run)")
                results["tests"].append({"name": "heartbeat", "status": "skipped"})
                results["summary"]["skipped"] += 1
            else:
                emit_heartbeat("test", test_state)
                logger.info("✓ Heartbeat emitted successfully")
                results["tests"].append({"name": "heartbeat", "status": "passed"})
                results["summary"]["passed"] += 1
        except Exception as e:
            logger.error(f"✗ Heartbeat emission failed: {e}")
            results["tests"].append({"name": "heartbeat", "status": "failed", "error": str(e)})
            results["summary"]["failed"] += 1

        # Test 3: Enrichers
        logger.info("\n[3/5] Testing enrichers")
        try:
            from dashboard.enrichers import enrich_heartbeat

            test_heartbeat = {
                "agent": "design",
                "session_id": "test-123",
                "state": {"current_phase": "design_complete"},
            }

            enriched = enrich_heartbeat(test_heartbeat)
            logger.info(f"✓ Enricher processed heartbeat: {len(enriched)} fields")
            results["tests"].append({"name": "enrichers", "status": "passed"})
            results["summary"]["passed"] += 1
        except Exception as e:
            logger.error(f"✗ Enricher test failed: {e}")
            results["tests"].append({"name": "enrichers", "status": "failed", "error": str(e)})
            results["summary"]["failed"] += 1

        # Test 4: Database operations (if dashboard is running)
        logger.info("\n[4/5] Testing database operations")
        if self.dry_run:
            logger.info("⊘ Database test skipped (dry-run mode)")
            results["tests"].append({"name": "database", "status": "skipped"})
            results["summary"]["skipped"] += 1
        else:
            try:
                import requests

                response = requests.get("http://localhost:8080/api/health", timeout=2)
                if response.ok:
                    logger.info("✓ Dashboard backend is running")
                    results["tests"].append({"name": "database", "status": "passed"})
                    results["summary"]["passed"] += 1
                else:
                    logger.warning("✗ Dashboard backend returned error")
                    results["tests"].append({"name": "database", "status": "failed"})
                    results["summary"]["failed"] += 1
            except requests.exceptions.RequestException:
                logger.warning("⊘ Dashboard backend not running (start with run_dashboard.py)")
                results["tests"].append({"name": "database", "status": "skipped"})
                results["summary"]["skipped"] += 1

        # Test 5: Frontend file
        logger.info("\n[5/5] Testing frontend file existence")
        try:
            frontend_path = Path(__file__).parent.parent / "dashboard" / "frontend" / "index.html"
            if frontend_path.exists():
                logger.info(f"✓ Frontend file exists: {frontend_path}")
                results["tests"].append({"name": "frontend", "status": "passed"})
                results["summary"]["passed"] += 1
            else:
                logger.error("✗ Frontend file not found")
                results["tests"].append({"name": "frontend", "status": "failed"})
                results["summary"]["failed"] += 1
        except Exception as e:
            logger.error(f"✗ Frontend test failed: {e}")
            results["tests"].append({"name": "frontend", "status": "failed", "error": str(e)})
            results["summary"]["failed"] += 1

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Dashboard Test Summary")
        logger.info("=" * 80)
        logger.info(f"Passed: {results['summary']['passed']}")
        logger.info(f"Failed: {results['summary']['failed']}")
        logger.info(f"Skipped: {results['summary']['skipped']}")

        self._save_artifact("dashboard_test_results.json", results)

        return results

    def _save_artifact(self, filename: str, data: Any):
        """Save artifact to output directory.

        Args:
            filename: Name of artifact file
            data: Data to save (will be JSON serialized)
        """
        artifact_path = self.output_dir / filename

        try:
            with open(artifact_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            log_artifact_saved(self.logger, artifact_path)
        except Exception as e:
            self.logger.error(f"Failed to save artifact {filename}: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Test multi-agent system with dry-run and debug support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test design agent with dry-run
  %(prog)s --agent design --dry-run --debug

  # Test E2E workflow with real API
  %(prog)s --e2e --title "Add timeout" --description "Users need timeout config"

  # Test dashboard
  %(prog)s --dashboard

  # Test specific agent with custom output
  %(prog)s --agent testing --output-dir /tmp/my-tests --debug
        """,
    )

    # Test mode selection
    test_mode = parser.add_mutually_exclusive_group(required=True)
    test_mode.add_argument(
        "--agent",
        choices=["design", "testing", "docs"],
        help="Test specific agent individually",
    )
    test_mode.add_argument("--e2e", action="store_true", help="Test complete E2E workflow")
    test_mode.add_argument("--dashboard", action="store_true", help="Test dashboard functionality")

    # Issue details (required for agent/e2e modes)
    parser.add_argument("--title", help="Issue title (required for --agent and --e2e)")
    parser.add_argument("--description", help="Issue description (required for --agent and --e2e)")

    # Test options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use mock responses instead of real API calls",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/claude/agent-tests"),
        help="Directory for storing test artifacts (default: /tmp/claude/agent-tests)",
    )

    args = parser.parse_args()

    # Validate title/description for agent and e2e modes
    if (args.agent or args.e2e) and not args.dry_run:
        if not args.title or not args.description:
            parser.error("--title and --description are required for agent/e2e testing (unless --dry-run)")

    # Use defaults for dry-run mode
    if args.dry_run and not args.title:
        args.title = "Test Issue: Add timeout support to BuildRun"
    if args.dry_run and not args.description:
        args.description = "Users need to configure build timeout to prevent hanging builds"

    # Create tester instance
    tester = AgentTester(dry_run=args.dry_run, debug=args.debug, output_dir=args.output_dir)

    try:
        # Execute requested test
        if args.agent:
            if args.agent == "design":
                result = tester.test_design_agent(args.title, args.description)
            elif args.agent == "testing":
                result = tester.test_testing_agent()
            elif args.agent == "docs":
                result = tester.test_docs_agent()

            print(f"\n{'=' * 80}")
            print(f"{args.agent.upper()} Agent Test Complete")
            print(f"{'=' * 80}")
            print(f"Results saved to: {args.output_dir}")

        elif args.e2e:
            result = tester.test_e2e_workflow(args.title, args.description)

            print(f"\n{'=' * 80}")
            print("E2E Workflow Test Complete")
            print(f"{'=' * 80}")
            print(f"Results saved to: {args.output_dir}")

        elif args.dashboard:
            result = tester.test_dashboard()

            summary = result["summary"]
            total = summary["passed"] + summary["failed"] + summary["skipped"]
            print(f"\n{'=' * 80}")
            print("Dashboard Test Complete")
            print(f"{'=' * 80}")
            print(f"Tests: {total} ({summary['passed']} passed, {summary['failed']} failed, {summary['skipped']} skipped)")
            print(f"Results saved to: {args.output_dir}")

            # Exit with error code if any tests failed
            if summary["failed"] > 0:
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
