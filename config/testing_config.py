"""Testing configuration for Shipwright Build Ginkgo test generation.

This module provides Shipwright-specific patterns and configurations for
generating Ginkgo v2 tests, including strategy patterns, test types, and
Go import templates.
"""

from typing import Dict, List, Set, Any, Final

# Shipwright build strategy patterns for test generation
SHIPWRIGHT_TEST_PATTERNS: Final[Dict[str, Any]] = {
    "strategies": {
        "kaniko": {
            "keywords": ["kaniko", "registry", "image", "dockerfile"],
            "helpers": ["libfactory.NewKanikoStrategy"],
            "test_template": "kaniko_build_test",
            "common_scenarios": [
                "basic kaniko build with registry push",
                "kaniko build with custom dockerfile path",
                "kaniko build with build args",
                "kaniko build with multi-stage dockerfile",
            ],
        },
        "buildkit": {
            "keywords": ["buildkit", "multi-stage", "cache", "dockerfile"],
            "helpers": ["libfactory.NewBuildkitStrategy"],
            "test_template": "buildkit_build_test",
            "common_scenarios": [
                "buildkit build with cache optimization",
                "buildkit build with multi-stage dockerfile",
                "buildkit build with secrets",
                "buildkit build with ssh agent forwarding",
            ],
        },
        "buildpacks": {
            "keywords": ["buildpacks", "cnb", "cloud-native", "auto-detect"],
            "helpers": ["libfactory.NewBuildpacksStrategy"],
            "test_template": "buildpacks_build_test",
            "common_scenarios": [
                "buildpacks auto-detect language",
                "buildpacks with custom builder image",
                "buildpacks with environment variables",
                "buildpacks with custom buildpack order",
            ],
        },
        "buildah": {
            "keywords": ["buildah", "rootless", "oci", "dockerfile"],
            "helpers": ["libfactory.NewBuildahStrategy"],
            "test_template": "buildah_build_test",
            "common_scenarios": [
                "buildah rootless build",
                "buildah build with custom dockerfile",
                "buildah build with volumes",
                "buildah build with isolation mode",
            ],
        },
        "s2i": {
            "keywords": ["s2i", "source-to-image", "openshift", "legacy"],
            "helpers": ["libfactory.NewS2IStrategy"],
            "test_template": "s2i_build_test",
            "common_scenarios": [
                "s2i build with builder image",
                "s2i build with incremental flag",
                "s2i build with scripts url",
                "s2i build with environment variables",
            ],
        },
    },
    "source_types": {
        "git": {
            "keywords": ["git", "clone", "repository", "branch"],
            "fields": ["url", "revision", "contextDir"],
            "common_scenarios": [
                "git clone from public repository",
                "git clone with specific branch",
                "git clone with tag",
                "git clone with credentials",
                "git clone with submodules",
            ],
        },
        "bundle": {
            "keywords": ["bundle", "oci", "image"],
            "fields": ["image"],
            "common_scenarios": [
                "bundle from oci image",
                "bundle with credentials",
                "bundle with specific platform",
            ],
        },
        "registry": {
            "keywords": ["registry", "image", "container"],
            "fields": ["image"],
            "common_scenarios": [
                "source from registry image",
                "source from private registry",
                "source with pull secret",
            ],
        },
    },
    "output_types": {
        "image": {
            "keywords": ["image", "registry", "push", "tag"],
            "fields": ["image", "credentials"],
            "common_scenarios": [
                "push to docker hub",
                "push to private registry",
                "push to openshift internal registry",
                "push with multiple tags",
                "push with labels",
            ],
        },
        "imagestream": {
            "keywords": ["imagestream", "openshift", "internal"],
            "fields": ["name", "namespace"],
            "common_scenarios": [
                "output to imagestream",
                "output to imagestream with tag",
            ],
        },
    },
    "security_contexts": {
        "privileged": {
            "keywords": ["privileged", "root", "elevated"],
            "test_focus": "security validation",
        },
        "nonroot": {
            "keywords": ["nonroot", "rootless", "unprivileged"],
            "test_focus": "rootless execution",
        },
        "restricted": {
            "keywords": ["restricted", "scc", "security-context"],
            "test_focus": "openshift scc compliance",
        },
    },
}

# Test type specifications
TEST_TYPES: Final[Dict[str, Dict[str, Any]]] = {
    "unit": {
        "framework": "ginkgo-v2",
        "scope": "isolated_with_mocks",
        "duration": "fast",
        "focus_areas": [
            "function logic",
            "error handling",
            "input validation",
            "edge cases",
        ],
        "typical_patterns": [
            "table-driven tests",
            "mocking external dependencies",
            "testing error paths",
            "boundary conditions",
        ],
    },
    "integration": {
        "framework": "ginkgo-v2",
        "scope": "real_kubernetes_cluster",
        "duration": "medium",
        "focus_areas": [
            "controller reconciliation",
            "webhook validation",
            "api interactions",
            "resource creation/deletion",
        ],
        "typical_patterns": [
            "create and verify resources",
            "test controller behavior",
            "validate webhooks",
            "test resource lifecycle",
        ],
    },
    "e2e": {
        "framework": "ginkgo-v2",
        "scope": "full_workflow",
        "duration": "slow",
        "focus_areas": [
            "complete build workflows",
            "end-to-end scenarios",
            "multi-component interactions",
            "real build execution",
        ],
        "typical_patterns": [
            "full build lifecycle",
            "strategy-specific workflows",
            "source to image scenarios",
            "registry integration",
        ],
    },
}

# Ginkgo v2 import templates
GINKGO_IMPORTS: Final[Dict[str, List[str]]] = {
    "dot_imports": [
        "github.com/onsi/ginkgo/v2",
        "github.com/onsi/gomega",
    ],
    "standard": [
        "context",
        "time",
        "fmt",
        "strings",
    ],
    "k8s_core": [
        "k8s.io/api/core/v1",
        "metav1 \"k8s.io/apimachinery/pkg/apis/meta/v1\"",
        "k8s.io/apimachinery/pkg/types",
        "k8s.io/client-go/kubernetes/scheme",
    ],
    "k8s_testing": [
        "sigs.k8s.io/controller-runtime/pkg/client",
        "sigs.k8s.io/controller-runtime/pkg/client/fake",
    ],
    "shipwright_api": [
        "shipwright \"github.com/shipwright-io/build/pkg/apis/build/v1beta1\"",
    ],
    "test_helpers": [
        "\"github.com/shipwright-io/build/test/libfactory\"",
        "\"github.com/shipwright-io/build/test/libk8s\"",
    ],
}

# Common Gomega assertions for Shipwright tests
COMMON_ASSERTIONS: Final[Dict[str, str]] = {
    "resource_created": "Expect(err).ToNot(HaveOccurred())",
    "resource_exists": "Expect(err).ToNot(HaveOccurred())",
    "resource_not_found": "Expect(errors.IsNotFound(err)).To(BeTrue())",
    "build_succeeded": "Expect(buildRun.Status.CompletionTime).ToNot(BeNil())",
    "build_failed": "Expect(buildRun.Status.GetCondition(shipwright.Succeeded).Status).To(Equal(v1.ConditionFalse))",
    "field_equals": "Expect(actual).To(Equal(expected))",
    "field_contains": "Expect(actual).To(ContainSubstring(expected))",
    "eventually_true": "Eventually(func() bool { ... }, timeout, interval).Should(BeTrue())",
    "consistently_true": "Consistently(func() bool { ... }, duration, interval).Should(BeTrue())",
}

# Test data structures for Data-Driven Testing
DDT_PATTERNS: Final[Dict[str, str]] = {
    "strategy_matrix": """
type StrategyTestScenario struct {
    Name            string
    StrategyName    string
    SourceType      string
    OutputType      string
    ExpectedSuccess bool
    ExpectedError   string
}
""",
    "build_parameter_matrix": """
type BuildParameterScenario struct {
    Name       string
    ParamName  string
    ParamValue string
    Expected   string
}
""",
    "validation_matrix": """
type ValidationScenario struct {
    Name          string
    Input         interface{}
    ExpectError   bool
    ErrorContains string
}
""",
    "timeout_matrix": """
type TimeoutScenario struct {
    Name            string
    Timeout         string
    ExpectedTimeout time.Duration
    ExpectError     bool
}
""",
}

# Ginkgo v2 test structure templates
GINKGO_TEMPLATES: Final[Dict[str, str]] = {
    "describe_block": """
var _ = Describe("{description}", func() {
    {content}
})
""",
    "context_block": """
Context("{context}", func() {
    {content}
})
""",
    "it_block": """
It("[{test_id}] {description}", func() {
    {test_body}
})
""",
    "before_each": """
BeforeEach(func() {
    {setup_code}
})
""",
    "after_each": """
AfterEach(func() {
    {cleanup_code}
})
""",
    "describe_table": """
DescribeTable("{description}",
    func(scenario {scenario_type}) {
        {test_logic}
    },
    {entries}
)
""",
    "entry": """Entry("{name}", {scenario_type}{{{fields}}})""",
}

# Test timeouts and intervals
TEST_TIMEOUTS: Final[Dict[str, str]] = {
    "unit_test": "5s",
    "integration_test": "30s",
    "e2e_test": "5m",
    "build_completion": "10m",
    "resource_ready": "30s",
    "poll_interval": "1s",
}

# Test labels and markers
TEST_LABELS: Final[Dict[str, List[str]]] = {
    "focus_labels": [
        "Focus",      # Run only these tests
        "Pending",    # Skip these tests
        "Serial",     # Run serially, not in parallel
    ],
    "custom_labels": [
        "Slow",       # Mark slow tests
        "Flaky",      # Known flaky tests
        "Privileged", # Requires privileged mode
        "E2E",        # End-to-end tests
    ],
}

# Shipwright-specific test helpers
TEST_HELPERS: Final[Dict[str, str]] = {
    "create_build": """
build := libfactory.NewBuild(namespace, buildName).
    WithSource(sourceURL).
    WithStrategy(strategyName).
    WithOutput(outputImage).
    Create()
""",
    "create_buildrun": """
buildRun := libfactory.NewBuildRun(namespace, buildRunName).
    WithBuild(buildName).
    Create()
""",
    "wait_for_buildrun": """
buildRun, err := libk8s.WaitForBuildRunCompletion(ctx, k8sClient, namespace, buildRunName, timeout)
Expect(err).ToNot(HaveOccurred())
""",
    "verify_build_output": """
image, err := libk8s.GetImageFromRegistry(outputImage)
Expect(err).ToNot(HaveOccurred())
Expect(image).ToNot(BeNil())
""",
}


def get_strategy_pattern(strategy_name: str) -> Dict[str, Any]:
    """Get test pattern information for a build strategy.

    Args:
        strategy_name: Name of the build strategy (kaniko, buildkit, etc.)

    Returns:
        Dictionary containing strategy test patterns
    """
    return SHIPWRIGHT_TEST_PATTERNS["strategies"].get(
        strategy_name.lower(),
        {
            "keywords": [],
            "helpers": [],
            "test_template": "generic_build_test",
            "common_scenarios": [],
        },
    )


def get_test_type_config(test_type: str) -> Dict[str, Any]:
    """Get configuration for a test type.

    Args:
        test_type: Type of test (unit, integration, e2e)

    Returns:
        Dictionary containing test type configuration
    """
    return TEST_TYPES.get(test_type.lower(), TEST_TYPES["unit"])


def detect_patterns_in_description(description: str) -> Dict[str, List[str]]:
    """Detect Shipwright patterns in issue description.

    Args:
        description: Issue description text

    Returns:
        Dictionary mapping pattern types to detected patterns
    """
    detected = {
        "strategies": [],
        "source_types": [],
        "output_types": [],
        "security_contexts": [],
    }

    description_lower = description.lower()

    # Detect strategies
    for strategy_name, pattern in SHIPWRIGHT_TEST_PATTERNS["strategies"].items():
        if any(keyword in description_lower for keyword in pattern["keywords"]):
            detected["strategies"].append(strategy_name)

    # Detect source types
    for source_type, pattern in SHIPWRIGHT_TEST_PATTERNS["source_types"].items():
        if any(keyword in description_lower for keyword in pattern["keywords"]):
            detected["source_types"].append(source_type)

    # Detect output types
    for output_type, pattern in SHIPWRIGHT_TEST_PATTERNS["output_types"].items():
        if any(keyword in description_lower for keyword in pattern["keywords"]):
            detected["output_types"].append(output_type)

    # Detect security contexts
    for context_name, pattern in SHIPWRIGHT_TEST_PATTERNS["security_contexts"].items():
        if any(keyword in description_lower for keyword in pattern["keywords"]):
            detected["security_contexts"].append(context_name)

    return detected


def generate_test_id(component: str, test_number: int) -> str:
    """Generate a test ID in Shipwright format.

    Args:
        component: Component name (e.g., BUILD, STRATEGY)
        test_number: Sequential test number

    Returns:
        Formatted test ID (e.g., BUILD-123)
    """
    return f"{component.upper()}-{test_number:03d}"
