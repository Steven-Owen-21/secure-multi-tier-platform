"""Composite alarm evaluation logic.

Mirrors the Terraform CloudWatch composite alarm in
infrastructure/modules/observability/main.tf.

The composite alarm rule is:
    ALARM(alb_5xx) AND ALARM(ecs_cpu) AND ALARM(db_connections)

The composite alarm evaluates to ALARM if and only if all three child
alarms are simultaneously in ALARM state. Any other combination of child
states (OK, ALARM, INSUFFICIENT_DATA) results in a non-ALARM state.

Valid child alarm states:
    - "OK": The metric is within the acceptable threshold.
    - "ALARM": The metric has breached the threshold.
    - "INSUFFICIENT_DATA": Not enough data to evaluate.
"""

from typing import Literal

# Valid alarm states as defined by CloudWatch
AlarmState = Literal["OK", "ALARM", "INSUFFICIENT_DATA"]

VALID_ALARM_STATES: frozenset[str] = frozenset({"OK", "ALARM", "INSUFFICIENT_DATA"})


def evaluate_composite_alarm(
    alb_5xx_state: AlarmState,
    ecs_cpu_state: AlarmState,
    db_connections_state: AlarmState,
) -> AlarmState:
    """Evaluate the composite alarm state from three child alarm states.

    This mirrors the Terraform composite alarm logic:
        alarm_rule = "ALARM(alb_5xx) AND ALARM(ecs_cpu) AND ALARM(db_connections)"

    The composite alarm transitions to ALARM only when ALL three children
    are simultaneously in ALARM state. Otherwise it returns OK.

    Args:
        alb_5xx_state: State of the ALB 5xx error rate alarm.
        ecs_cpu_state: State of the ECS CPU utilisation alarm.
        db_connections_state: State of the DB connections alarm.

    Returns:
        "ALARM" if all three children are in ALARM state, "OK" otherwise.

    Raises:
        ValueError: If any child state is not a valid alarm state.
    """
    # Validate inputs
    for name, state in [
        ("alb_5xx_state", alb_5xx_state),
        ("ecs_cpu_state", ecs_cpu_state),
        ("db_connections_state", db_connections_state),
    ]:
        if state not in VALID_ALARM_STATES:
            raise ValueError(
                f"{name} must be one of {sorted(VALID_ALARM_STATES)}, got '{state}'"
            )

    # Composite alarm rule: ALL children must be ALARM
    if (
        alb_5xx_state == "ALARM"
        and ecs_cpu_state == "ALARM"
        and db_connections_state == "ALARM"
    ):
        return "ALARM"

    return "OK"
