"""
Database Farm Operations Tests.

Tests all farm-related database methods including:
- Farm initialization
- Message counter
- Daily login
- Crop planting and harvesting
- Animal buying and harvesting
- Decorations
- Farm upgrades
- Farm status queries
"""
import pytest
import datetime
from app.db.database import db


@pytest.mark.integration
class TestFarmInitialization:
    """Test farm initialization."""

    @pytest.mark.integration
    def test_initialize_farm_creates_game_state(self, sample_client):
        """Initialize farm checks existing game state."""
        db.initialize_farm(sample_client)
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT gold_coins, farm_level, message_counter, last_login_date FROM game_state WHERE client_id = %s",
                (sample_client,)
            )
            row = cursor.fetchone()
            
            assert row is not None
            assert row['gold_coins'] == 0
            assert row['farm_level'] == 1
            assert row['message_counter'] == 0

    @pytest.mark.integration
    def test_initialize_farm_idempotent(self, sample_client):
        """Initialize farm can be called multiple times without duplication."""
        db.initialize_farm(sample_client)
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM game_state WHERE client_id = %s", (sample_client,))
            count_before = cursor.fetchone()['count']
        
        db.initialize_farm(sample_client)
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM game_state WHERE client_id = %s", (sample_client,))
            count_after = cursor.fetchone()['count']
        
        assert count_before == count_after == 1


@pytest.mark.integration
class TestMessageCounter:
    """Test message counter operations."""

    @pytest.mark.integration
    def test_increment_message_counter(self, sample_client):
        """Increment message counter returns new value."""
        new_count = db.increment_message_counter(sample_client)
        
        assert new_count == 1
        
        new_count = db.increment_message_counter(sample_client)
        assert new_count == 2

    @pytest.mark.integration
    def test_get_message_counter(self, sample_client):
        """Get message counter returns current value."""
        db.increment_message_counter(sample_client)
        db.increment_message_counter(sample_client)
        
        count = db.get_message_counter(sample_client)
        assert count == 2

    @pytest.mark.integration
    def test_get_message_counter_no_farm(self, sample_client):
        """Get message counter returns 0 for new client."""
        count = db.get_message_counter(sample_client)
        assert count == 0


@pytest.mark.integration
class TestDailyLogin:
    """Test daily login bonus."""

    @pytest.mark.integration
    def test_claim_daily_login_first_time(self, sample_client):
        """Claim daily login awards 5 gold."""
        success, message = db.claim_daily_login(sample_client)
        
        assert success is True
        assert "5 gold" in message
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT gold_coins, last_login_date FROM game_state WHERE client_id = %s", (sample_client,))
            row = cursor.fetchone()
            assert row['gold_coins'] == 5
            assert row['last_login_date'] is not None

    @pytest.mark.integration
    def test_claim_daily_login_already_claimed(self, sample_client):
        """Cannot claim daily login twice in one day."""
        db.claim_daily_login(sample_client)
        success, message = db.claim_daily_login(sample_client)
        
        assert success is False
        assert "Already claimed" in message

    @pytest.mark.integration
    def test_claim_daily_login_game_state_exists(self, sample_client):
        """Game state exists after client creation."""
        success, message = db.claim_daily_login(sample_client)
        assert success is True


@pytest.mark.integration
class TestPlantCrop:
    """Test crop planting."""

    @pytest.mark.integration
    def test_plant_crop_success(self, sample_client):
        """Plant crop deducts gold and creates crop record."""
        db.update_gold_coins(sample_client, 10, "test_gold")
        
        result = db.plant_crop(sample_client, "parsnip", 0, 0)
        
        assert result['success'] is True
        assert result['goldSpent'] == 5
        assert result['newGold'] == 5
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT crop_type, plot_index, planted_at_message, growth_duration, is_harvested FROM planted_crops WHERE client_id = %s",
                (sample_client,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row['crop_type'] == "parsnip"
            assert row['plot_index'] == 0
            assert row['planted_at_message'] == 0
            assert row['is_harvested'] is False

    @pytest.mark.integration
    def test_plant_crop_invalid_type(self, sample_client):
        """Plant crop returns error for invalid crop type."""
        result = db.plant_crop(sample_client, "invalid_crop", 0, 0)
        
        assert result['success'] is False
        assert "Invalid crop type" in result['error']

    @pytest.mark.integration
    def test_plant_crop_plot_occupied(self, sample_client):
        """Plant crop returns error if plot already has crop."""
        db.update_gold_coins(sample_client, 10, "test_gold")
        
        db.plant_crop(sample_client, "parsnip", 0, 0)
        result = db.plant_crop(sample_client, "potato", 0, 0)
        
        assert result['success'] is False
        assert "already has a crop" in result['error']

    @pytest.mark.integration
    def test_plant_crop_insufficient_gold(self, sample_client):
        """Plant crop returns error when not enough gold."""
        result = db.plant_crop(sample_client, "parsnip", 0, 0)
        
        assert result['success'] is False
        assert "Not enough gold" in result['error']

    @pytest.mark.integration
    def test_plant_crop_plot_not_unlocked(self, sample_client):
        """Plant crop returns error for locked plot."""
        db.update_gold_coins(sample_client, 10, "test_gold")
        
        result = db.plant_crop(sample_client, "parsnip", 10, 0)
        
        assert result['success'] is False
        assert "not unlocked" in result['error']


@pytest.mark.integration
class TestHarvestCrop:
    """Test crop harvesting."""

    @pytest.mark.integration
    def test_harvest_crop_success(self, sample_client):
        """Harvest mature crop awards gold."""
        db.update_gold_coins(sample_client, 10, "test_gold")
        
        db.plant_crop(sample_client, "parsnip", 0, 0)
        
        result = db.harvest_crop(sample_client, 0, 10)
        
        assert result['success'] is True
        assert result['cropType'] == "parsnip"
        assert result['goldEarned'] == 10
        assert result['newGold'] == 15

    @pytest.mark.integration
    def test_harvest_crop_not_mature(self, sample_client):
        """Cannot harvest immature crop."""
        db.update_gold_coins(sample_client, 10, "test_gold")
        
        db.plant_crop(sample_client, "parsnip", 0, 0)
        
        result = db.harvest_crop(sample_client, 0, 5)
        
        assert result['success'] is False
        assert "not yet mature" in result['error']

    @pytest.mark.integration
    def test_harvest_crop_no_crop(self, sample_client):
        """Cannot harvest empty plot."""
        result = db.harvest_crop(sample_client, 0, 0)
        
        assert result['success'] is False
        assert "No crop" in result['error']


@pytest.mark.integration
class TestBuyAnimal:
    """Test animal purchase."""

    @pytest.mark.integration
    def test_buy_animal_success(self, sample_client):
        """Buy animal deducts gold and creates animal record."""
        db.update_gold_coins(sample_client, 50, "test_gold")
        
        result = db.buy_animal(sample_client, "chicken", 0, 0)
        
        assert result['success'] is True
        assert result['goldSpent'] == 30
        assert result['newGold'] == 20
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT animal_type, slot_index, acquired_at_message, maturity_duration, is_mature FROM farm_animals WHERE client_id = %s",
                (sample_client,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row['animal_type'] == "chicken"
            assert row['slot_index'] == 0
            assert row['is_mature'] is False

    @pytest.mark.integration
    def test_buy_animal_invalid_type(self, sample_client):
        """Buy animal returns error for invalid animal type."""
        result = db.buy_animal(sample_client, "invalid_animal", 0, 0)
        
        assert result['success'] is False
        assert "Invalid animal type" in result['error']

    @pytest.mark.integration
    def test_buy_animal_slot_occupied(self, sample_client):
        """Buy animal returns error if slot is occupied."""
        db.update_gold_coins(sample_client, 200, "test_gold")
        
        db.buy_animal(sample_client, "chicken", 0, 0)
        result = db.buy_animal(sample_client, "cow", 0, 0)
        
        assert result['success'] is False
        assert "Slot already occupied" in result['error']

    @pytest.mark.integration
    def test_buy_animal_insufficient_gold(self, sample_client):
        """Buy animal returns error when not enough gold."""
        result = db.buy_animal(sample_client, "chicken", 0, 0)
        
        assert result['success'] is False
        assert "Not enough gold" in result['error']

    @pytest.mark.integration
    def test_buy_animal_slot_not_unlocked(self, sample_client):
        """Buy animal returns error for locked barn slot."""
        db.update_gold_coins(sample_client, 100, "test_gold")
        
        result = db.buy_animal(sample_client, "chicken", 5, 0)
        
        assert result['success'] is False
        assert "not unlocked" in result['error']


@pytest.mark.integration
class TestHarvestAnimal:
    """Test animal harvesting/selling."""

    @pytest.mark.integration
    def test_harvest_animal_success(self, sample_client):
        """Harvest mature animal awards gold."""
        db.update_gold_coins(sample_client, 50, "test_gold")
        
        db.buy_animal(sample_client, "chicken", 0, 0)
        
        result = db.harvest_animal(sample_client, 0, 40)
        
        assert result['success'] is True
        assert result['animalType'] == "chicken"
        assert result['goldEarned'] == 50

    @pytest.mark.integration
    def test_harvest_animal_not_mature(self, sample_client):
        """Cannot harvest immature animal."""
        db.update_gold_coins(sample_client, 50, "test_gold")
        
        db.buy_animal(sample_client, "chicken", 0, 0)
        
        result = db.harvest_animal(sample_client, 0, 20)
        
        assert result['success'] is False
        assert "not yet mature" in result['error']

    @pytest.mark.integration
    def test_harvest_animal_already_harvested(self, sample_client):
        """Cannot harvest already mature animal."""
        db.update_gold_coins(sample_client, 50, "test_gold")
        
        db.buy_animal(sample_client, "chicken", 0, 0)
        db.harvest_animal(sample_client, 0, 40)
        
        result = db.harvest_animal(sample_client, 0, 50)
        
        assert result['success'] is False
        assert "already harvested" in result['error']

    @pytest.mark.integration
    def test_harvest_animal_no_animal(self, sample_client):
        """Cannot harvest empty slot."""
        result = db.harvest_animal(sample_client, 0, 0)
        
        assert result['success'] is False
        assert "No animal" in result['error']


@pytest.mark.integration
class TestDecoration:
    """Test farm decoration operations."""

    @pytest.mark.integration
    def test_add_decoration_success(self, sample_client):
        """Add decoration deducts gold and creates record."""
        db.update_gold_coins(sample_client, 30, "test_gold")
        
        result = db.add_decoration(sample_client, "oak_tree", 1, 1, 0)
        
        assert result['success'] is True
        assert result['goldSpent'] == 25
        assert result['newGold'] == 5

    @pytest.mark.integration
    def test_add_decoration_invalid_type(self, sample_client):
        """Add decoration returns error for invalid type."""
        result = db.add_decoration(sample_client, "invalid_decor", 1, 1, 0)
        
        assert result['success'] is False
        assert "Invalid decoration type" in result['error']

    @pytest.mark.integration
    def test_add_decoration_insufficient_gold(self, sample_client):
        """Add decoration returns error when not enough gold."""
        result = db.add_decoration(sample_client, "oak_tree", 1, 1, 0)
        
        assert result['success'] is False
        assert "Not enough gold" in result['error']


@pytest.mark.integration
class TestFarmUpgrade:
    """Test farm level upgrades."""

    @pytest.mark.integration
    def test_upgrade_farm_level_success(self, sample_client):
        """Upgrade farm level deducts gold and increments level."""
        db.update_gold_coins(sample_client, 100, "test_gold")
        
        result = db.upgrade_farm_level(sample_client)
        
        assert result['success'] is True
        assert result['newLevel'] == 2
        assert result['cost'] == 75
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT farm_level FROM game_state WHERE client_id = %s", (sample_client,))
            row = cursor.fetchone()
            assert row['farm_level'] == 2

    @pytest.mark.integration
    def test_upgrade_farm_max_level(self, sample_client):
        """Cannot upgrade beyond max level."""
        db.update_gold_coins(sample_client, 2000, "test_gold")
        
        for _ in range(6):
            db.upgrade_farm_level(sample_client)
        
        result = db.upgrade_farm_level(sample_client)
        
        assert result['success'] is False
        assert "Maximum farm level" in result['error']

    @pytest.mark.integration
    def test_upgrade_farm_insufficient_gold(self, sample_client):
        """Cannot upgrade with insufficient gold."""
        result = db.upgrade_farm_level(sample_client)
        
        assert result['success'] is False
        assert "Not enough gold" in result['error']


@pytest.mark.integration
class TestFarmStatus:
    """Test farm status queries."""

    @pytest.mark.integration
    def test_get_farm_status_complete(self, sample_client):
        """Get farm status returns complete farm data."""
        db.update_gold_coins(sample_client, 100, "test_gold")
        db.plant_crop(sample_client, "parsnip", 0, 0)
        db.buy_animal(sample_client, "chicken", 0, 0)
        db.add_decoration(sample_client, "oak_tree", 1, 1, 0)
        
        status = db.get_farm_status(sample_client)
        
        assert 'gold' in status
        assert 'farmLevel' in status
        assert 'messageCounter' in status
        assert 'crops' in status
        assert 'animals' in status
        assert 'decorations' in status
        assert 'maxPlots' in status
        assert 'maxBarnSlots' in status
        
        assert len(status['crops']) == 1
        assert len(status['animals']) == 1
        assert len(status['decorations']) == 1

    @pytest.mark.integration
    def test_get_farm_status_returns_data(self, sample_client):
        """Get farm status returns data for new client."""
        status = db.get_farm_status(sample_client)
        
        assert 'gold' in status
        assert 'farmLevel' in status

    @pytest.mark.integration
    def test_get_farm_shop(self, sample_client):
        """Get farm shop returns available items."""
        db.update_gold_coins(sample_client, 100, "test_gold")
        
        shop = db.get_farm_shop(sample_client)
        
        assert 'seeds' in shop
        assert 'animals' in shop
        assert 'decorations' in shop
        assert 'playerGold' in shop
        assert 'farmLevel' in shop
        assert 'upgradeCost' in shop
        
        assert len(shop['seeds']) == 5
        assert shop['farmLevel'] == 1


@pytest.mark.integration
class TestGoldOperations:
    """Test gold update operations."""

    @pytest.mark.integration
    def test_update_gold_coins(self, sample_client):
        """Update gold coins changes gold amount."""
        db.update_gold_coins(sample_client, 10, "test_award")
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT gold_coins FROM game_state WHERE client_id = %s", (sample_client,))
            row = cursor.fetchone()
            assert row['gold_coins'] == 10


@pytest.mark.integration
class TestTilling:
    """Test plot tilling operations."""

    @pytest.mark.integration
    def test_till_plot_success(self, sample_client):
        """Till plot creates farm_plots record."""
        result = db.till_plot(sample_client, 0)
        assert result['success'] is True
        assert result['plotIndex'] == 0
        assert result['state'] == 'tilled'

    @pytest.mark.integration
    def test_till_plot_already_tilled(self, sample_client):
        """Cannot till already tilled plot."""
        db.till_plot(sample_client, 0)
        result = db.till_plot(sample_client, 0)
        assert result['success'] is False
        assert 'already tilled' in result['error']

    @pytest.mark.integration
    def test_till_plot_has_crop(self, sample_client):
        """Cannot till plot with existing crop."""
        db.update_gold_coins(sample_client, 10, "test")
        db.plant_crop(sample_client, "parsnip", 0, 0)
        result = db.till_plot(sample_client, 0)
        assert result['success'] is False

    @pytest.mark.integration
    def test_till_plot_not_unlocked(self, sample_client):
        """Cannot till plot beyond farm level."""
        result = db.till_plot(sample_client, 10)
        assert result['success'] is False
        assert 'not unlocked' in result['error']

    @pytest.mark.integration
    def test_get_tilled_plots_empty(self, sample_client):
        """Get tilled plots returns empty list initially."""
        plots = db.get_tilled_plots(sample_client)
        assert plots == []

    @pytest.mark.integration
    def test_get_tilled_plots_with_crops(self, sample_client):
        """Get tilled plots excludes plots with crops."""
        db.update_gold_coins(sample_client, 20, "test")
        db.till_plot(sample_client, 0)
        db.till_plot(sample_client, 1)
        db.plant_crop(sample_client, "parsnip", 0, 0)
        
        plots = db.get_tilled_plots(sample_client)
        assert plots == [1]


@pytest.mark.integration
class TestWatering:
    """Test crop watering system."""

    @pytest.mark.integration
    def test_water_crop_success(self, sample_client):
        """Water crop adds stage to watered_stages."""
        db.update_gold_coins(sample_client, 10, "test")
        db.plant_crop(sample_client, "parsnip", 0, 0)
        
        result = db.water_crop(sample_client, 0, 0)
        assert result['success'] is True
        assert 0 in result['wateredStages']

    @pytest.mark.integration
    def test_water_crop_already_watered_stage(self, sample_client):
        """Cannot water same stage twice."""
        db.update_gold_coins(sample_client, 10, "test")
        db.plant_crop(sample_client, "parsnip", 0, 0)
        db.water_crop(sample_client, 0, 0)
        
        result = db.water_crop(sample_client, 0, 0)
        assert result['success'] is False
        assert 'already watered' in result['error']

    @pytest.mark.integration
    def test_water_crop_no_crop(self, sample_client):
        """Cannot water empty plot."""
        result = db.water_crop(sample_client, 0, 0)
        assert result['success'] is False
        assert 'No crop' in result['error']

    @pytest.mark.integration
    def test_water_crop_multiple_stages(self, sample_client):
        """Can water multiple different stages."""
        db.update_gold_coins(sample_client, 10, "test")
        db.plant_crop(sample_client, "parsnip", 0, 0)
        
        db.water_crop(sample_client, 0, 0)
        result = db.water_crop(sample_client, 0, 1)
        assert result['success'] is True
        assert 0 in result['wateredStages']
        assert 1 in result['wateredStages']

    @pytest.mark.integration
    def test_watered_stages_persistence(self, sample_client):
        """Watered stages persist in database."""
        db.update_gold_coins(sample_client, 10, "test")
        db.plant_crop(sample_client, "parsnip", 0, 0)
        db.water_crop(sample_client, 0, 0)
        db.water_crop(sample_client, 0, 2)
        
        status = db.get_farm_status(sample_client)
        crop = status['crops'][0]
        assert 0 in crop['wateredStages']
        assert 2 in crop['wateredStages']


@pytest.mark.integration
class TestMermaidUnlock:
    """Test mermaid unlock feature (Marina milestone)."""

    @pytest.mark.integration
    def test_unlock_mermaid_success(self, sample_client):
        """Unlock mermaid adds mermaid to farm_animals."""
        result = db.unlock_mermaid(sample_client)
        assert result['success'] is True
        assert 'Mermaid unlocked' in result['message']

    @pytest.mark.integration
    def test_unlock_mermaid_already_unlocked(self, sample_client):
        """Unlock mermaid is idempotent."""
        db.unlock_mermaid(sample_client)
        result = db.unlock_mermaid(sample_client)
        assert result['success'] is True
        assert result.get('alreadyUnlocked') is True

    @pytest.mark.integration
    def test_mermaid_appears_in_farm_status(self, sample_client):
        """Mermaid appears in farm status after unlock."""
        db.unlock_mermaid(sample_client)
        status = db.get_farm_status(sample_client)
        mermaid = [a for a in status['animals'] if a['animalType'] == 'mermaid']
        assert len(mermaid) == 1

    @pytest.mark.integration
    def test_get_marina_message_count(self, sample_client, sample_counselor):
        """Get message count for counselor."""
        db.create_session(sample_client, sample_counselor)
        count = db.get_marina_message_count(sample_client, sample_counselor)
        assert isinstance(count, int)


@pytest.mark.integration
class TestFarmItems:
    """Test legacy farm items system."""

    @pytest.mark.integration
    def test_get_farm_items_empty(self, sample_client):
        """Get farm items returns empty list initially."""
        items = db.get_farm_items(sample_client)
        assert items == []

    @pytest.mark.integration
    def test_add_farm_item_success(self, sample_client):
        """Add farm item creates record."""
        item_id = db.add_farm_item(
            client_id=sample_client,
            item_type="egg",
            item_name="Chicken Egg",
            item_metadata={"quality": "normal"}
        )
        assert item_id > 0
        
        items = db.get_farm_items(sample_client)
        assert len(items) == 1
        assert items[0]['item_type'] == "egg"

    @pytest.mark.integration
    def test_add_farm_item_with_metadata(self, sample_client):
        """Add farm item stores metadata."""
        db.add_farm_item(
            client_id=sample_client,
            item_type="seed",
            item_name="Corn Seeds",
            item_metadata={"count": 5}
        )
        
        items = db.get_farm_items(sample_client)
        assert items[0]['metadata']['count'] == 5


@pytest.mark.integration
class TestGrowthProgression:
    """Test message-based growth calculations."""

    @pytest.mark.integration
    def test_crop_growth_stage_exists(self, sample_client):
        """Crop growth stage field exists in status."""
        db.update_gold_coins(sample_client, 10, "test")
        db.plant_crop(sample_client, "parsnip", 0, 0)
        
        status = db.get_farm_status(sample_client)
        assert 'growthStage' in status['crops'][0]

    @pytest.mark.integration
    def test_animal_maturity_calculation(self, sample_client):
        """Animal maturity reflects message progress."""
        db.update_gold_coins(sample_client, 50, "test")
        db.buy_animal(sample_client, "chicken", 0, 0)
        
        for i in range(40):
            db.increment_message_counter(sample_client)
        
        result = db.harvest_animal(sample_client, 0, 40)
        assert result['success'] is True

    @pytest.mark.integration
    def test_different_crops_different_durations(self, sample_client):
        """Different crops have different growth durations."""
        db.update_gold_coins(sample_client, 30, "test")
        
        db.plant_crop(sample_client, "parsnip", 0, 0)
        db.plant_crop(sample_client, "corn", 1, 0)
        
        status = db.get_farm_status(sample_client)
        parsnip = [c for c in status['crops'] if c['cropType'] == 'parsnip'][0]
        corn = [c for c in status['crops'] if c['cropType'] == 'corn'][0]
        
        assert parsnip['growthDuration'] == 10
        assert corn['growthDuration'] == 30


@pytest.mark.integration
class TestFarmEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.integration
    def test_concurrent_plant_same_plot(self, sample_client):
        """Second plant on same plot fails."""
        db.update_gold_coins(sample_client, 20, "test")
        
        result1 = db.plant_crop(sample_client, "parsnip", 0, 0)
        result2 = db.plant_crop(sample_client, "potato", 0, 0)
        
        assert result1['success'] is True
        assert result2['success'] is False

    @pytest.mark.integration
    def test_harvest_twice_same_crop(self, sample_client):
        """Cannot harvest same crop twice."""
        db.update_gold_coins(sample_client, 10, "test")
        db.plant_crop(sample_client, "parsnip", 0, 0)
        
        db.harvest_crop(sample_client, 0, 10)
        result = db.harvest_crop(sample_client, 0, 15)
        
        assert result['success'] is False
        assert 'No crop' in result['error']

    @pytest.mark.integration
    def test_farm_state_consistency(self, sample_client):
        """Farm operations maintain state consistency."""
        db.update_gold_coins(sample_client, 100, "test")
        
        db.plant_crop(sample_client, "parsnip", 0, 0)
        db.plant_crop(sample_client, "potato", 1, 0)
        db.buy_animal(sample_client, "chicken", 0, 0)
        db.add_decoration(sample_client, "oak_tree", 5, 5, 0)
        
        status = db.get_farm_status(sample_client)
        
        assert len(status['crops']) == 2
        assert len(status['animals']) == 1
        assert len(status['decorations']) == 1
        
        expected_spent = 5 + 8 + 30 + 25
        assert status['gold'] == 100 - expected_spent
