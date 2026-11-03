import os

from fastapi import FastAPI, HTTPException

from .domain_publisher import SendingDomainPublisher
from .infrai_client import InfraiClient, InfraiError
from .models import PublicationResult, PublishSendingDomain

app = FastAPI(title="Field-service sending records")


@app.post("/sending-domain/publish", response_model=PublicationResult)
def publish_sending_domain(request: PublishSendingDomain) -> PublicationResult:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is required")

    client = InfraiClient(api_key)
    try:
        return SendingDomainPublisher(client).publish(request)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "details": exc.details},
        ) from exc
    finally:
        client.close()
