"""Property-based tests for composite alarm evaluation logic.

**Validates: Requirements 22.1, 22.7**

Uses Hypothesis to verify that the composite alarm evaluation correctly
determines the composite alarm state for all valid combinations of child
alarm states (OK, ALARM, INSUFFICIENT_DATA).

The composite alarm rule mirrors Terraform:
    ALARM(alb_5xx) AND ALARM(ecs_cpu) AND ALARM(db_connections)

Result is ALARM if and only if all three children are simultaneously ALARM.
"""

import pytest
from hypothesis import given, settings, strategies as st

from infrastructure.logic.composite_alarm import (
    AlarmState,
    evaluate_composite_alarm,
    VALID_ALARM_STATES,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy that produces any valid alarm state
alarm_state_strategy = st.sampled_from(["OK", "ALARM", "INSUFFICIENT_DATA"])


# ---------------------------------------------------------------------------
# Property 5: Composite alarm evaluates to ALARM only when all children are in ALARM
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(
    alb_5xx_state=alarm_state_strategy,
    ecs_cpu_state=alarm_state_strategy,
    db_connections_state=alarm_state_strategy,
)
def test_composite_alarm_is_alarm_iff_all_children_alarm(
    alb_5xx_state: str,
    ecs_cpu_state: str,
    db_connections_state: str,
):
    """Property 5: Composite alarm evaluates to ALARM only when all children are in ALARM.

    For any combination of three child alarm states (each being OK, ALARM, or
    INSUFFICIENT_DATA), the composite alarm evaluation SHALL produce ALARM if
    and only if all three children are simultaneously in ALARM state.

    **Validates: Requirements 22.1, 22.7**
    """
    result = evaluate_composite_alarm(
        alb_5xx_state=alb_5xx_state,
        ecs_cpu_state=ecs_cpu_state,
        db_connections_state=db_connections_state,
    )

    all_alarm = (
        alb_5xx_state == "ALARM"
        and ecs_cpu_state == "ALARM"
        and db_connections_state == "ALARM"
    )

    if all_alarm:
        assert result == "ALARM", (
            f"Composite alarm should be ALARM when all children are ALARM, "
            f"but got '{result}'"
        )
    else:
        assert result != "ALARM", (
            f"Composite alarm should NOT be ALARM when children are "
            f"({alb_5xx_state}, {ecs_cpu_state}, {db_connections_state}), "
            f"but got '{result}'"
        )


@pytest.mark.property
@settings(max_examples=100)
@given(
    alb_5xx_state=alarm_state_strategy,
    ecs_cpu_state=alarm_state_strategy,
    db_connections_state=alarm_state_strategy,
)
def test_composite_alarm_returns_valid_state(
    alb_5xx_state: str,
    ecs_cpu_state: str,
    db_connections_state: str,
):
    """Property: Composite alarm always returns a valid alarm state.

    **Validates: Requirements 22.1, 22.7**
    """
    result = evaluate_composite_alarm(
        alb_5xx_state=alb_5xx_state,
        ecs_cpu_state=ecs_cpu_state,
        db_connections_state=db_connections_state,
    )

    assert result in VALID_ALARM_STATES, (
        f"Composite alarm returned invalid state '{result}', "
        f"expected one of {sorted(VALID_ALARM_STATES)}"
    )
