# Phase 7 Test Fixes - Complete

**Date**: 2026-02-08
**Status**: ✅ All 89 tests passing (100%)
**Coverage**: 68% (was 66%)

---

## Summary

Fixed all 7 failing tests by eliminating global state issues in the LLM client and improving test isolation.

## Root Causes Identified

### 1. Global httpx.AsyncClient Caching
**Problem**: `simple_llm_client` stored a persistent `httpx.AsyncClient` instance. When tests closed the client, subsequent tests received a closed client, causing "Event loop is closed" and "Cannot send a request, as client has been closed" errors.

**Solution**: Changed to per-request client creation. Each `chat_completion()` call creates a fresh `httpx.AsyncClient`, uses it, and closes it immediately. No global state is maintained.

### 2. Module Import Caching
**Problem**: Multiple modules (`card_generator.py`, `card_updater.py`, `guide_system.py`) import `simple_llm_client` at module load time. When monkeypatch fixtures replaced the global instance in `simple_llm_fixed.py`, these modules still held references to the original instance.

**Solution**: Added `guide_system` to all mock fixtures, ensuring all import paths are patched:
- `app.services.simple_llm_fixed.simple_llm_client` (source)
- `app.api.chat.simple_llm_client`
- `app.api.guide.simple_llm_client`
- `app.api.session_analyzer.simple_llm_client`
- `app.services.card_generator.simple_llm_client`
- `app.services.card_updater.simple_llm_client`
- `app.services.guide_system.simple_llm_client`

### 3. Test Expectation Mismatch
**Problem**: `test_conversation_continues_naturally_when_no_card_needed` expected `result['suggested_card']` to be `None` for "I'm just feeling a bit anxious today", but the real LLM (or unmocked client) returned a card suggestion.

**Solution**: Created new `mock_llm_no_card` fixture that returns a "no card" response (`card_type: null, topic: null, confidence: 0.0`), allowing the test to verify guide system's "no card" code path.

---

## Changes Made

### File: `backend/app/services/simple_llm_fixed.py`

```python
# Before: Cached client
class SimpleLLMClient:
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(timeout=settings.timeout)
        return self._client

# After: Per-request client
class SimpleLLMClient:
    def _get_client(self):
        import httpx
        return httpx.AsyncClient(timeout=settings.timeout)
    
    async def chat_completion(...):
        client = self._get_client()
        try:
            response = await client.post(...)
            return response.json()
        finally:
            await client.aclose()  # Always close after request
```

### File: `backend/tests/conftest.py`

**Added fixture**:
```python
@pytest.fixture
def mock_llm_no_card(monkeypatch):
    """
    Mock SimpleLLMClient to return "no card" responses.
    
    Use this for tests that expect no card to be suggested.
    """
    class MockNoCardClient:
        async def chat_completion(...):
            return {
                "choices": [{
                    "message": {
                        "content": '{"card_type": null, "topic": null, "confidence": 0.0}'
                    }
                }]
            }
    
    # Monkeypatch all import paths including guide_system
    # ... (same pattern as other mocks)
```

**Updated all mock fixtures** (`mock_llm_success`, `mock_llm_error`, `mock_llm_fallback`):
- Added `import app.services.guide_system as guide_system_module`
- Added `monkeypatch.setattr(guide_system_module, 'simple_llm_client', mock_instance, raising=False)`

**Updated test** (`test_guide_system.py`):
```python
# Before
async def test_conversation_continues_naturally_when_no_card_needed(
    self, sample_client, sample_guide_counselor, mock_card_generator_success
):
    # ...

# After
async def test_conversation_continues_naturally_when_no_card_needed(
    self, sample_client, sample_guide_counselor, mock_llm_no_card
):
    # ...
```

---

## Test Results

### Before Fixes
```
FAILED tests/test_api_cards.py::TestCardsGenerateSave::test_generate_from_text_success_character
FAILED tests/test_api_guide.py::TestGuideConversationFlow::test_confirm_card_creation_success
FAILED tests/test_api_guide.py::TestGuideCardSuggestion::test_card_creation_from_suggestion
FAILED tests/test_api_session_analyzer.py::TestSessionAnalyzer::test_analyze_session_llm_error
FAILED tests/test_e2e_flows.py::TestE2EOnboarding::test_complete_onboarding_flow
FAILED tests/test_e2e_flows.py::TestE2EWorldEventCreation::test_world_event_creation_and_context_loading
FAILED tests/test_llm.py::test_chat_with_counselor

7 failed, 82 passed (92.1% pass rate)
```

### After Fixes
```
============================= 89 passed in 33.48s =============================

89 passed (100% pass rate)
```

---

## Key Benefits

1. **Deterministic Tests**: Tests now pass regardless of run order
2. **No State Pollution**: Mock fixtures properly clean up after themselves via monkeypatch restoration
3. **Better Error Handling**: No more "Event loop is closed" or "client is closed" errors
4. **Proper Isolation**: Each test gets fresh LLM client per request
5. **Complete Mock Coverage**: All import paths for `simple_llm_client` are patched

---

## Lessons Learned

1. **Per-request HTTP clients are safer in tests** than cached clients with explicit lifecycle management
2. **Module import caching is a common source of mock failures** - always trace import paths
3. **Test fixtures should use autouse cautiously** - they can mask issues if they're too broad
4. **Monkeypatch is the right tool** for replacing global state in tests

---

## Remaining Work

None - all 89 tests pass and infrastructure is complete.

---

## Next Steps (Optional)

1. **Coverage**: Increase from 68% to 75% (test infrastructure goal)
2. **Real LLM Tests**: Consider marking `test_llm.py` tests as `@pytest.mark.llm` since they require actual API key
3. **Parallel Testing**: Consider running tests with `-n auto` flag once coverage is stable (pytest-xdist)
