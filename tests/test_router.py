"""
Tests for the intent router.

These tests verify that the router correctly classifies queries into
the four intent categories. We test with obvious cases to make sure
the basic wiring works, and some edge cases to make sure the fallback
logic is solid.

Note: These tests call the actual Groq API, so you need a valid
GROQ_API_KEY in your .env file. They're integration tests by nature
since the classification is done by the LLM.
"""

import pytest
import os
import sys

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Skip all tests if no API key is set - we don't want CI to fail
# just because someone didn't configure their key
requires_api_key = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set - skipping LLM-dependent tests"
)


@requires_api_key
class TestIntentRouter:
    """Test intent classification across all four categories."""

    def test_troubleshoot_build_failure(self):
        """Obvious troubleshoot case - build failure."""
        from app.agents.router import classify_intent
        result = classify_intent("Why did my build fail?")
        assert result == "TROUBLESHOOT"

    def test_troubleshoot_error_message(self):
        """Error messages should route to troubleshoot."""
        from app.agents.router import classify_intent
        result = classify_intent("I'm getting a NullPointerException in my pipeline")
        assert result == "TROUBLESHOOT"

    def test_workflow_setup(self):
        """How-to questions should route to workflow."""
        from app.agents.router import classify_intent
        result = classify_intent("How do I set up a multibranch pipeline?")
        assert result == "WORKFLOW"

    def test_workflow_configuration(self):
        """Configuration questions are workflow tasks."""
        from app.agents.router import classify_intent
        result = classify_intent("How do I configure GitHub webhooks for my pipeline?")
        assert result == "WORKFLOW"

    def test_recommend_plugin(self):
        """Plugin recommendations should route to recommend."""
        from app.agents.router import classify_intent
        result = classify_intent("What plugin should I use for Docker-based agents?")
        assert result == "RECOMMEND"

    def test_general_version_info(self):
        """Simple knowledge questions go to general."""
        from app.agents.router import classify_intent
        result = classify_intent("What is a Jenkinsfile?")
        assert result == "GENERAL"

    def test_fallback_on_empty_query(self):
        """Empty-ish queries should not crash, should fall back to general."""
        from app.agents.router import classify_intent
        result = classify_intent("hello")
        assert result in ["GENERAL", "WORKFLOW"]  # either is acceptable

    def test_classify_with_context(self):
        """Router should still work when context is provided."""
        from app.agents.router import classify_intent
        result = classify_intent(
            "Why is this failing?",
            "Jenkins 2.462, 3 jobs, 18 plugins, focused on job: broken-pipeline"
        )
        assert result == "TROUBLESHOOT"
