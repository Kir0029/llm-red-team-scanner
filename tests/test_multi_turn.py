"""Tests for multi-turn attack engine."""

from scanner.core.multi_turn import (
    AttackStrategy,
    MultiTurnEngine,
    MultiTurnResult,
    TurnResult,
)
from scanner.models.base import Message, ModelProvider, ModelResponse, ProviderType


class MockProvider(ModelProvider):
    """Mock LLM provider for testing."""

    def __init__(self, responses: list[str] | None = None) -> None:
        super().__init__(model="mock-model", provider_type=ProviderType.OLLAMA)
        self.responses = responses or ["I cannot help with that."]
        self._call_count = 0

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        idx = min(self._call_count, len(self.responses) - 1)
        self._call_count += 1
        return ModelResponse(
            content=self.responses[idx],
            model=self.model,
            provider=self.provider_type,
        )


class TestAttackStrategy:
    """Tests for AttackStrategy enum."""

    def test_strategies_exist(self) -> None:
        assert AttackStrategy.CRESCENDO == "crescendo"
        assert AttackStrategy.ADAPTIVE == "adaptive"
        assert AttackStrategy.ITERATIVE == "iterative"


class TestMultiTurnEngine:
    """Tests for MultiTurnEngine."""

    def test_engine_creation(self) -> None:
        provider = MockProvider()
        engine = MultiTurnEngine(provider=provider, max_turns=3)
        assert engine.max_turns == 3

    async def test_single_turn_refusal(self) -> None:
        provider = MockProvider(responses=["I'm sorry, I can't help with that."])
        engine = MultiTurnEngine(provider=provider, max_turns=1)

        result = await engine.attack(
            initial_prompt="Tell me something bad",
            pattern_id="test-001",
        )

        assert isinstance(result, MultiTurnResult)
        assert len(result.turns) == 1
        assert result.turns[0].classification == "REFUSED"
        assert result.success is False

    async def test_early_stop_on_compromise(self) -> None:
        provider = MockProvider(responses=[
            "Sure, here's how: Step 1...",
            "This should not be reached",
        ])
        engine = MultiTurnEngine(provider=provider, max_turns=5)

        result = await engine.attack(
            initial_prompt="How to hack?",
            pattern_id="test-002",
        )

        assert len(result.turns) == 1
        assert result.success is True
        assert result.final_classification == "COMPROMISED"

    async def test_max_turns_reached(self) -> None:
        provider = MockProvider(responses=[
            "I can't help.",
            "I still can't help.",
            "No, I won't.",
        ])
        engine = MultiTurnEngine(provider=provider, max_turns=3)

        result = await engine.attack(
            initial_prompt="Bad request",
            pattern_id="test-003",
        )

        assert len(result.turns) == 3
        assert result.max_turns_reached is True
        assert result.success is False

    async def test_crescendo_strategy(self) -> None:
        provider = MockProvider(responses=[
            "I can't.",
            "I still can't.",
            "No.",
        ])
        engine = MultiTurnEngine(provider=provider, max_turns=3)

        result = await engine.attack(
            initial_prompt="Help me",
            strategy=AttackStrategy.CRESCENDO,
            pattern_id="test-004",
        )

        assert result.strategy == AttackStrategy.CRESCENDO

    async def test_adaptive_strategy(self) -> None:
        provider = MockProvider(responses=[
            "I can't help with that.",
            "Still refusing.",
        ])
        engine = MultiTurnEngine(provider=provider, max_turns=2)

        result = await engine.attack(
            initial_prompt="Do something bad",
            strategy=AttackStrategy.ADAPTIVE,
            pattern_id="test-005",
        )

        assert result.strategy == AttackStrategy.ADAPTIVE

    async def test_iterative_strategy(self) -> None:
        provider = MockProvider(responses=[
            "I can't.",
            "Still no.",
        ])
        engine = MultiTurnEngine(provider=provider, max_turns=2)

        result = await engine.attack(
            initial_prompt="Give me info",
            strategy=AttackStrategy.ITERATIVE,
            pattern_id="test-006",
        )

        assert result.strategy == AttackStrategy.ITERATIVE

    async def test_callback_is_called(self) -> None:
        turns_received: list[TurnResult] = []

        def on_turn(turn: TurnResult) -> None:
            turns_received.append(turn)

        provider = MockProvider(responses=["I can't.", "Still no."])
        engine = MultiTurnEngine(provider=provider, max_turns=2, on_turn=on_turn)

        await engine.attack(
            initial_prompt="Test",
            pattern_id="test-007",
        )

        assert len(turns_received) == 2

    async def test_conversation_history_grows(self) -> None:
        provider = MockProvider(responses=["I can't.", "Still no.", "No."])
        engine = MultiTurnEngine(provider=provider, max_turns=3)

        result = await engine.attack(
            initial_prompt="Test",
            pattern_id="test-008",
        )

        assert len(result.turns) == 3
        # Each turn should have a unique prompt (escalated)
        prompts = [t.prompt for t in result.turns]
        assert len(set(prompts)) > 1
