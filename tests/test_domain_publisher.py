from fieldservice_mail.domain_publisher import SendingDomainPublisher, choose_dmarc_policy
from fieldservice_mail.models import DispatchStatus, PublishSendingDomain, WorkOrderEvidence


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, path: str, **kwargs: object) -> object:
        self.calls.append((method, path, kwargs))
        if path == "/v1/dns/domain/add":
            return {"zone_id": "zone_field_ops"}
        if path == "/v1/email/domain/verify":
            return {"verification": {"status": "verified"}}
        return {}


def request_for(status: DispatchStatus, photos: int, follow_up: str | None) -> PublishSendingDomain:
    return PublishSendingDomain(
        domain="dispatch.example.com",
        spf_include="mail.example.net",
        dkim_name="field._domainkey",
        dkim_content="field.dkim.example.net",
        evidence=WorkOrderEvidence(
            work_order_id="WO-1842",
            photo_count=photos,
            dispatch_status=status,
            technician_follow_up=follow_up,
        ),
    )


def test_completed_evidence_publishes_reject_policy_and_crosses_both_groups() -> None:
    client = RecordingClient()
    result = SendingDomainPublisher(client).publish(
        request_for(DispatchStatus.COMPLETED, 3, "Customer received the repair summary")
    )

    assert result.dmarc_policy == "reject"
    assert result.verification_status == "verified"
    assert [(method, path) for method, path, _ in client.calls] == [
        ("POST", "/v1/dns/domain/add"),
        ("PUT", "/v1/dns/record/upsert"),
        ("PUT", "/v1/dns/record/upsert"),
        ("PUT", "/v1/dns/record/upsert"),
        ("POST", "/v1/email/domain/verify"),
        ("POST", "/v1/email/domain/rotate_dkim/dispatch.example.com"),
    ]
    dmarc_call = client.calls[2][2]
    assert dmarc_call["json"]["zone_id"] == "zone_field_ops"  # type: ignore[index]
    assert "p=reject" in dmarc_call["json"]["content"]  # type: ignore[index]
    dkim_call = client.calls[3][2]
    assert dkim_call["json"]["record_type"] == "CNAME"  # type: ignore[index]
    assert dkim_call["json"]["zone_id"] == "zone_field_ops"  # type: ignore[index]


def test_incomplete_job_keeps_quarantine_policy() -> None:
    request = request_for(DispatchStatus.IN_PROGRESS, 1, None)
    assert choose_dmarc_policy(request) == "quarantine"
