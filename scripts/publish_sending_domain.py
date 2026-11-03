import argparse
import json
import os

from fieldservice_mail.domain_publisher import SendingDomainPublisher
from fieldservice_mail.infrai_client import InfraiClient
from fieldservice_mail.models import DispatchStatus, PublishSendingDomain, WorkOrderEvidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish field-service sending records")
    parser.add_argument("domain")
    parser.add_argument("--spf-include", required=True)
    parser.add_argument("--dkim-name", required=True)
    parser.add_argument("--dkim-content", required=True)
    parser.add_argument("--work-order", required=True)
    args = parser.parse_args()

    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before publishing")

    request = PublishSendingDomain(
        domain=args.domain,
        spf_include=args.spf_include,
        dkim_name=args.dkim_name,
        dkim_content=args.dkim_content,
        evidence=WorkOrderEvidence(
            work_order_id=args.work_order,
            photo_count=3,
            dispatch_status=DispatchStatus.COMPLETED,
            technician_follow_up="Completion note sent to the property manager",
        ),
    )
    client = InfraiClient(api_key)
    try:
        result = SendingDomainPublisher(client).publish(request)
        print(json.dumps(result.model_dump(), indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
