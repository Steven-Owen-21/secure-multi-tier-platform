"""Property-based tests for SNS alert formatting logic.

**Validates: Requirements 8.8**

Uses Hypothesis to verify that the SNS alert formatting logic produces valid
alert messages for all possible GuardDuty finding severity and type combinations.
"""

import json
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings, strategies as st

from app.services.alert_formatter import (
    GUARDDUTY_RECOMMENDED_ACTIONS,
    SecurityAlert,
    format_guardduty_alert,
)

# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------

VALID_SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Representative GuardDuty finding types covering all categories.
GUARDDUTY_FINDING_TYPES = [
    "UnauthorizedAccess:EC2/SSHBruteForce",
    "UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration",
    "Recon:EC2/PortProbeUnprotectedPort",
    "Recon:EC2/Portscan",
    "Trojan:EC2/BlackholeTraffic",
    "Trojan:EC2/DropPoint",
    "CryptoCurrency:EC2/BitcoinTool.B",
    "Backdoor:EC2/DenialOfService.Tcp",
    "Behavior:EC2/NetworkPortUnusual",
    "Behavior:EC2/TrafficVolumeUnusual",
    "Stealth:IAMUser/CloudTrailLoggingDisabled",
    "Discovery:S3/MaliciousIPCaller",
    "Exfiltration:S3/ObjectRead.Unusual",
    "Impact:EC2/WinRMBruteForce",
    "PenTest:IAMUser/KaliLinux",
    "Policy:IAMUser/RootCredentialUsage",
    "PrivilegeEscalation:IAMUser/AdministrativePermissions",
    "UnauthorizedAccess:S3/TorIPCaller",
]

VALID_REGIONS = [
    "eu-west-1",
    "eu-west-2",
    "us-east-1",
    "us-west-2",
    "ap-southeast-1",
]


@st.composite
def guardduty_finding(draw):
    """Generate a valid GuardDuty finding with arbitrary severity and type.

    Produces all valid combinations of severity (LOW, MEDIUM, HIGH, CRITICAL)
    and finding type strings.
    """
    severity = draw(st.sampled_from(VALID_SEVERITIES))
    finding_type = draw(st.sampled_from(GUARDDUTY_FINDING_TYPES))
    affected_resource = draw(
        st.from_regex(
            r"arn:aws:[a-z0-9]+:eu-west-2:\d{12}:[a-z\-]+/[a-z0-9\-]+",
            fullmatch=True,
        )
    )
    description = draw(st.text(min_size=1, max_size=500, alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        min_codepoint=32,
        max_codepoint=126,
    )))
    account_id = draw(st.from_regex(r"\d{12}", fullmatch=True))
    region = draw(st.sampled_from(VALID_REGIONS))
    timestamp = draw(st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
        timezones=st.just(timezone.utc),
    ))

    return {
        "severity": severity,
        "finding_type": finding_type,
        "affected_resource": affected_resource,
        "description": description,
        "account_id": account_id,
        "region": region,
        "timestamp": timestamp,
    }


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(finding=guardduty_finding())
def test_alert_formatting_produces_valid_security_alert(finding):
    """Property: format_guardduty_alert always produces a valid SecurityAlert.

    For any valid combination of GuardDuty finding severity and type,
    the formatting function must return a SecurityAlert that passes
    Pydantic validation with all required fields populated.

    **Validates: Requirements 8.8**
    """
    alert = format_guardduty_alert(**finding)

    # The result must be a valid SecurityAlert instance
    assert isinstance(alert, SecurityAlert)

    # All fields must be non-empty strings (except timestamp which is datetime)
    assert alert.source == "guardduty"
    assert alert.severity in VALID_SEVERITIES
    assert len(alert.finding_type) > 0
    assert len(alert.affected_resource) > 0
    assert len(alert.description) > 0
    assert len(alert.recommended_action) > 0
    assert isinstance(alert.timestamp, datetime)
    assert len(alert.account_id) == 12
    assert alert.account_id.isdigit()
    assert len(alert.region) > 0


@pytest.mark.property
@settings(max_examples=100)
@given(finding=guardduty_finding())
def test_alert_source_is_always_guardduty(finding):
    """Property: GuardDuty alerts always have source set to "guardduty".

    **Validates: Requirements 8.8**
    """
    alert = format_guardduty_alert(**finding)
    assert alert.source == "guardduty"


@pytest.mark.property
@settings(max_examples=100)
@given(finding=guardduty_finding())
def test_alert_severity_matches_input(finding):
    """Property: the alert severity always matches the input finding severity.

    **Validates: Requirements 8.8**
    """
    alert = format_guardduty_alert(**finding)
    assert alert.severity == finding["severity"]


@pytest.mark.property
@settings(max_examples=100)
@given(finding=guardduty_finding())
def test_alert_recommended_action_matches_severity(finding):
    """Property: recommended action is determined by severity level.

    Each severity maps to a specific recommended action from the lookup table.

    **Validates: Requirements 8.8**
    """
    alert = format_guardduty_alert(**finding)
    expected_action = GUARDDUTY_RECOMMENDED_ACTIONS[finding["severity"]]
    assert alert.recommended_action == expected_action


@pytest.mark.property
@settings(max_examples=100)
@given(finding=guardduty_finding())
def test_alert_is_json_serialisable(finding):
    """Property: SecurityAlert can always be serialised to valid JSON for SNS.

    SNS messages must be valid JSON strings. The alert must serialise without
    error for all valid inputs.

    **Validates: Requirements 8.8**
    """
    alert = format_guardduty_alert(**finding)

    # Pydantic model_dump with mode="json" produces JSON-serialisable dict
    alert_dict = alert.model_dump(mode="json")
    json_str = json.dumps(alert_dict)

    # Must produce non-empty JSON
    assert len(json_str) > 0

    # Must be parseable back
    parsed = json.loads(json_str)
    assert parsed["source"] == "guardduty"
    assert parsed["severity"] == finding["severity"]
    assert parsed["finding_type"] == finding["finding_type"]


@pytest.mark.property
@settings(max_examples=100)
@given(finding=guardduty_finding())
def test_alert_preserves_finding_type_and_resource(finding):
    """Property: finding type and affected resource are passed through unchanged.

    The formatter must not modify or truncate the finding type or resource.

    **Validates: Requirements 8.8**
    """
    alert = format_guardduty_alert(**finding)
    assert alert.finding_type == finding["finding_type"]
    assert alert.affected_resource == finding["affected_resource"]
