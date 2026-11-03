from typing import Any

from .models import DispatchStatus, PublicationResult, PublishedRecord, PublishSendingDomain


def choose_dmarc_policy(request: PublishSendingDomain) -> str:
    evidence = request.evidence
    ready = (
        evidence.photo_count > 0
        and evidence.dispatch_status is DispatchStatus.COMPLETED
        and bool(evidence.technician_follow_up and evidence.technician_follow_up.strip())
    )
    return "reject" if ready else "quarantine"


class SendingDomainPublisher:
    def __init__(self, client: Any) -> None:
        self._client = client

    def publish(self, request: PublishSendingDomain) -> PublicationResult:
        domain_data = self._client.request(
            "POST",
            "/v1/dns/domain/add",
            json={"domain": request.domain, "metadata": {"use_case": "field_service_mail"}},
            idempotency_key=f"domain:{request.domain}",
        )
        zone_id = self._zone_id(domain_data)
        policy = choose_dmarc_policy(request)
        records = [
            PublishedRecord(
                record_type="TXT",
                name="@",
                content=f"v=spf1 include:{request.spf_include} -all",
            ),
            PublishedRecord(
                record_type="TXT",
                name="_dmarc",
                content=f"v=DMARC1; p={policy}; rua=mailto:dmarc@{request.domain}",
            ),
            PublishedRecord(
                record_type="CNAME",
                name=request.dkim_name,
                content=request.dkim_content,
            ),
        ]
        for record in records:
            payload = {
                "zone_id": zone_id,
                "record_type": record.record_type,
                "name": record.name,
                "content": record.content,
                "ttl": 300,
                "metadata": {"work_order_id": request.evidence.work_order_id},
            }
            self._client.request(
                "PUT",
                "/v1/dns/record/upsert",
                json=payload,
                idempotency_key=f"record:{zone_id}:{record.name}:{record.content}",
            )

        verification = self._client.request(
            "POST",
            "/v1/email/domain/verify",
            json={"domain": request.domain},
            idempotency_key=f"verify:{request.domain}",
        )
        self._client.request(
            "POST",
            f"/v1/email/domain/rotate_dkim/{request.domain}",
            idempotency_key=f"dkim:{request.domain}:{request.evidence.work_order_id}",
        )
        return PublicationResult(
            domain=request.domain,
            zone_id=zone_id,
            dmarc_policy=policy,
            records=records,
            verification_status=str(verification["verification"]["status"]),
            dkim_rotated=True,
        )

    @staticmethod
    def _zone_id(domain_data: Any) -> str:
        if not isinstance(domain_data, dict) or not domain_data.get("zone_id"):
            raise RuntimeError("Domain response did not contain zone_id")
        return str(domain_data["zone_id"])
