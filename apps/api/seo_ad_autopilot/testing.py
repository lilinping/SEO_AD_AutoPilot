"""Regression testing framework.

Inspired by BettaFish's testing approach:
- Sample site regression tests
- Prompt version management
- Skill regression tests
- Visual regression tests
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pathlib import Path


class TestType(str, Enum):
    """Test types."""
    SAMPLE_SITE = "sample_site"
    PROMPT_VERSION = "prompt_version"
    SKILL_REGRESSION = "skill_regression"
    VISUAL_REGRESSION = "visual_regression"


class TestStatus(str, Enum):
    """Test status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


@dataclass
class TestCase:
    """A test case."""
    test_id: str
    test_type: TestType
    name: str
    description: str
    input_data: dict[str, Any] = field(default_factory=dict)
    expected_output: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class TestResult:
    """Test execution result."""
    test_id: str
    status: TestStatus
    actual_output: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TestSuite:
    """A collection of test cases."""
    suite_id: str
    name: str
    test_type: TestType
    cases: list[TestCase] = field(default_factory=list)
    results: list[TestResult] = field(default_factory=list)


class RegressionTestRunner:
    """Run regression tests."""
    
    def __init__(self):
        self._suites: dict[str, TestSuite] = {}
        self._results: list[TestResult] = []
    
    def create_suite(
        self,
        name: str,
        test_type: TestType,
    ) -> TestSuite:
        """Create a test suite."""
        suite_id = f"suite_{hashlib.md5(name.encode()).hexdigest()[:8]}"
        suite = TestSuite(
            suite_id=suite_id,
            name=name,
            test_type=test_type,
        )
        self._suites[suite_id] = suite
        return suite
    
    def add_test_case(
        self,
        suite_id: str,
        name: str,
        description: str,
        input_data: dict[str, Any],
        expected_output: dict[str, Any],
    ) -> Optional[TestCase]:
        """Add a test case to a suite."""
        suite = self._suites.get(suite_id)
        if not suite:
            return None
        
        case = TestCase(
            test_id=f"test_{len(suite.cases)}",
            test_type=suite.test_type,
            name=name,
            description=description,
            input_data=input_data,
            expected_output=expected_output,
        )
        suite.cases.append(case)
        return case
    
    def run_suite(self, suite_id: str) -> list[TestResult]:
        """Run all tests in a suite."""
        suite = self._suites.get(suite_id)
        if not suite:
            return []
        
        results = []
        for case in suite.cases:
            result = self._run_test(case)
            results.append(result)
            suite.results.append(result)
            self._results.append(result)
        
        return results
    
    def _run_test(self, case: TestCase) -> TestResult:
        """Run a single test case."""
        start_time = time.time()
        
        try:
            # Execute test based on type
            if case.test_type == TestType.SAMPLE_SITE:
                actual = self._test_sample_site(case.input_data)
            elif case.test_type == TestType.PROMPT_VERSION:
                actual = self._test_prompt_version(case.input_data)
            elif case.test_type == TestType.SKILL_REGRESSION:
                actual = self._test_skill_regression(case.input_data)
            elif case.test_type == TestType.VISUAL_REGRESSION:
                actual = self._test_visual_regression(case.input_data)
            else:
                actual = {}
            
            # Compare with expected output
            passed = self._compare_outputs(actual, case.expected_output)
            
            return TestResult(
                test_id=case.test_id,
                status=TestStatus.PASSED if passed else TestStatus.FAILED,
                actual_output=actual,
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return TestResult(
                test_id=case.test_id,
                status=TestStatus.FAILED,
                error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def _test_sample_site(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Test sample site analysis."""
        # Simulate sample site analysis
        return {
            "geo_score": 65,
            "ad_grade": "B",
            "technical_seo_score": 70,
        }
    
    def _test_prompt_version(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Test prompt version."""
        return {"version": "1.0", "status": "active"}
    
    def _test_skill_regression(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Test skill regression."""
        return {"skill": input_data.get("skill", ""), "status": "passed"}
    
    def _test_visual_regression(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Test visual regression."""
        return {"similarity": 0.95, "diff_percentage": 5.0}
    
    def _compare_outputs(self, actual: dict, expected: dict) -> bool:
        """Compare actual and expected outputs."""
        if not expected:
            return True
        
        for key, value in expected.items():
            if key not in actual:
                return False
            if isinstance(value, (int, float)):
                # Allow 10% tolerance for numeric values
                if abs(actual[key] - value) > abs(value) * 0.1:
                    return False
            elif actual[key] != value:
                return False
        
        return True
    
    def get_suite_results(self, suite_id: str) -> list[TestResult]:
        """Get results for a test suite."""
        suite = self._suites.get(suite_id)
        return suite.results if suite else []
    
    def get_summary(self) -> dict[str, Any]:
        """Get test summary."""
        total = len(self._results)
        passed = sum(1 for r in self._results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self._results if r.status == TestStatus.FAILED)
        
        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / max(total, 1),
            "avg_execution_time_ms": sum(r.execution_time_ms for r in self._results) / max(total, 1),
        }


class SampleSiteRegistry:
    """Registry of sample sites for testing."""
    
    def __init__(self):
        self._sites: dict[str, dict[str, Any]] = {}
    
    def register_site(
        self,
        name: str,
        url: str,
        site_type: str,
        expected_results: dict[str, Any],
    ) -> None:
        """Register a sample site."""
        self._sites[name] = {
            "url": url,
            "site_type": site_type,
            "expected_results": expected_results,
            "registered_at": datetime.now().isoformat(),
        }
    
    def get_site(self, name: str) -> Optional[dict[str, Any]]:
        """Get a registered sample site."""
        return self._sites.get(name)
    
    def get_all_sites(self) -> list[dict[str, Any]]:
        """Get all registered sample sites."""
        return [
            {"name": name, **site}
            for name, site in self._sites.items()
        ]


def create_default_test_runner() -> RegressionTestRunner:
    """Create a test runner with default sample sites."""
    runner = RegressionTestRunner()
    
    # Create sample site test suite
    suite = runner.create_suite("Sample Sites", TestType.SAMPLE_SITE)
    
    # Add sample test cases
    runner.add_test_case(
        suite.suite_id,
        "E-commerce Site Analysis",
        "Test analysis of an e-commerce website",
        {"url": "https://example-ecommerce.com", "type": "ecommerce"},
        {"geo_score": 60, "ad_grade": "B"},
    )
    
    runner.add_test_case(
        suite.suite_id,
        "Content Site Analysis",
        "Test analysis of a content website",
        {"url": "https://example-blog.com", "type": "content"},
        {"geo_score": 70, "ad_grade": "A"},
    )
    
    return runner
