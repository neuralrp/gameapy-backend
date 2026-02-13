"""
Farm API Endpoint Tests.

Tests all farm-related API endpoints with authentication:
- Farm status
- Plant/harvest crops
- Buy/harvest animals
- Farm upgrades
- Daily login
- Farm shop

Note: Farm endpoints are at /api/v1/farm/* (not /api/v1/gameapy/farm/*)
"""
import pytest
from fastapi.testclient import TestClient
from app.db.database import db


@pytest.mark.integration
class TestFarmStatusAPI:
    """Test farm status API endpoint."""

    @pytest.mark.integration
    def test_get_farm_status_authenticated(self, test_client_with_auth, sample_user):
        """GET /farm/status returns farm status for authenticated user."""
        response = test_client_with_auth.get("/api/v1/farm/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'gold' in data
        assert 'farmLevel' in data
        assert 'messageCounter' in data
        assert 'crops' in data
        assert 'animals' in data
        assert 'decorations' in data
        assert 'maxPlots' in data
        assert 'maxBarnSlots' in data

    @pytest.mark.integration
    def test_get_farm_status_auto_initializes(self, test_client_with_auth, sample_user):
        """GET /farm/status auto-initializes farm if not exists."""
        response = test_client_with_auth.get("/api/v1/farm/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['gold'] == 0
        assert data['farmLevel'] == 1


@pytest.mark.integration
class TestPlantCropAPI:
    """Test crop planting API endpoint."""

    @pytest.mark.integration
    def test_plant_crop_endpoint(self, test_client_with_auth, sample_user):
        """POST /farm/plant plants a crop successfully."""
        db.update_gold_coins(sample_user, 10, "test")
        
        response = test_client_with_auth.post(
            "/api/v1/farm/plant",
            params={"crop_type": "parsnip", "plot_index": 0}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['goldSpent'] == 5

    @pytest.mark.integration
    def test_plant_crop_invalid_type(self, test_client_with_auth, sample_user):
        """POST /farm/plant returns 400 for invalid crop type."""
        response = test_client_with_auth.post(
            "/api/v1/farm/plant",
            params={"crop_type": "invalid", "plot_index": 0}
        )
        
        assert response.status_code == 400

    @pytest.mark.integration
    def test_plant_crop_plot_occupied(self, test_client_with_auth, sample_user):
        """POST /farm/plant returns 400 for occupied plot."""
        db.update_gold_coins(sample_user, 10, "test")
        
        test_client_with_auth.post(
            "/api/v1/farm/plant",
            params={"crop_type": "parsnip", "plot_index": 0}
        )
        
        response = test_client_with_auth.post(
            "/api/v1/farm/plant",
            params={"crop_type": "potato", "plot_index": 0}
        )
        
        assert response.status_code == 400

    @pytest.mark.integration
    def test_plant_crop_insufficient_gold(self, test_client_with_auth, sample_user):
        """POST /farm/plant returns 400 when not enough gold."""
        response = test_client_with_auth.post(
            "/api/v1/farm/plant",
            params={"crop_type": "corn", "plot_index": 0}
        )
        
        assert response.status_code == 400


@pytest.mark.integration
class TestHarvestCropAPI:
    """Test crop harvesting API endpoint."""

    @pytest.mark.integration
    def test_harvest_crop_endpoint(self, test_client_with_auth, sample_user):
        """POST /farm/harvest harvests a mature crop."""
        db.update_gold_coins(sample_user, 10, "test")
        
        test_client_with_auth.post(
            "/api/v1/farm/plant",
            params={"crop_type": "parsnip", "plot_index": 0}
        )
        
        test_client_with_auth.post("/api/v1/farm/increment-messages")
        test_client_with_auth.post("/api/v1/farm/increment-messages")
        test_client_with_auth.post("/api/v1/farm/increment-messages")
        test_client_with_auth.post("/api/v1/farm/increment-messages")
        test_client_with_auth.post("/api/v1/farm/increment-messages")
        test_client_with_auth.post("/api/v1/farm/increment-messages")
        test_client_with_auth.post("/api/v1/farm/increment-messages")
        test_client_with_auth.post("/api/v1/farm/increment-messages")
        test_client_with_auth.post("/api/v1/farm/increment-messages")
        test_client_with_auth.post("/api/v1/farm/increment-messages")
        
        response = test_client_with_auth.post(
            "/api/v1/farm/harvest",
            params={"plot_index": 0}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['goldEarned'] == 10

    @pytest.mark.integration
    def test_harvest_crop_not_mature(self, test_client_with_auth, sample_user):
        """POST /farm/harvest returns 400 for immature crop."""
        db.update_gold_coins(sample_user, 10, "test")
        
        test_client_with_auth.post(
            "/api/v1/farm/plant",
            params={"crop_type": "parsnip", "plot_index": 0}
        )
        
        response = test_client_with_auth.post(
            "/api/v1/farm/harvest",
            params={"plot_index": 0}
        )
        
        assert response.status_code == 400


@pytest.mark.integration
class TestBuyAnimalAPI:
    """Test animal purchase API endpoint."""

    @pytest.mark.integration
    def test_buy_animal_endpoint(self, test_client_with_auth, sample_user):
        """POST /farm/buy-animal purchases an animal."""
        db.update_gold_coins(sample_user, 50, "test")
        
        response = test_client_with_auth.post(
            "/api/v1/farm/buy-animal",
            params={"animal_type": "chicken", "slot_index": 0}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['goldSpent'] == 30

    @pytest.mark.integration
    def test_buy_animal_invalid_type(self, test_client_with_auth, sample_user):
        """POST /farm/buy-animal returns 400 for invalid animal."""
        response = test_client_with_auth.post(
            "/api/v1/farm/buy-animal",
            params={"animal_type": "invalid", "slot_index": 0}
        )
        
        assert response.status_code == 400

    @pytest.mark.integration
    def test_buy_animal_insufficient_gold(self, test_client_with_auth, sample_user):
        """POST /farm/buy-animal returns 400 when not enough gold."""
        response = test_client_with_auth.post(
            "/api/v1/farm/buy-animal",
            params={"animal_type": "cow", "slot_index": 0}
        )
        
        assert response.status_code == 400


@pytest.mark.integration
class TestFarmShopAPI:
    """Test farm shop API endpoint."""

    @pytest.mark.integration
    def test_get_farm_shop(self, test_client_with_auth, sample_user):
        """GET /farm/shop-v2 returns shop items."""
        response = test_client_with_auth.get("/api/v1/farm/shop-v2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'seeds' in data
        assert 'animals' in data
        assert 'decorations' in data
        assert 'playerGold' in data
        assert 'farmLevel' in data
        assert 'upgradeCost' in data

    @pytest.mark.integration
    def test_farm_shop_at_level_1(self, test_client_with_auth, sample_user):
        """Farm shop shows correct animals at level 1."""
        response = test_client_with_auth.get("/api/v1/farm/shop-v2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data['animals']) == 1
        assert data['animals'][0]['id'] == 'chicken'


@pytest.mark.integration
class TestDailyLoginAPI:
    """Test daily login API endpoint."""

    @pytest.mark.integration
    def test_daily_login_endpoint(self, test_client_with_auth, sample_user):
        """POST /game-state/daily-login claims daily bonus."""
        response = test_client_with_auth.post("/api/v1/game-state/daily-login")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['gold_awarded'] == 5

    @pytest.mark.integration
    def test_daily_login_already_claimed(self, test_client_with_auth, sample_user):
        """POST /game-state/daily-login returns 400 if already claimed."""
        test_client_with_auth.post("/api/v1/game-state/daily-login")
        
        response = test_client_with_auth.post("/api/v1/game-state/daily-login")
        
        assert response.status_code == 400


@pytest.mark.integration
class TestFarmUpgradeAPI:
    """Test farm upgrade API endpoint."""

    @pytest.mark.integration
    def test_upgrade_farm_endpoint(self, test_client_with_auth, sample_user):
        """POST /farm/upgrade upgrades farm level."""
        db.update_gold_coins(sample_user, 100, "test")
        
        response = test_client_with_auth.post("/api/v1/farm/upgrade")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['newLevel'] == 2

    @pytest.mark.integration
    def test_upgrade_farm_insufficient_gold(self, test_client_with_auth, sample_user):
        """POST /farm/upgrade returns 400 with insufficient gold."""
        response = test_client_with_auth.post("/api/v1/farm/upgrade")
        
        assert response.status_code == 400


@pytest.mark.integration
class TestMessageCounterAPI:
    """Test message counter API endpoint."""

    @pytest.mark.integration
    def test_increment_messages(self, test_client_with_auth, sample_user):
        """POST /farm/increment-messages increments counter."""
        response = test_client_with_auth.post("/api/v1/farm/increment-messages")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['message_counter'] == 1


@pytest.mark.integration
class TestDecorationAPI:
    """Test decoration API endpoint."""

    @pytest.mark.integration
    def test_add_decoration_endpoint(self, test_client_with_auth, sample_user):
        """POST /farm/add-decoration adds a decoration."""
        db.update_gold_coins(sample_user, 30, "test")
        
        response = test_client_with_auth.post(
            "/api/v1/farm/add-decoration",
            params={"decoration_type": "oak_tree", "x": 1, "y": 1, "variant": 0}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['goldSpent'] == 25

    @pytest.mark.integration
    def test_add_decoration_invalid_type(self, test_client_with_auth, sample_user):
        """POST /farm/add-decoration returns 400 for invalid type."""
        response = test_client_with_auth.post(
            "/api/v1/farm/add-decoration",
            params={"decoration_type": "invalid", "x": 1, "y": 1}
        )
        
        assert response.status_code == 400
