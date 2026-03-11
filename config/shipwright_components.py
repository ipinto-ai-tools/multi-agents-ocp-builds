"""
Shipwright Build Component Configuration

This module defines the component structure, requirements, and validation rules
for the Shipwright Build project on OpenShift.

Shipwright Architecture Overview:
=================================

Shipwright is a framework for building container images on Kubernetes/OpenShift.
It provides a declarative way to define and execute container image builds using
various strategies (e.g., Buildpacks, Buildah, Kaniko, etc.).

Core Components:
----------------
1. Build API: Defines the build specification and configuration
2. BuildRun API: Represents an instance of a build execution
3. BuildStrategy API: Defines reusable build steps for namespace-scoped strategies
4. ClusterBuildStrategy API: Defines reusable build steps for cluster-wide strategies
5. Controllers: Reconcile custom resources and manage build execution
6. Webhook: Validates and mutates build-related resources

Build Strategies:
-----------------
- Buildpacks (CNB): Cloud Native Buildpacks for automatic image building
- Buildah: Build OCI images using Buildah
- Kaniko: Build container images in Kubernetes
- BuildKit: Modern build toolkit from Docker/Moby

Key Features:
-------------
- Declarative build definitions
- Multiple build strategy support
- Integration with OCI registries
- Git source support with authentication
- Build output to various registries
- Parameterized builds
- Build retention policies
"""

from typing import Dict, List, Set

# Component definitions with their purposes and responsibilities
COMPONENTS: Dict[str, str] = {
    # API Components
    "build_api": "Build custom resource definition and API types",
    "buildrun_api": "BuildRun custom resource definition and API types",
    "buildstrategy_api": "BuildStrategy custom resource definition and API types",
    "clusterbuildstrategy_api": "ClusterBuildStrategy custom resource definition and API types",

    # Controller Components
    "build_controller": "Reconciles Build resources and manages build lifecycle",
    "buildrun_controller": "Reconciles BuildRun resources and executes builds",
    "buildstrategy_controller": "Reconciles BuildStrategy resources",
    "clusterbuildstrategy_controller": "Reconciles ClusterBuildStrategy resources",

    # Webhook Components
    "webhook_validation": "Validates build-related custom resources",
    "webhook_mutation": "Mutates build-related custom resources with defaults",
    "webhook_conversion": "Handles API version conversion for CRDs",

    # Core Logic Components
    "source_handler": "Handles Git source cloning and credential management",
    "registry_handler": "Manages container registry authentication and push operations",
    "strategy_resolver": "Resolves and validates build strategies",
    "taskrun_generator": "Generates Tekton TaskRun from Build and BuildStrategy",

    # Security Components
    "rbac_manager": "Manages RBAC for build execution",
    "secret_manager": "Handles secrets for source and registry authentication",
    "pod_security": "Enforces pod security standards for build pods",

    # Monitoring Components
    "metrics_exporter": "Exports Prometheus metrics for builds",
    "event_recorder": "Records Kubernetes events for build lifecycle",

    # CLI Components
    "cli_build": "CLI commands for managing Build resources",
    "cli_buildrun": "CLI commands for managing BuildRun resources",
    "cli_strategy": "CLI commands for managing BuildStrategy resources",
}

# Custom Resource Definition types
CRD_TYPES: List[str] = [
    "Build",
    "BuildRun",
    "BuildStrategy",
    "ClusterBuildStrategy",
]

# Test requirements per component type
TEST_REQUIREMENTS: Dict[str, Set[str]] = {
    # API components require validation and conversion tests
    "build_api": {"unit", "validation", "conversion", "e2e"},
    "buildrun_api": {"unit", "validation", "conversion", "e2e"},
    "buildstrategy_api": {"unit", "validation", "conversion", "e2e"},
    "clusterbuildstrategy_api": {"unit", "validation", "conversion", "e2e"},

    # Controllers require reconciliation and integration tests
    "build_controller": {"unit", "integration", "e2e"},
    "buildrun_controller": {"unit", "integration", "e2e"},
    "buildstrategy_controller": {"unit", "integration", "e2e"},
    "clusterbuildstrategy_controller": {"unit", "integration", "e2e"},

    # Webhooks require validation and mutation tests
    "webhook_validation": {"unit", "integration", "e2e"},
    "webhook_mutation": {"unit", "integration", "e2e"},
    "webhook_conversion": {"unit", "integration", "e2e"},

    # Core logic components require comprehensive testing
    "source_handler": {"unit", "integration", "e2e"},
    "registry_handler": {"unit", "integration", "e2e"},
    "strategy_resolver": {"unit", "integration"},
    "taskrun_generator": {"unit", "integration", "e2e"},

    # Security components require security-focused tests
    "rbac_manager": {"unit", "integration", "security"},
    "secret_manager": {"unit", "integration", "security"},
    "pod_security": {"unit", "integration", "security"},

    # Monitoring components require observability tests
    "metrics_exporter": {"unit", "integration"},
    "event_recorder": {"unit", "integration"},

    # CLI components require functional tests
    "cli_build": {"unit", "functional", "e2e"},
    "cli_buildrun": {"unit", "functional", "e2e"},
    "cli_strategy": {"unit", "functional", "e2e"},
}

# Security checks required for OpenShift compliance
SECURITY_CHECKS: List[str] = [
    "FIPS_140_2",           # FIPS 140-2 cryptographic module validation
    "TLS_1_2_minimum",      # Minimum TLS version for registry communication
    "RBAC_least_privilege", # Role-Based Access Control with least privilege
    "secret_encryption",    # Secrets encrypted at rest
    "pod_security_standards", # Pod Security Standards enforcement
    "image_signing",        # Container image signing verification
    "registry_auth",        # Secure registry authentication
    "source_auth",          # Secure source repository authentication
    "network_policies",     # Network policies for build pod isolation
    "resource_limits",      # Resource limits and quotas enforcement
    "audit_logging",        # Comprehensive audit logging
    "CVE_scanning",         # Container vulnerability scanning
]

# Component file path patterns for automated discovery
COMPONENT_PATH_PATTERNS: Dict[str, List[str]] = {
    # API definitions
    "build_api": [
        "pkg/apis/build/v1alpha1/build_types.go",
        "pkg/apis/build/v1beta1/build_types.go",
    ],
    "buildrun_api": [
        "pkg/apis/build/v1alpha1/buildrun_types.go",
        "pkg/apis/build/v1beta1/buildrun_types.go",
    ],
    "buildstrategy_api": [
        "pkg/apis/build/v1alpha1/buildstrategy_types.go",
        "pkg/apis/build/v1beta1/buildstrategy_types.go",
    ],
    "clusterbuildstrategy_api": [
        "pkg/apis/build/v1alpha1/clusterbuildstrategy_types.go",
        "pkg/apis/build/v1beta1/clusterbuildstrategy_types.go",
    ],

    # Controllers
    "build_controller": [
        "pkg/controller/build/*.go",
        "pkg/reconciler/build/*.go",
    ],
    "buildrun_controller": [
        "pkg/controller/buildrun/*.go",
        "pkg/reconciler/buildrun/*.go",
    ],
    "buildstrategy_controller": [
        "pkg/controller/buildstrategy/*.go",
        "pkg/reconciler/buildstrategy/*.go",
    ],
    "clusterbuildstrategy_controller": [
        "pkg/controller/clusterbuildstrategy/*.go",
        "pkg/reconciler/clusterbuildstrategy/*.go",
    ],

    # Webhooks
    "webhook_validation": [
        "pkg/webhook/validation/*.go",
    ],
    "webhook_mutation": [
        "pkg/webhook/mutation/*.go",
        "pkg/webhook/default/*.go",
    ],
    "webhook_conversion": [
        "pkg/webhook/conversion/*.go",
    ],

    # Core logic
    "source_handler": [
        "pkg/git/*.go",
        "pkg/bundle/*.go",
    ],
    "registry_handler": [
        "pkg/image/*.go",
        "pkg/registry/*.go",
    ],
    "strategy_resolver": [
        "pkg/buildstrategy/resolver/*.go",
    ],
    "taskrun_generator": [
        "pkg/reconciler/buildrun/resources/*.go",
    ],

    # Security
    "rbac_manager": [
        "pkg/rbac/*.go",
    ],
    "secret_manager": [
        "pkg/credentials/*.go",
    ],
    "pod_security": [
        "pkg/security/*.go",
    ],

    # Monitoring
    "metrics_exporter": [
        "pkg/metrics/*.go",
    ],
    "event_recorder": [
        "pkg/events/*.go",
    ],

    # CLI
    "cli_build": [
        "cmd/shipwright/commands/build/*.go",
    ],
    "cli_buildrun": [
        "cmd/shipwright/commands/buildrun/*.go",
    ],
    "cli_strategy": [
        "cmd/shipwright/commands/buildstrategy/*.go",
        "cmd/shipwright/commands/clusterbuildstrategy/*.go",
    ],
}

# Build strategy types and their characteristics
BUILD_STRATEGIES: Dict[str, Dict[str, str]] = {
    "buildpacks-v3": {
        "type": "ClusterBuildStrategy",
        "builder": "Cloud Native Buildpacks",
        "description": "Automatically detect and build applications using CNB",
        "use_case": "Automated builds for common languages and frameworks",
    },
    "buildah": {
        "type": "ClusterBuildStrategy",
        "builder": "Buildah",
        "description": "Build OCI-compliant images using Buildah",
        "use_case": "Dockerfile-based builds with rootless support",
    },
    "kaniko": {
        "type": "ClusterBuildStrategy",
        "builder": "Kaniko",
        "description": "Build container images in Kubernetes without Docker daemon",
        "use_case": "Dockerfile builds in unprivileged environments",
    },
    "buildkit": {
        "type": "ClusterBuildStrategy",
        "builder": "BuildKit",
        "description": "Modern build toolkit with advanced caching",
        "use_case": "High-performance builds with efficient caching",
    },
    "source-to-image": {
        "type": "ClusterBuildStrategy",
        "builder": "Source-to-Image (S2I)",
        "description": "OpenShift's S2I builder",
        "use_case": "Legacy S2I builds for backward compatibility",
    },
}

# Critical paths for build execution flow
BUILD_EXECUTION_FLOW: List[str] = [
    "Build resource created/updated",
    "Build controller validates spec",
    "Build controller creates/updates BuildRun",
    "BuildRun controller resolves BuildStrategy",
    "BuildRun controller clones source (if Git)",
    "BuildRun controller generates Tekton TaskRun",
    "Tekton executes TaskRun with strategy steps",
    "Build output pushed to registry",
    "BuildRun status updated with results",
    "Events and metrics recorded",
]

# OpenShift-specific integration points
OPENSHIFT_INTEGRATIONS: Dict[str, str] = {
    "image_streams": "Integration with OpenShift ImageStreams for build output",
    "internal_registry": "Support for OpenShift internal registry",
    "build_configs": "Migration path from BuildConfig to Shipwright Build",
    "project_quotas": "Respect OpenShift project resource quotas",
    "scc": "Security Context Constraints compliance",
    "oauth": "OAuth integration for registry authentication",
    "routes": "Exposure of webhook endpoints via OpenShift Routes",
}

# Component dependencies (which components depend on others)
COMPONENT_DEPENDENCIES: Dict[str, List[str]] = {
    "build_controller": ["build_api", "webhook_validation"],
    "buildrun_controller": ["buildrun_api", "build_api", "buildstrategy_api",
                            "source_handler", "registry_handler", "taskrun_generator"],
    "buildstrategy_controller": ["buildstrategy_api", "webhook_validation"],
    "clusterbuildstrategy_controller": ["clusterbuildstrategy_api", "webhook_validation"],
    "taskrun_generator": ["strategy_resolver", "source_handler", "registry_handler"],
    "webhook_validation": ["build_api", "buildrun_api", "buildstrategy_api"],
    "webhook_mutation": ["build_api", "buildrun_api"],
}

# Performance benchmarks for build operations
PERFORMANCE_BENCHMARKS: Dict[str, str] = {
    "build_validation": "< 100ms for webhook validation",
    "buildrun_creation": "< 500ms from Build to BuildRun creation",
    "taskrun_generation": "< 1s to generate Tekton TaskRun",
    "source_clone": "Dependent on source size and network",
    "registry_push": "Dependent on image size and network",
    "reconciliation_loop": "< 10s for typical reconciliation",
}


def get_component_info(component_name: str) -> Dict[str, any]:
    """
    Get comprehensive information about a component.

    Args:
        component_name: Name of the component

    Returns:
        Dictionary containing component information including purpose,
        test requirements, dependencies, and file patterns
    """
    return {
        "name": component_name,
        "purpose": COMPONENTS.get(component_name, "Unknown component"),
        "test_requirements": list(TEST_REQUIREMENTS.get(component_name, set())),
        "dependencies": COMPONENT_DEPENDENCIES.get(component_name, []),
        "file_patterns": COMPONENT_PATH_PATTERNS.get(component_name, []),
    }


def validate_component(component_name: str) -> bool:
    """
    Validate that a component name is recognized.

    Args:
        component_name: Name of the component to validate

    Returns:
        True if component is valid, False otherwise
    """
    return component_name in COMPONENTS


def get_required_tests(component_name: str) -> Set[str]:
    """
    Get required test types for a component.

    Args:
        component_name: Name of the component

    Returns:
        Set of required test types (e.g., {'unit', 'integration', 'e2e'})
    """
    return TEST_REQUIREMENTS.get(component_name, set())


def get_security_requirements() -> List[str]:
    """
    Get all security requirements for Shipwright on OpenShift.

    Returns:
        List of security check identifiers
    """
    return SECURITY_CHECKS.copy()
