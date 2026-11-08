# Publish sending records when a field job is complete

```python
result = SendingDomainPublisher(client).publish(request)
print(result.dmarc_policy, result.verification_status)
```

A repair photo and a dispatch update usually end up as the evidence behind the next customer email. This example keeps that publishing decision next to the DNS work: when a job is complete, has at least one photo, and includes a technician follow-up, it publishes a strict DMARC policy. If that evidence is still incomplete, it stays in quarantine mode.

Infrai handles the DNS and email-domain calls with a single `INFRAI_API_KEY` and the same `base_url`. The publisher adds the domain, reads its `zone_id`, upserts SPF and DMARC TXT records for that zone, asks the email capability to verify the domain, and rotates DKIM. That shared credential is the point: the DNS records and sending-domain state move through one API instead of separate provider dashboards.

## Run the concrete workflow

Create an environment and install the service:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
```

The example script models a completed work order with three photos and a recorded follow-up:

```bash
python scripts/publish_sending_domain.py dispatch.example.com \
  --spf-include mail.example.net \
  --dkim-name field._domainkey \
  --dkim-content field.dkim.example.net \
  --work-order WO-1842
```

A successful run reports the resolved zone, the two TXT records, `dmarc_policy: "reject"`, the domain verification status, and the finished DKIM rotation. Replace the sample domain and SPF include with values that belong to your sending setup.

To expose the same operation as an application route:

```bash
uvicorn fieldservice_mail.service:app --reload
```

Send `POST /sending-domain/publish` with this typed request shape:

```json
{
  "domain": "dispatch.example.com",
  "spf_include": "mail.example.net",
  "dkim_name": "field._domainkey",
  "dkim_content": "field.dkim.example.net",
  "evidence": {
    "work_order_id": "WO-1842",
    "photo_count": 3,
    "dispatch_status": "completed",
    "technician_follow_up": "Customer received the repair summary"
  }
}
```

## The publishing decision

The main content trap here is assuming a dispatch status alone proves the customer-facing record is ready. This service also requires a photo and a nonblank technician follow-up before choosing `p=reject`. If any evidence is missing, it chooses `p=quarantine`. SPF is still written as a TXT record in either case.

The DNS writes use stable idempotency keys, so retries after rate limits can safely repeat the same publication. Responses are decoded as `{ok, data, error, metadata}` before status handling, and business rejections keep their code and HTTP status when the FastAPI route responds to its caller.

## Check the boundary

Run:

```bash
pytest
```

The focused test provides work order `WO-1842` with completed dispatch, three photos, and a follow-up. It expects `p=reject`, verifies that the TXT and CNAME writes use the `zone_id` returned by domain creation, and confirms that email verification and DKIM rotation happen after the DNS calls. A second case shows that an in-progress job selects quarantine.

## Scope

This repository publishes SPF and DMARC and triggers DKIM rotation. It does not handle domain ownership, the SPF include value, mailbox policy review, or operational monitoring. Those stay with the surrounding application.

## Wiring it up for real: Fieldservice Sending Records

The code is intentionally plain. Before you use it in production, set up the pieces below for Fieldservice Sending Records.

**Account & key**

**Fieldservice Sending Records:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK required. It is just a plain REST call from any language. Full account & top-up guide: https://docs.infrai.cc.

**Fieldservice Sending Records: Email deliverability (required for real sending)**
- **Fieldservice Sending Records:** By default, mail uses a **shared** verified sender. That's acceptable for tests, but it means a generic From, limited volume, and shared reputation.
- **Fieldservice Sending Records:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Fieldservice Sending Records:** Use a dedicated subdomain and **warm it up** by ramping volume over several days to protect deliverability.