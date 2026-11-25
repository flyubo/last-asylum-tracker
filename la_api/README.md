# LA Tracker API Core

This is an isolated API-platform module. The existing server-139 ranking tracker remains unchanged.

## Included
- `protocol.py`: JuFeng frame encoder/decoder, independent directional counters, checksum validation, gzip handling and message-name framing.
- `catalog.py`: builds a searchable JSON index from recovered .proto schemas and the 2,050-name message list.
- `index.html`: browser API explorer.
- `api_catalog.json`: small, verified starter subset (4 core messages) so the explorer can load immediately.
- `tests/test_protocol.py`: codec tests for chunked TCP input, gzip, counter wrap and checksum rejection.
- `PCAP_VALIDATION.md`: redacted validation summary from the supplied PCAP.

## Build the full catalogue
Place the recovered analysis bundle in a local, untracked `analysis/` folder, then run:

```bash
python -m la_api.catalog --proto-dir analysis/proto --messages analysis/api_messages_all.txt --output la_api/api_catalog.json
```

The supplied analysis bundle generates **3,170 catalogue entries**, including **2,822 messages with matching protobuf schemas**. The starter JSON currently contains only four core messages; replace it with the generated full catalogue when the analysis bundle is staged locally.

## Authentication boundary
The transport codec does not generate SDK signatures, account tokens, or device credentials. Session establishment should use a fresh, legitimate session from the user's own running game client or an officially supported authentication flow. The PCAP note confirms that a completed login and reconnect-token response were captured, but the old token may have expired.

Never commit credentials, tokens, PCAPs, or device identifiers to Git. Keep any local session bridge and credential store outside the public web root and repository.
