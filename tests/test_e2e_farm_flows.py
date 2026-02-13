"""
E2E Farm Flow Tests.

Tests complete farming cycles from start to finish.
"""
import pytest
from app.db.database import db


@pytest.mark.e2e
class TestCompleteFarmingCycle:
    """Test complete farming cycle."""

    @pytest.mark.e2e
    def test_complete_crop_cycle(self, sample_client):
        """Full cycle: till → plant → water → grow → harvest."""
        db.update_gold_coins(sample_client, 20, "test")
        initial_gold = db.get_farm_status(sample_client)['gold']
        
        till_result = db.till_plot(sample_client, 0)
        assert till_result['success'] is True
        
        plant_result = db.plant_crop(sample_client, "parsnip", 0, 0)
        assert plant_result['success'] is True
        assert plant_result['goldSpent'] == 5
        
        db.water_crop(sample_client, 0, 0)
        db.water_crop(sample_client, 0, 1)
        
        for _ in range(10):
            db.increment_message_counter(sample_client)
        
        harvest_result = db.harvest_crop(sample_client, 0, 10)
        assert harvest_result['success'] is True
        assert harvest_result['goldEarned'] == 10
        
        final_gold = db.get_farm_status(sample_client)['gold']
        assert final_gold > initial_gold - 5

    @pytest.mark.e2e
    def test_farm_upgrade_progression(self, sample_client):
        """Progress from level 1 to level 3 with unlocks."""
        db.update_gold_coins(sample_client, 500, "test")
        
        result = db.upgrade_farm_level(sample_client)
        assert result['success'] is True
        assert result['newLevel'] == 2
        
        result = db.upgrade_farm_level(sample_client)
        assert result['success'] is True
        assert 'cow' in result['unlocks']
        
        shop = db.get_farm_shop(sample_client)
        animal_ids = [a['id'] for a in shop['animals']]
        assert 'cow' in animal_ids

    @pytest.mark.e2e
    def test_animal_raising_flow(self, sample_client):
        """Full animal cycle: buy → grow → sell."""
        db.update_gold_coins(sample_client, 100, "test")
        
        buy_result = db.buy_animal(sample_client, "chicken", 0, 0)
        assert buy_result['success'] is True
        assert buy_result['goldSpent'] == 30
        
        for _ in range(40):
            db.increment_message_counter(sample_client)
        
        sell_result = db.harvest_animal(sample_client, 0, 40)
        assert sell_result['success'] is True
        assert sell_result['goldEarned'] == 50
        assert sell_result['newGold'] == 120
