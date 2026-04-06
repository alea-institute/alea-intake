"""Tests for distribution artifacts: LICENSE, Docker, Helm, install script."""

import os
import re
import stat

import pytest
import yaml

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)


class TestLicense:
    """Test 1: LICENSE file."""

    def test_license_exists(self):
        assert os.path.isfile(os.path.join(PROJECT_ROOT, "LICENSE"))

    def test_license_contains_mit(self):
        with open(os.path.join(PROJECT_ROOT, "LICENSE")) as f:
            text = f.read()
        assert "MIT License" in text

    def test_license_contains_alea(self):
        with open(os.path.join(PROJECT_ROOT, "LICENSE")) as f:
            text = f.read()
        assert "ALEA" in text

    def test_license_contains_current_year(self):
        with open(os.path.join(PROJECT_ROOT, "LICENSE")) as f:
            text = f.read()
        assert "2026" in text


class TestDockerComposeSingleTenant:
    """Test 2: docker-compose.yml single-tenant quick start."""

    def test_file_exists(self):
        assert os.path.isfile(os.path.join(PROJECT_ROOT, "docker-compose.yml"))

    def test_sets_single_tenant_mode(self):
        with open(os.path.join(PROJECT_ROOT, "docker-compose.yml")) as f:
            text = f.read()
        assert "ALEA_DEPLOYMENT_MODE" in text
        # Verify it's set to single_tenant
        assert "single_tenant" in text

    def test_sets_sqlite_backend(self):
        with open(os.path.join(PROJECT_ROOT, "docker-compose.yml")) as f:
            text = f.read()
        assert "ALEA_DATABASE_BACKEND" in text
        assert "sqlite" in text


class TestDockerComposeMultiTenant:
    """Test 3: docker-compose.multi.yml multi-tenant setup."""

    def test_file_exists(self):
        assert os.path.isfile(
            os.path.join(PROJECT_ROOT, "docker-compose.multi.yml")
        )

    def test_sets_multi_tenant_mode(self):
        with open(os.path.join(PROJECT_ROOT, "docker-compose.multi.yml")) as f:
            text = f.read()
        assert "multi_tenant" in text

    def test_includes_postgres_service(self):
        with open(os.path.join(PROJECT_ROOT, "docker-compose.multi.yml")) as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        assert "db" in services
        assert "pgvector" in services["db"].get("image", "")


class TestDockerfile:
    """Test 4: Dockerfile syntax and structure."""

    def test_dockerfile_exists(self):
        assert os.path.isfile(os.path.join(PROJECT_ROOT, "Dockerfile"))

    def test_has_oci_labels(self):
        with open(os.path.join(PROJECT_ROOT, "Dockerfile")) as f:
            text = f.read()
        assert "org.opencontainers.image.title" in text
        assert "1.0.0" in text

    def test_has_healthcheck(self):
        with open(os.path.join(PROJECT_ROOT, "Dockerfile")) as f:
            text = f.read()
        assert "HEALTHCHECK" in text

    def test_has_entrypoint_script(self):
        assert os.path.isfile(
            os.path.join(PROJECT_ROOT, "entrypoint.sh")
        )


class TestHelmChart:
    """Test 5: Helm Chart.yaml."""

    def test_chart_yaml_exists(self):
        path = os.path.join(PROJECT_ROOT, "helm", "alea-intake", "Chart.yaml")
        assert os.path.isfile(path)

    def test_chart_api_version(self):
        path = os.path.join(PROJECT_ROOT, "helm", "alea-intake", "Chart.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["apiVersion"] == "v2"

    def test_chart_name(self):
        path = os.path.join(PROJECT_ROOT, "helm", "alea-intake", "Chart.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["name"] == "alea-intake"

    def test_chart_version(self):
        path = os.path.join(PROJECT_ROOT, "helm", "alea-intake", "Chart.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["version"] == "1.0.0"


class TestHelmValues:
    """Test 6: Helm values.yaml."""

    def test_values_yaml_exists(self):
        path = os.path.join(PROJECT_ROOT, "helm", "alea-intake", "values.yaml")
        assert os.path.isfile(path)

    def test_has_deployment_mode(self):
        path = os.path.join(PROJECT_ROOT, "helm", "alea-intake", "values.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "deploymentMode" in data

    def test_has_persistence_section(self):
        path = os.path.join(PROJECT_ROOT, "helm", "alea-intake", "values.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "persistence" in data

    def test_has_observability_section(self):
        path = os.path.join(PROJECT_ROOT, "helm", "alea-intake", "values.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "observability" in data

    def test_has_security_section(self):
        path = os.path.join(PROJECT_ROOT, "helm", "alea-intake", "values.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "security" in data


class TestHelmDeploymentTemplate:
    """Test 7: Helm deployment.yaml references values."""

    def test_deployment_template_exists(self):
        path = os.path.join(
            PROJECT_ROOT, "helm", "alea-intake", "templates", "deployment.yaml"
        )
        assert os.path.isfile(path)

    def test_references_values(self):
        path = os.path.join(
            PROJECT_ROOT, "helm", "alea-intake", "templates", "deployment.yaml"
        )
        with open(path) as f:
            text = f.read()
        assert ".Values." in text

    def test_has_health_probes(self):
        path = os.path.join(
            PROJECT_ROOT, "helm", "alea-intake", "templates", "deployment.yaml"
        )
        with open(path) as f:
            text = f.read()
        assert "livenessProbe" in text or "readinessProbe" in text

    def test_has_resource_limits(self):
        path = os.path.join(
            PROJECT_ROOT, "helm", "alea-intake", "templates", "deployment.yaml"
        )
        with open(path) as f:
            text = f.read()
        assert "resources" in text


class TestInstallScript:
    """Test 8: install.sh."""

    def test_script_exists(self):
        path = os.path.join(PROJECT_ROOT, "scripts", "install.sh")
        assert os.path.isfile(path)

    def test_script_is_executable(self):
        path = os.path.join(PROJECT_ROOT, "scripts", "install.sh")
        st = os.stat(path)
        assert st.st_mode & stat.S_IXUSR

    def test_downloads_compose_and_runs(self):
        path = os.path.join(PROJECT_ROOT, "scripts", "install.sh")
        with open(path) as f:
            text = f.read()
        assert "docker compose" in text


class TestHelmSecretTemplate:
    """Test 9: Helm secret.yaml uses secretKeyRef."""

    def test_secret_template_exists(self):
        path = os.path.join(
            PROJECT_ROOT, "helm", "alea-intake", "templates", "secret.yaml"
        )
        assert os.path.isfile(path)

    def test_no_inline_secret_values(self):
        """Pitfall 6: secrets must not have hardcoded values in values.yaml."""
        path = os.path.join(PROJECT_ROOT, "helm", "alea-intake", "values.yaml")
        with open(path) as f:
            text = f.read()
        # Should reference existingSecret, not contain actual passwords
        assert "existingSecret" in text

    def test_deployment_uses_secret_ref(self):
        """Deployment env vars should reference secrets via secretKeyRef."""
        path = os.path.join(
            PROJECT_ROOT, "helm", "alea-intake", "templates", "deployment.yaml"
        )
        with open(path) as f:
            text = f.read()
        assert "secretKeyRef" in text
