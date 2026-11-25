# PCAP Validation Notes (redacted)

Source: the user's supplied PCAPdroid capture. This note records structural validation only; it intentionally excludes account IDs, device identifiers, signatures, token values, and other credential contents.

## Reassembled game socket

- Game socket endpoint observed: `35.71.144.148:9929`
- Client-to-server TCP stream: 2,820 payload bytes, no sequence gaps in the captured stream.
- Server-to-client TCP stream: 259,754 payload bytes, no sequence gaps in the captured stream.
- Decoded client-to-server frames: 37.
- Decoded server-to-client frames: 238.
- Frame decoding succeeded in both directions, including checksum validation and gzip decompression.

## Login/session evidence

The capture contains this sequence:
1. `LoginNoticeC2S`
2. `LoginReqC2S` (1,428-byte protobuf body)
3. `LoginNoticeS2C`
4. `LoginReconnectTokenKeyS2C` (105-byte protobuf body; includes an account UID field and a 96-byte token-key field)
5. `EyGameLoginRespS2C` (gzip-compressed, 35,637-byte decoded protobuf body)
6. `LoginSuccessC2S`

This establishes that the supplied capture contains a real completed game login and a server-issued reconnect token. It does not establish that the captured token is still valid now.

## API request evidence

The same authenticated TCP stream contains `QueryRankInfoC2S` and `QueryUnionPublicInfoC2S` requests. The captured ranking requests target server 139.

## Next engineering step

Build a local-only session bridge that obtains a fresh session through the user's running, authenticated game client, keeps credentials outside Git, and hands a short-lived session to the API worker. Do not print or commit token/signature values. The captured reconnect token may be expired, so it should be treated as evidence of the protocol flow, not as a reusable current credential.
