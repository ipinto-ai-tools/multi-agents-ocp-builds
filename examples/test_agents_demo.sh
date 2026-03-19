#!/bin/bash
# Demo script for testing multi-agent system
# This script demonstrates various testing scenarios

set -e  # Exit on error

echo "============================================"
echo "Multi-Agent System Testing Demo"
echo "============================================"
echo ""

# Check if user wants dry-run or live mode
echo "Select testing mode:"
echo "1) Dry-run (mock responses, no API calls)"
echo "2) Live (real API calls, requires Vertex AI authentication)"
read -p "Enter choice [1-2]: " mode_choice

if [ "$mode_choice" = "2" ]; then
    if [ -z "$ANTHROPIC_VERTEX_PROJECT_ID" ]; then
        echo ""
        echo "Error: ANTHROPIC_VERTEX_PROJECT_ID not set"
        echo "Please set it with: export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id"
        echo "And ensure gcloud auth is configured: gcloud auth application-default login"
        exit 1
    fi
    DRY_RUN=""
    echo "Running in LIVE mode (will make real API calls)"
else
    DRY_RUN="--dry-run"
    echo "Running in DRY-RUN mode (using mock responses)"
fi

echo ""
echo "What would you like to test?"
echo "1) Individual agent (design, testing, or docs)"
echo "2) Complete E2E workflow"
echo "3) Dashboard functionality"
echo "4) All of the above"
read -p "Enter choice [1-4]: " test_choice

OUTPUT_DIR="/tmp/claude/agent-tests-demo-$(date +%Y%m%d_%H%M%S)"
echo ""
echo "Results will be saved to: $OUTPUT_DIR"
echo ""

case $test_choice in
    1)
        echo "Select agent to test:"
        echo "1) Design Agent"
        echo "2) Testing Agent"
        echo "3) Docs Agent"
        read -p "Enter choice [1-3]: " agent_choice

        case $agent_choice in
            1) AGENT="design" ;;
            2) AGENT="testing" ;;
            3) AGENT="docs" ;;
            *) echo "Invalid choice"; exit 1 ;;
        esac

        echo ""
        echo "Testing $AGENT agent..."
        uv run python scripts/test_agents.py \
            --agent "$AGENT" \
            $DRY_RUN \
            --debug \
            --output-dir "$OUTPUT_DIR"
        ;;

    2)
        echo ""
        echo "Testing E2E workflow..."
        uv run python scripts/test_agents.py \
            --e2e \
            $DRY_RUN \
            --debug \
            --output-dir "$OUTPUT_DIR"
        ;;

    3)
        echo ""
        echo "Testing dashboard..."
        echo ""
        echo "Note: For full dashboard testing, start the dashboard first:"
        echo "  Terminal 1: uv run python scripts/run_dashboard.py"
        echo "  Terminal 2: Run this script"
        echo ""
        read -p "Press Enter to continue with dashboard tests..."

        uv run python scripts/test_agents.py \
            --dashboard \
            --debug \
            --output-dir "$OUTPUT_DIR"
        ;;

    4)
        echo ""
        echo "=== Testing Design Agent ==="
        uv run python scripts/test_agents.py \
            --agent design \
            $DRY_RUN \
            --debug \
            --output-dir "$OUTPUT_DIR"

        echo ""
        echo "=== Testing Testing Agent ==="
        uv run python scripts/test_agents.py \
            --agent testing \
            $DRY_RUN \
            --debug \
            --output-dir "$OUTPUT_DIR"

        echo ""
        echo "=== Testing Docs Agent ==="
        uv run python scripts/test_agents.py \
            --agent docs \
            $DRY_RUN \
            --debug \
            --output-dir "$OUTPUT_DIR"

        echo ""
        echo "=== Testing E2E Workflow ==="
        uv run python scripts/test_agents.py \
            --e2e \
            $DRY_RUN \
            --debug \
            --output-dir "$OUTPUT_DIR"

        echo ""
        echo "=== Testing Dashboard ==="
        uv run python scripts/test_agents.py \
            --dashboard \
            --debug \
            --output-dir "$OUTPUT_DIR"
        ;;

    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "============================================"
echo "Testing Complete!"
echo "============================================"
echo ""
echo "Results saved to: $OUTPUT_DIR"
echo ""
echo "View artifacts:"
echo "  - Logs: cat $OUTPUT_DIR/test_*.log"
echo "  - Design output: cat $OUTPUT_DIR/design_output.json | jq ."
echo "  - Testing output: cat $OUTPUT_DIR/testing_output.json | jq ."
echo "  - Docs output: cat $OUTPUT_DIR/docs_output.json | jq ."
echo "  - E2E result: cat $OUTPUT_DIR/e2e_result.json | jq ."
echo ""
echo "For detailed testing documentation, see:"
echo "  docs/TESTING_INFRASTRUCTURE.md"
echo ""
