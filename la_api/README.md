# LA Tracker API Core

This isolated module adds a local PCAP-session query path. The existing server-139 tracker and default branch are unchanged.

## Run locally (Windows)

1. Download this branch as ZIP and extract it.
2. Keep your PCAP on your PC; do not add it to Git.
3. Open PowerShell in the extracted repository root.
4. Run:

```powershell
python run_la_tracker.py
```

5. Open `http://127.0.0.1:8765`.
6. Select your own `.pcap` file, import its session, and click reconnect.
7. After reconnect succeeds, query server 139 rankings or enter a guild ID.

Python 3.10+ is recommended. No third-party Python packages are required.

## PCAP session flow

- `pcap_session.py` reassembles the captured TCP stream and extracts the account name, account UID, server ID, endpoint and reconnect token from the matching login frames.
- `socket_client.py` sends `LoginNoticeC2S`, then `LoginReconnectC2S`, completes the game login acknowledgement, and can send `QueryRankInfoC2S` / `QueryUnionPublicInfoC2S`.
- `local_server.py` serves the console and API on **127.0.0.1 only**.
- `local_console.html` provides PCAP import, reconnect, ranking and guild queries.

The captured PCAP currently resolves to account server **137** and endpoint **35.71.144.148:9929**. The query form defaults to target server **139**; the account's login server and the ranking target server are separate values.

## Important limitation

The PCAP contains a server-issued reconnect token, but it may have expired or been invalidated. The app can attempt the legitimate reconnect using the user's own captured session. If the server rejects it or the endpoint has changed, the old PCAP alone cannot mint a fresh token. In that case a new normal login session is required; MuMu integration is deliberately deferred until this PCAP-only path has been tested.

The app keeps the extracted token in process memory only. It is not written to disk, browser storage, logs, GitHub, or API responses. The PCAP is read in the browser and posted only to the local loopback service. Do not expose port 8765 to a LAN or public network.

## Other API tooling

- `protocol.py`: JuFeng frame encoder/decoder, directional counters, checksum and gzip.
- `catalog.py`: full API catalogue builder from recovered .proto files and message names.
- `index.html`: static API schema explorer.
- `api_catalog.json`: four-message starter catalogue; generate the full catalogue with the recovered analysis bundle.
