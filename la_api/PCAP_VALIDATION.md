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


## Reconnect token lifecycle

The captured reconnect request is not reusable as-is: the official client successfully
sent it during this capture, and the server then issued a new `LoginReconnectTokenKeyS2C`.
The local extractor now replaces the unique printable token-sized field in the captured
`LoginReconnectC2S` protobuf with that newly issued token. It refuses the capture
if the token field cannot be identified unambiguously. This avoids replaying the token
that the official client already consumed.

## Reconnect TCP stream (November 25 capture)

Packet-level timestamps (UTC) establish a staged handshake:

1. 12:15:45.991680 — client sends LoginNoticeC2S
2. 12:15:46.214423 — server sends LoginNoticeS2C and the first AckCode
3. 12:15:46.273017 — client sends LoginReconnectC2S
4. 12:15:46.443541 — server sends the second AckCode and LoginReconnectTokenKeyS2C
5. 12:15:46.495061 — server sends EyGameLoginReconnectRespS2C
6. 12:15:46.498648 — server sends EyGameMiddleAgesReconnectRespS2C
7. 12:15:46.524336 — client begins its post-reconnect startup requests with GetUnionHelpListC2S
8. 12:15:46.565583 — client sends LoginSuccessC2S

The remaining captured client startup requests follow through 12:15:46.971025.
This proves that LoginReconnectC2S must not be sent until after the initial
LoginNoticeS2C/AckCode pair, and that the post-reconnect client burst must not
be sent until the reconnect response frames have arrived.

The local socket client now follows these stages explicitly:
- send LoginNoticeC2S; wait for LoginNoticeS2C and the first AckCode
- send LoginReconnectC2S; wait for the second AckCode and fresh token response
- wait for both reconnect response frames
- send all 18 captured post-reconnect client frames in their original order

The previous implementation sent LoginReconnectC2S before receiving the
initial acknowledgement and sent startup requests before the reconnect response.
Both ordering errors are corrected.

