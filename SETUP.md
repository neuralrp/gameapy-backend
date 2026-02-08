# Gameapy Backend Setup

## Environment Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Add your OpenRouter API key:
```
OPENROUTER_API_KEY=your_api_key_here
```

## Running the Backend

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start the server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

## Testing OpenRouter Integration

1. Run the test script:
```bash
python test_openrouter.py
```

## API Endpoints

### Core API (`/api/v1`)
- `/health` - Health check
- `/clients` - Client profile CRUD
- `/counselors` - Counselor profile CRUD  
- `/sessions` - Session management
- `/messages` - Message management
- `/character-cards` - Character card system
- `/game-state` - Game progress
- `/farm-items` - Farm minigame

### Chat API (`/api/v1/chat`)
- `/chat` - Send message and get AI response
- `/chat/stream` - Streaming chat responses
- `/insights/extract` - Extract insights from sessions
- `/models` - Available LLM models
- `/models/{model_id}` - Model information

## OpenRouter Integration Features

- **Multiple model support**: Claude, GPT, Llama, etc.
- **Automatic fallback**: If primary model fails, uses fallback
- **Safety parameters**: Configurable temperature, max tokens, timeout
- **Retry logic**: Handles API failures gracefully
- **Insight extraction**: Analyzes sessions for clinical insights
- **Character-based responses**: Counselor personas (coach, wise old man, etc.)

## Counselor Personas

The system supports creative counselor personas:
- **Baseball Coach**: Sports metaphors, tough love
- **Wise Old Man**: Wisdom, life experience
- **Mermaid**: Ocean imagery, emotional depth
- **Zeus**: Power, authority, mythology

Each persona has:
- Unique system prompts
- Specialized therapeutic approach
- Custom response patterns
- Themed language and metaphors