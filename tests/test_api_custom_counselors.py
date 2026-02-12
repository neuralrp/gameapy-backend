"""
Custom Counselors API endpoints tests. 

Tests create, list, update, and delete endpoints for custom advisors.
All endpoints require authentication via JWT token.
"""
import pytest
from unittest import mock
from app.db.database import db


@pytest.mark.integration
class TestCustomCounselorsCreate:
    """Test POST /api/v1/counselors/custom/create endpoint."""

    def test_create_custom_advisor_success(self, test_client_with_auth, sample_user, mock_llm_success):
        """Test creating a custom advisor successfully."""
        from app.services.advisor_generator import advisor_generator
        with mock.patch.object(
            advisor_generator,
            'generate_advisor',
            new_callable=mock.AsyncMock
        ) as mock_generate:
            mock_generate.return_value = {
                "spec": "persona_profile_v1",
                "spec_version": "1.0",
                "data": {
                    "name": "Captain Wisdom",
                    "who_you_are": "A grizzled sea captain",
                    "your_vibe": "Gruff but caring",
                    "your_worldview": "Life is like the ocean",
                    "session_template": "Ahoy there!",
                    "session_examples": [
                        {
                            "user_situation": "I'm feeling anxious",
                            "your_response": "Let's navigate through this storm",
                            "approach": "Maritime metaphor"
                        }
                    ],
                    "tags": ["maritime", "wisdom"],
                    "visuals": {"icon": "lucide:anchor"},
                    "crisis_protocol": "Call 988",
                    "hotlines": []
                }
            }

            response = test_client_with_auth.post(
                "/api/v1/counselors/custom/create",
                json={
                    "name": "Captain Wisdom",
                    "specialty": "Life advice with maritime metaphors",
                    "vibe": "Gruff but caring old sea captain"
                }
            )

            assert response.status_code == 201
            data = response.json()
            assert data['success'] is True
            assert data['message'] == "Advisor created successfully"
            assert 'counselor_id' in data['data']
            assert 'persona' in data['data']
            assert data['data']['persona']['data']['name'] == "Captain Wisdom"

            counselors = db.get_custom_counselors(sample_user)
            assert len(counselors) == 1
            assert counselors[0]['name'] == "Captain Wisdom"

    def test_create_custom_advisor_limit_exceeded(self, test_client_with_auth, sample_user):
        """Test that max 5 advisors limit is enforced."""
        for i in range(5):
            db.create_custom_counselor(
                client_id=sample_user,
                persona_data={
                    "spec": "persona_profile_v1",
                    "data": {
                        "name": f"Advisor {i}",
                        "who_you_are": "Test",
                        "your_vibe": "Friendly",
                        "your_worldview": "Help",
                        "session_template": "Hi",
                        "session_examples": [],
                        "tags": [],
                        "visuals": {},
                        "crisis_protocol": "",
                        "hotlines": []
                    }
                }
            )

        response = test_client_with_auth.post(
            "/api/v1/counselors/custom/create",
            json={
                "name": "Advisor 6",
                "specialty": "Testing",
                "vibe": "Friendly"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data['success'] is False
        assert "Maximum of 5 custom advisors allowed" in data['message']
        assert data['data']['current_count'] == 5

    def test_create_custom_advisor_invalid_input(self, test_client_with_auth, sample_user):
        """Test validation of invalid input."""
        response = test_client_with_auth.post(
            "/api/v1/counselors/custom/create",
            json={
                "name": "Test",
                "specialty": "Too short"
            }
        )

        assert response.status_code == 422


@pytest.mark.integration
class TestCustomCounselorsList:
    """Test GET /api/v1/counselors/custom/list endpoint."""

    def test_list_custom_advisors_success(self, test_client_with_auth, sample_user):
        """Test listing custom advisors for a client."""
        db.create_custom_counselor(
            client_id=sample_user,
            persona_data={
                "spec": "persona_profile_v1",
                "data": {
                    "name": "Advisor 1",
                    "who_you_are": "Test",
                    "your_vibe": "Friendly",
                    "your_worldview": "Help",
                    "session_template": "Hi",
                    "session_examples": [],
                    "tags": [],
                    "visuals": {},
                    "crisis_protocol": "",
                    "hotlines": []
                }
            }
        )
        db.create_custom_counselor(
            client_id=sample_user,
            persona_data={
                "spec": "persona_profile_v1",
                "data": {
                    "name": "Advisor 2",
                    "who_you_are": "Test",
                    "your_vibe": "Calm",
                    "your_worldview": "Help",
                    "session_template": "Hello",
                    "session_examples": [],
                    "tags": [],
                    "visuals": {},
                    "crisis_protocol": "",
                    "hotlines": []
                }
            }
        )

        response = test_client_with_auth.get("/api/v1/counselors/custom/list")

        assert response.status_code == 200
        advisors = response.json()
        assert len(advisors) == 2
        assert advisors[0]['name'] in ["Advisor 1", "Advisor 2"]
        assert advisors[1]['name'] in ["Advisor 1", "Advisor 2"]
        assert 'id' in advisors[0]
        assert 'profile' in advisors[0]

    def test_list_custom_advisors_empty(self, test_client_with_auth, sample_user):
        """Test listing returns empty list for client with no advisors."""
        response = test_client_with_auth.get("/api/v1/counselors/custom/list")

        assert response.status_code == 200
        advisors = response.json()
        assert len(advisors) == 0
        assert isinstance(advisors, list)


@pytest.mark.integration
class TestCustomCounselorsUpdate:
    """Test PUT /api/v1/counselors/custom/update endpoint."""

    def test_update_custom_advisor_success(self, test_client_with_auth, sample_user):
        """Test updating a custom advisor successfully."""
        counselor_id = db.create_custom_counselor(
            client_id=sample_user,
            persona_data={
                "spec": "persona_profile_v1",
                "data": {
                    "name": "Original Name",
                    "who_you_are": "Original",
                    "your_vibe": "Friendly",
                    "your_worldview": "Help",
                    "session_template": "Hi",
                    "session_examples": [],
                    "tags": [],
                    "visuals": {},
                    "crisis_protocol": "",
                    "hotlines": []
                }
            }
        )

        response = test_client_with_auth.put(
            "/api/v1/counselors/custom/update",
            json={
                "counselor_id": counselor_id,
                "persona_data": {
                    "spec": "persona_profile_v1",
                    "data": {
                        "name": "Updated Name",
                        "who_you_are": "Updated",
                        "your_vibe": "Calm",
                        "your_worldview": "Help",
                        "session_template": "Hello",
                        "session_examples": [],
                        "tags": [],
                        "visuals": {},
                        "crisis_protocol": "",
                        "hotlines": []
                    }
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['message'] == "Advisor updated successfully"

        counselors = db.get_custom_counselors(sample_user)
        assert len(counselors) == 1
        assert counselors[0]['name'] == "Updated Name"

    def test_update_custom_advisor_not_found(self, test_client_with_auth):
        """Test updating non-existent advisor returns 404."""
        response = test_client_with_auth.put(
            "/api/v1/counselors/custom/update",
            json={
                "counselor_id": 99999,
                "persona_data": {
                    "spec": "persona_profile_v1",
                    "data": {
                        "name": "Test",
                        "who_you_are": "Test",
                        "your_vibe": "Friendly",
                        "your_worldview": "Help",
                        "session_template": "Hi",
                        "session_examples": [],
                        "tags": [],
                        "visuals": {},
                        "crisis_protocol": "",
                        "hotlines": []
                    }
                }
            }
        )

        assert response.status_code == 404
        assert "not found" in response.json()['detail'].lower()

    def test_update_system_persona_forbidden(self, test_client_with_auth):
        """Test attempting to update system persona returns 403."""
        system_counselors = db.get_all_counselors()
        if not system_counselors:
            pytest.skip("No system counselors available")
        
        system_counselor_id = system_counselors[0]['id']

        response = test_client_with_auth.put(
            "/api/v1/counselors/custom/update",
            json={
                "counselor_id": system_counselor_id,
                "persona_data": {
                    "spec": "persona_profile_v1",
                    "data": {
                        "name": "Hacked",
                        "who_you_are": "Hacked",
                        "your_vibe": "Hacked",
                        "your_worldview": "Hacked",
                        "session_template": "Hi",
                        "session_examples": [],
                        "tags": [],
                        "visuals": {},
                        "crisis_protocol": "",
                        "hotlines": []
                    }
                }
            }
        )

        assert response.status_code == 403
        assert "access denied" in response.json()['detail'].lower()

    def test_update_custom_advisor_invalid_structure(self, test_client_with_auth):
        """Test updating with invalid persona structure."""
        response = test_client_with_auth.put(
            "/api/v1/counselors/custom/update",
            json={
                "counselor_id": 1,
                "persona_data": "not a dict"
            }
        )

        assert response.status_code == 422


@pytest.mark.integration
class TestCustomCounselorsDelete:
    """Test DELETE /api/v1/counselors/custom/{counselor_id} endpoint."""

    def test_delete_custom_advisor_success(self, test_client_with_auth, sample_user):
        """Test deleting a custom advisor successfully."""
        counselor_id = db.create_custom_counselor(
            client_id=sample_user,
            persona_data={
                "spec": "persona_profile_v1",
                "data": {
                    "name": "To Delete",
                    "who_you_are": "Test",
                    "your_vibe": "Friendly",
                    "your_worldview": "Help",
                    "session_template": "Hi",
                    "session_examples": [],
                    "tags": [],
                    "visuals": {},
                    "crisis_protocol": "",
                    "hotlines": []
                }
            }
        )

        response = test_client_with_auth.delete(f"/api/v1/counselors/custom/{counselor_id}")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['message'] == "Advisor deleted successfully"

        counselors = db.get_custom_counselors(sample_user)
        assert len(counselors) == 0

    def test_delete_custom_advisor_not_found(self, test_client_with_auth):
        """Test deleting non-existent advisor returns 404."""
        response = test_client_with_auth.delete("/api/v1/counselors/custom/99999")

        assert response.status_code == 404
        assert "not found" in response.json()['detail'].lower()

    def test_delete_wrong_client(self, db, sample_user):
        """Test deleting advisor owned by another client returns 404."""
        from app.auth.security import get_password_hash
        
        other_user_id = db.create_user(
            username="otheruser",
            password_hash=get_password_hash("testpass123"),
            profile_data={
                'data': {
                    'name': 'Other User',
                    'personality': 'Test',
                    'tags': ['test']
                }
            }
        )

        counselor_id = db.create_custom_counselor(
            client_id=other_user_id,
            persona_data={
                "spec": "persona_profile_v1",
                "data": {
                    "name": "Protected Advisor",
                    "who_you_are": "Test",
                    "your_vibe": "Friendly",
                    "your_worldview": "Help",
                    "session_template": "Hi",
                    "session_examples": [],
                    "tags": [],
                    "visuals": {},
                    "crisis_protocol": "",
                    "hotlines": []
                }
            }
        )

        from app.auth.security import create_access_token
        from fastapi.testclient import TestClient
        from main import app
        
        original_token = create_access_token(data={"sub": str(sample_user)})
        client = TestClient(app)
        
        response = client.delete(
            f"/api/v1/counselors/custom/{counselor_id}",
            headers={"Authorization": f"Bearer {original_token}"}
        )

        assert response.status_code == 404
        assert "not found" in response.json()['detail'].lower()

        counselors = db.get_custom_counselors(other_user_id)
        assert len(counselors) == 1
        assert counselors[0]['name'] == "Protected Advisor"
