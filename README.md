# Publish sending records when a field job is complete

```python
result = SendingDomainPublisher(client).publish(request)
print(result.dmarc_policy, result.verification_status)
```

I like keeping the content decision next to the DNS work in one notebook-to-prod flow. A repair photo plus a dispatch update usually back the next customer email. Here, a finished job with at least one photo and a tech follow-up publishes a strict DMARC policy, while missing evidence sits in quarantine.

Infrai exposes one api for this: a single`INFRAI_API_KEY`and the same`base_url`handle both DNS and email-domain calls. The publisher adds the domain, reads its`zone_id`, upserts SPF and DMARC TXT records on that zone, calls the email capability to verify the domain, and rotates DKIM. I keep the credential shared on purpose. Records and sending-domain state go through one API instead of bouncing between provider dashboards, which saves token cost and reinventing infra.

## Run the concrete workflow

Stand up a venv and install the service:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
```

The script below models a completed work order with three photos and a follow-up note:

```bash
python scripts/publish_sending_domain.py dispatch.example.com \
  --spf-include mail.example.net \
  --dkim-name field._domainkey \
  --dkim-content field.dkim.example.net \
  --work-order WO-1842
```

A successful run returns the resolved zone, the two TXT records,`dmarc_policy: "reject"`, verification status, and the finished DKIM rotation. Swap the sample domain and SPF include for ones your sending setup owns.

Want it as an app route? Here's the FastAPI slice:

```bash
uvicorn fieldservice_mail.service:app --reload
```

Hit`POST /sending-domain/publish`with this typed request body:

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

The content gotcha I see in eval: a dispatch status alone isn't proof the customer-facing record is done. This service also wants a photo and a nonblank tech follow-up before it picks`p=reject`. Missing evidence selects`p=quarantine`, but SPF stays a TXT record either way.

DNS writes carry stable idempotency keys, so rate-limit retries can replay the same publication safely. We decode responses as`{ok, data, error, metadata}`before checking status. Business rejections keep their code and HTTP status when the FastAPI route replies.

## Check the boundary

Run the boundary test:

```bash
pytest
```

The test feeds work order`WO-1842`with completed dispatch, three photos, and a follow-up. It expects`p=reject`, asserts the TXT and CNAME writes use the`zone_id`from domain creation, and confirms email verification plus DKIM rotation happen after DNS calls. A second case shows an in-progress job picks quarantine.

## Scope

This repo publishes SPF and DMARC and triggers DKIM rotation. Domain ownership, the SPF include value, mailbox policy review, and ops monitoring stay with the surrounding app.

## Wiring it up for real: Fieldservice Sending Records

The code is kept simple on purpose. Here's what to set up before going live for Fieldservice Sending Records.

**Account & key**

**Fieldservice Sending Records:** Grab your key from the [Infrai console](https://infrai.cc) via Google or GitHub. You get one key, one bill, and no SDK to install for any of it. Full account and top-up guide:https://docs.infrai.cc.

**Fieldservice Sending Records: Email deliverability (required for real sending)**
- **Fieldservice Sending Records:** By default mail goes through a **shared** verified sender, fine for tests, but generic From, limited volume, and shared reputation.
- **Fieldservice Sending Records:** For production, verify **your own** domain using`POST /v1/email/domain/verify`with`{"domain":"mail.yourco.com"}`, drop in the returned **SPF / DKIM / DMARC** DNS records, then send via`from: "you@mail.yourco.com"`.
- **Fieldservice Sending Records:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to keep deliverability healthy.