"""Tests for TLE API endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestTLEGetEndpoint:
    """Tests for GET /api/simulation/tle endpoint."""

    def test_get_tle_returns_data(self, client):
        """GET /tle should return current TLE data."""
        response = client.get("/api/simulation/tle")
        assert response.status_code == 200

        data = response.json()
        assert "line1" in data
        assert "line2" in data
        assert "inclination" in data
        assert "period" in data

    def test_get_tle_line1_format(self, client):
        """TLE line1 should start with '1 '."""
        response = client.get("/api/simulation/tle")
        data = response.json()
        assert data["line1"].startswith("1 ")

    def test_get_tle_line2_format(self, client):
        """TLE line2 should start with '2 '."""
        response = client.get("/api/simulation/tle")
        data = response.json()
        assert data["line2"].startswith("2 ")

    def test_get_tle_inclination_range(self, client):
        """Inclination should be between 0 and 180 degrees."""
        response = client.get("/api/simulation/tle")
        data = response.json()
        assert 0 <= data["inclination"] <= 180

    def test_get_tle_period_positive(self, client):
        """Period should be positive."""
        response = client.get("/api/simulation/tle")
        data = response.json()
        assert data["period"] > 0


class TestTLESetEndpoint:
    """Tests for PUT /api/simulation/tle endpoint."""

    # Valid ISS TLE for testing
    VALID_TLE_LINE1 = "1 25544U 98067A   24001.00000000  .00016717  00000-0  10270-3 0  9003"
    VALID_TLE_LINE2 = "2 25544  51.6400   0.0000 0005000   0.0000   0.0000 15.50000000000000"

    def test_set_valid_tle(self, client):
        """Setting valid TLE should succeed."""
        response = client.put(
            "/api/simulation/tle",
            json={"line1": self.VALID_TLE_LINE1, "line2": self.VALID_TLE_LINE2},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["line1"] == self.VALID_TLE_LINE1
        assert data["line2"] == self.VALID_TLE_LINE2

    def test_set_tle_updates_inclination(self, client):
        """Setting TLE should update orbital parameters."""
        response = client.put(
            "/api/simulation/tle",
            json={"line1": self.VALID_TLE_LINE1, "line2": self.VALID_TLE_LINE2},
        )
        assert response.status_code == 200

        data = response.json()
        # ISS inclination is ~51.6 degrees
        assert 50 < data["inclination"] < 53

    def test_set_invalid_tle_line1(self, client):
        """Setting invalid TLE line1 should fail."""
        response = client.put(
            "/api/simulation/tle",
            json={"line1": "invalid tle line", "line2": self.VALID_TLE_LINE2},
        )
        # Should fail validation (min_length=60)
        assert response.status_code == 422

    def test_set_invalid_tle_line2(self, client):
        """Setting invalid TLE line2 should fail."""
        response = client.put(
            "/api/simulation/tle",
            json={"line1": self.VALID_TLE_LINE1, "line2": "invalid tle line"},
        )
        # Should fail validation (min_length=60)
        assert response.status_code == 422

    def test_set_tle_sgp4_error(self, client):
        """Setting TLE that causes SGP4 error should fail."""
        # TLE with invalid satellite number (causes SGP4 error)
        bad_line1 = "1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000"
        bad_line2 = "2 00000   0.0000   0.0000 0000000   0.0000   0.0000  0.00000000000000"

        response = client.put(
            "/api/simulation/tle",
            json={"line1": bad_line1, "line2": bad_line2},
        )
        # Should fail with SGP4 validation error
        assert response.status_code == 400

    def test_set_tle_missing_line1(self, client):
        """Missing line1 should fail."""
        response = client.put(
            "/api/simulation/tle",
            json={"line2": self.VALID_TLE_LINE2},
        )
        assert response.status_code == 422

    def test_set_tle_missing_line2(self, client):
        """Missing line2 should fail."""
        response = client.put(
            "/api/simulation/tle",
            json={"line1": self.VALID_TLE_LINE1},
        )
        assert response.status_code == 422


class TestTLEIntegration:
    """Integration tests for TLE functionality."""

    VALID_TLE_LINE1 = "1 25544U 98067A   24001.00000000  .00016717  00000-0  10270-3 0  9003"
    VALID_TLE_LINE2 = "2 25544  51.6400   0.0000 0005000   0.0000   0.0000 15.50000000000000"

    def test_set_then_get_tle(self, client):
        """Setting TLE then getting should return same values."""
        # Set TLE
        client.put(
            "/api/simulation/tle",
            json={"line1": self.VALID_TLE_LINE1, "line2": self.VALID_TLE_LINE2},
        )

        # Get TLE
        response = client.get("/api/simulation/tle")
        data = response.json()

        assert data["line1"] == self.VALID_TLE_LINE1
        assert data["line2"] == self.VALID_TLE_LINE2

    def test_tle_affects_telemetry(self, client):
        """TLE should affect orbit data in telemetry."""
        # Set TLE
        client.put(
            "/api/simulation/tle",
            json={"line1": self.VALID_TLE_LINE1, "line2": self.VALID_TLE_LINE2},
        )

        # Get telemetry
        response = client.get("/api/simulation/telemetry")
        data = response.json()

        # Check orbit data exists
        assert "orbit" in data
        assert "latitude" in data["orbit"]
        assert "longitude" in data["orbit"]
        assert "altitude" in data["orbit"]

        # Altitude should be reasonable for ISS (~400 km)
        assert 350 < data["orbit"]["altitude"] < 450
