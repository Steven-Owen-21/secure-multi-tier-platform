"""SNS alert formatting for security findings.

Provides pure functions to format GuardDuty findings, AWS Config non-compliance
events, and WAF blocks into structured SecurityAlert messages suitable for
SNS publication.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SecurityAlert(BaseModel):
    """Structured security alert for SNS notification.

    Represents a formatted alert message published to the platform's SNS
    alerts topic when GuardDuty, Config, or WAF generates a finding.
    """

    source: Literal["guardduty", "config", "waf"]
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    finding_type: str = Field(min_length=1)
    affected_resource: str = Field(min_length=1)
    description: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)
    timestamp: datetime
    account_id: str = Field(pattern=r"^\d{12}$")
    region: str = Field(min_length=1)


# Recommended actions by severity level for GuardDuty findings.
GUARDDUTY_RECOMMENDED_ACTIONS: dict[str, str] = {
    "LOW": "Review finding and monitor for escalation. No immediate action required.",
    "MEDIUM": "Investigate the affected resource within 24 hours. Check for unusual activity.",
    "HIGH": "Investigate immediately. Isolate affected resource if compromise is suspected.",
    "CRITICAL": (
        "URGENT: Isolate affected resource immediately. "
        "Engage incident response team. Preserve evidence for forensic analysis."
    ),
}


def format_guardduty_alert(
    *,
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    finding_type: str,
    affected_resource: str,
    description: str,
    timestamp: datetime,
    account_id: str,
    region: str,
) -> SecurityAlert:
    """Format a GuardDuty finding into a structured SecurityAlert.

    Produces a valid SecurityAlert with the source set to "guardduty" and
    a recommended action derived from the severity level.

    Args:
        severity: Finding severity (LOW, MEDIUM, HIGH, CRITICAL).
        finding_type: GuardDuty finding type (e.g. "UnauthorizedAccess:EC2/SSHBruteForce").
        affected_resource: ARN or identifier of the affected resource.
        description: Human-readable description of the finding.
        timestamp: When the finding was generated.
        account_id: 12-digit AWS account ID.
        region: AWS region where the finding was detected.

    Returns:
        A validated SecurityAlert instance ready for SNS publication.
    """
    recommended_action = GUARDDUTY_RECOMMENDED_ACTIONS[severity]

    return SecurityAlert(
        source="guardduty",
        severity=severity,
        finding_type=finding_type,
        affected_resource=affected_resource,
        description=description,
        recommended_action=recommended_action,
        timestamp=timestamp,
        account_id=account_id,
        region=region,
    )
