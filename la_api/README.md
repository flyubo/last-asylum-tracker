# LA Tracker API Core

This is a new, isolated API-platform module. It does not replace or modify the existing server-139 ranking tracker.

## Included
- `protocol.py`: JuFeng frame encoder/decoder, directional counters, checksum validation and gzip handling.
- `catalog.py`: builds a searchable JSON index from recovered .proto schemas and the message-name list.

## Build the API catalogue
Place the recovered analysis bundle in a local, untracked `analysis/` folder, then run:

```bash
python -m la_api.catalog --proto-dir analysis/proto --messages analysis/api_messages_all.txt --output la_api/api_catalog.json
```

The current analysis generated 3,170 catalogue entries, including 2,822 messages with matching protobuf schemas.

## Authentication boundary
The transport codec does not generate SDK signatures, account tokens, or device credentials. Session establishment must use a legitimate session from the user's own game client or an officially supported authentication flow. Never commit credentials, tokens, PCAPs, or device identifiers to Git.
