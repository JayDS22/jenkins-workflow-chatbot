"""
Tests for the Jenkins Context Reader.

These tests verify the JenkinsContext class works correctly both when
Jenkins is available and when it falls back to mock data.

The offline fallback tests are the important ones for CI - they prove
the code doesn't crash when Jenkins isn't reachable, which is going to
be the case for most reviewers who clone and run this without Docker.
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.jenkins_context import JenkinsContext


class TestJenkinsContextOffline:
    """Tests that work without a running Jenkins instance."""

    def setup_method(self):
        """
        Create a JenkinsContext pointing at a non-existent server.
        This forces the offline fallback behavior.
        """
        # Override env vars to point at nothing
        os.environ["JENKINS_URL"] = "http://localhost:59999"
        os.environ["JENKINS_USER"] = "test"
        os.environ["JENKINS_TOKEN"] = "test"
        self.ctx = JenkinsContext()

    def test_offline_detection(self):
        """Should detect that Jenkins is not reachable."""
        assert self.ctx.is_connected is False

    def test_server_info_fallback(self):
        """Should return mock data when Jenkins is offline."""
        info = self.ctx.get_server_info()
        assert "jenkins_version" in info
        assert "installed_plugins" in info
        assert "jobs" in info
        assert info["connected"] is False

    def test_server_info_has_plugins(self):
        """Mock data should include realistic plugin names."""
        info = self.ctx.get_server_info()
        plugins = info["installed_plugins"]
        assert len(plugins) > 0
        # These are common plugins that should be in the mock data
        assert "git" in plugins
        assert "workflow-aggregator" in plugins

    def test_server_info_has_jobs(self):
        """Mock data should include the demo job names."""
        info = self.ctx.get_server_info()
        jobs = info["jobs"]
        assert len(jobs) > 0
        assert "broken-pipeline" in jobs

    def test_get_job_details_offline(self):
        """Should return an error dict, not crash, when offline."""
        result = self.ctx.get_job_details("some-job")
        assert "error" in result

    def test_get_build_log_offline(self):
        """Should return an error dict, not crash, when offline."""
        result = self.ctx.get_build_log("some-job")
        assert "error" in result

    def test_get_failed_builds_offline(self):
        """Should return an empty list, not crash, when offline."""
        result = self.ctx.get_failed_builds_summary()
        assert isinstance(result, list)
        assert len(result) == 0


class TestJenkinsContextLive:
    """
    Tests that require a running Jenkins instance.
    Skipped automatically if Jenkins isn't available.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Try to connect to Jenkins, skip if not available."""
        os.environ.setdefault("JENKINS_URL", "http://localhost:8080")
        os.environ.setdefault("JENKINS_USER", "admin")
        os.environ.setdefault("JENKINS_TOKEN", "")
        self.ctx = JenkinsContext()
        if not self.ctx.is_connected:
            pytest.skip("Jenkins is not running - skipping live tests")

    def test_live_server_info(self):
        """Should return real Jenkins data."""
        info = self.ctx.get_server_info()
        assert info["connected"] is True
        assert info["jenkins_version"] != "2.462.1 (offline/mock)"
        assert isinstance(info["plugin_count"], int)
        assert isinstance(info["job_count"], int)

    def test_live_server_has_version(self):
        """Jenkins version should be a real version string."""
        info = self.ctx.get_server_info()
        version = info["jenkins_version"]
        # Real Jenkins versions look like "2.462.1" or "2.440"
        assert "." in version
