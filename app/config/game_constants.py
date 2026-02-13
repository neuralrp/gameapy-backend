"""
Game constants for the Farm Minigame.
All values are designed for message-based growth (not real-time).
"""

# Crop definitions: growth_messages = how many messages to reach maturity
CROPS = {
    "parsnip": {
        "seed_cost": 5,
        "sell_price": 10,
        "growth_messages": 10,
        "stages": 5,  # Number of growth stage sprites (0-4)
    },
    "cauliflower": {
        "seed_cost": 8,
        "sell_price": 18,
        "growth_messages": 20,
        "stages": 6,
    },
    "potato": {
        "seed_cost": 8,
        "sell_price": 15,
        "growth_messages": 15,
        "stages": 6,
    },
    "corn": {
        "seed_cost": 12,
        "sell_price": 25,
        "growth_messages": 30,
        "stages": 4,
    },
    "tomato": {
        "seed_cost": 10,
        "sell_price": 20,
        "growth_messages": 25,
        "stages": 4,
    },
}

# Water bonus: 30% reduction in messages per watered stage
WATER_BONUS = 0.30

# Animal definitions
ANIMALS = {
    "chicken": {
        "cost": 30,
        "sell_price": 50,
        "maturity_messages": 40,
    },
    "horse": {
        "cost": 60,
        "sell_price": 100,
        "maturity_messages": 50,
    },
    "cow": {
        "cost": 100,
        "sell_price": 160,
        "maturity_messages": 80,
    },
}

# Decoration definitions
DECORATIONS = {
    "oak_tree": {
        "cost": 25,
        "name": "Oak Tree",
    },
    "pine_tree": {
        "cost": 30,
        "name": "Pine Tree",
    },
    "flower_bed": {
        "cost": 15,
        "name": "Flower Bed",
    },
    "mushroom": {
        "cost": 20,
        "name": "Mushroom Cluster",
    },
    "fence": {
        "cost": 10,
        "name": "Fence Section",
    },
    "lamp": {
        "cost": 20,
        "name": "Lamp Post",
    },
    "bench": {
        "cost": 15,
        "name": "Bench",
    },
}

# Farm level progression
FARM_LEVELS = {
    1: {"plots": 4, "barn_slots": 1, "unlocks": ["chicken"]},
    2: {"plots": 6, "barn_slots": 2, "unlocks": []},
    3: {"plots": 8, "barn_slots": 3, "unlocks": ["cow"]},
    4: {"plots": 10, "barn_slots": 3, "unlocks": ["pond", "horse"]},
    5: {"plots": 12, "barn_slots": 4, "unlocks": ["trees"]},
    6: {"plots": 14, "barn_slots": 5, "unlocks": ["decorations"]},
    7: {"plots": 16, "barn_slots": 6, "unlocks": ["max"]},
}

# Upgrade costs (by level)
UPGRADE_COSTS = {
    1: 75,   # To level 2
    2: 125,  # To level 3
    3: 175,  # To level 4
    4: 250,  # To level 5
    5: 350,  # To level 6
    6: 450,  # To level 7
}

# Starting state
STARTING_GOLD = 15  # 10 for first card + 5 for login
MAX_PLOTS = 16
MAX_BARN_SLOTS = 6

# Marina milestone for mermaid
MARINA_MERMAID_UNLOCK_MESSAGES = 100
