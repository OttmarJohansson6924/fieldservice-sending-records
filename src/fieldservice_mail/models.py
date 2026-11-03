import re
from dataclasses import dataclass
from enum import StrEnum


class DispatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class WorkOrderEvidence:
    work_order_id: str
    photo_count: int
    dispatch_status: DispatchStatus
    technician_follow_up: str | None = None

    def __post_init__(self) -> None:
        if not self.work_order_id:
            raise ValueError("work_order_id must not be empty")
        if self.photo_count < 0:
            raise ValueError("photo_count must be non-negative")


@dataclass
class PublishSendingDomain:
    domain: str
    spf_include: str
    dkim_name: str
    dkim_content: str
    evidence: WorkOrderEvidence

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", self.domain):
            raise ValueError("domain has an invalid format")
        for name in ("spf_include", "dkim_name", "dkim_content"):
            if not getattr(self, name):
                raise ValueError(f"{name} must not be empty")


@dataclass
class PublishedRecord:
    record_type: str
    name: str
    content: str


@dataclass
class PublicationResult:
    domain: str
    zone_id: str
    dmarc_policy: str
    records: list[PublishedRecord]
    verification_status: str
    dkim_rotated: bool
