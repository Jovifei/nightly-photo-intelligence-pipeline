"""Asset state machine and transition guards.

The state set and allowed transitions mirror config/state_machine.yaml and
docs/09_data_model_and_state_machine.md. Transition history is append-only;
this module only validates a single from->to step.
"""

from __future__ import annotations

from enum import Enum

from .errors import NPI_SCHEMA_INVALID, NpiError


class AssetState(str, Enum):
    """Minimal asset state set (config/state_machine.yaml)."""

    NEW = "NEW"
    INGESTED = "INGESTED"
    DUPLICATE = "DUPLICATE"
    UNSUPPORTED = "UNSUPPORTED"
    POSE_DONE = "POSE_DONE"
    SEGMENT_DONE = "SEGMENT_DONE"
    FACTS_DONE = "FACTS_DONE"
    INTERPRETATION_DONE = "INTERPRETATION_DONE"
    PROMPTS_DONE = "PROMPTS_DONE"
    VALIDATED = "VALIDATED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"
    EXPORTED = "EXPORTED"
    RETRY = "RETRY"
    FAILED = "FAILED"


# Allowed transitions (config/state_machine.yaml transitions block).
ALLOWED_TRANSITIONS: dict[AssetState, frozenset[AssetState]] = {
    AssetState.NEW: frozenset(
        {AssetState.INGESTED, AssetState.DUPLICATE, AssetState.UNSUPPORTED, AssetState.FAILED}
    ),
    AssetState.INGESTED: frozenset(
        {AssetState.POSE_DONE, AssetState.NEEDS_REVIEW, AssetState.RETRY, AssetState.FAILED}
    ),
    AssetState.POSE_DONE: frozenset(
        {AssetState.SEGMENT_DONE, AssetState.NEEDS_REVIEW, AssetState.RETRY, AssetState.FAILED}
    ),
    AssetState.SEGMENT_DONE: frozenset(
        {AssetState.FACTS_DONE, AssetState.NEEDS_REVIEW, AssetState.RETRY, AssetState.FAILED}
    ),
    AssetState.FACTS_DONE: frozenset(
        {
            AssetState.INTERPRETATION_DONE,
            AssetState.NEEDS_REVIEW,
            AssetState.RETRY,
            AssetState.FAILED,
        }
    ),
    AssetState.INTERPRETATION_DONE: frozenset(
        {AssetState.PROMPTS_DONE, AssetState.NEEDS_REVIEW, AssetState.RETRY, AssetState.FAILED}
    ),
    AssetState.PROMPTS_DONE: frozenset(
        {AssetState.VALIDATED, AssetState.NEEDS_REVIEW, AssetState.RETRY, AssetState.FAILED}
    ),
    AssetState.VALIDATED: frozenset({AssetState.NEEDS_REVIEW, AssetState.APPROVED}),
    AssetState.NEEDS_REVIEW: frozenset(
        {
            AssetState.APPROVED,
            AssetState.FAILED,
            AssetState.INGESTED,
            AssetState.POSE_DONE,
            AssetState.SEGMENT_DONE,
            AssetState.FACTS_DONE,
            AssetState.INTERPRETATION_DONE,
            AssetState.PROMPTS_DONE,
        }
    ),
    AssetState.APPROVED: frozenset({AssetState.EXPORTED}),
    AssetState.RETRY: frozenset(
        {
            AssetState.INGESTED,
            AssetState.POSE_DONE,
            AssetState.SEGMENT_DONE,
            AssetState.FACTS_DONE,
            AssetState.INTERPRETATION_DONE,
            AssetState.PROMPTS_DONE,
            AssetState.FAILED,
        }
    ),
    AssetState.DUPLICATE: frozenset(),
    AssetState.UNSUPPORTED: frozenset(),
    AssetState.EXPORTED: frozenset(),
    AssetState.FAILED: frozenset(),
}


# Terminal states have no outgoing transitions.
TERMINAL_STATES: frozenset[AssetState] = frozenset(
    {AssetState.DUPLICATE, AssetState.UNSUPPORTED, AssetState.EXPORTED, AssetState.FAILED}
)


class InvalidTransitionError(NpiError):
    error_code = NPI_SCHEMA_INVALID

    def __init__(self, from_state: AssetState, to_state: AssetState) -> None:
        super().__init__(
            f"invalid state transition: {from_state.value} -> {to_state.value}",
        )
        self.from_state = from_state
        self.to_state = to_state


def is_valid_transition(from_state: AssetState, to_state: AssetState) -> bool:
    """Return True if from_state -> to_state is permitted by the state machine."""
    return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())


def validate_transition(from_state: AssetState, to_state: AssetState) -> None:
    """Raise InvalidTransitionError if the transition is not allowed."""
    if not is_valid_transition(from_state, to_state):
        raise InvalidTransitionError(from_state, to_state)


def parse_state(value: str) -> AssetState:
    """Parse a state string, raising InvalidTransitionError-ish on unknown values."""
    try:
        return AssetState(value)
    except ValueError as exc:
        raise NpiError(
            f"unknown asset state: {value!r}",
            error_code=NPI_SCHEMA_INVALID,
        ) from exc
