"""Judge engine for vulnerability detection."""

from scanner.judge.heuristic import HeuristicResult, heuristic_classify
from scanner.judge.llm_judge import LLMJudgeResult, llm_classify

__all__ = [
    "HeuristicResult",
    "heuristic_classify",
    "LLMJudgeResult",
    "llm_classify",
]
