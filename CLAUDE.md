# CLAUDE.md - Project Context for AI Assistants

This file contains project context, decisions, and learnings for AI assistants working on SIPring.

## Project Overview

SIPring is a Docker-based SIP phone ringing service for triggering alerts (doorbell, notifications) via HTTP requests. It uses a custom Python SIP implementation inspired by [FemtoSIP](https://github.com/astoeckel/femtosip).

## Key Decisions

### SIP Protocol

1. **No SIP Authentication Needed**: The Gigaset N670 IP DECT base station accepts INVITE messages from LAN without authentication. The `sipring/sip/auth.py` module exists for future use if needed.

2. **CANCEL Requirements** (RFC 3261):
   - CANCEL must match INVITE exactly: Request-URI, Call-ID, From (with tag), To, Via (with branch)
   - Only the CSeq method changes from "INVITE" to "CANCEL"
   - Same CSeq number as the INVITE

3. **BYE Requirements**:
   - BYE requires the To-tag from the 200 OK response (dialog established)
   - Uses a new branch but same Call-ID
   - Incremented CSeq number

4. **Call State Machine**:
   ```
   IDLE → INVITING → RINGING → (timeout) → CANCELING → TERMINATED
                        ↓
                 (answered) → ANSWERED → (send BYE) → TERMINATED
   ```

5. **Caller ID Display**: The `P-Asserted-Identity` and `Remote-Party-ID` headers are used to display caller name on the phone. Format based on working capture from `invite_haustuer_clean.sip`.

### Architecture

1. **Custom SIP vs Library**: Chose custom implementation over libraries like PJSIP because:
   - Minimal dependencies
   - Tailored to ring-only use case
   - Based on proven FemtoSIP concepts
   - Full control over SIP message format

2. **FastAPI**: Chosen for async support and auto API docs at `/docs`.

3. **JSON Storage**: Human-readable, NFS-compatible, simple backup. File locking with `fcntl.flock` for multi-node safety.

4. **Docker Networking**: Must use `network_mode: host` for SIP UDP to work correctly - SIP requires the source IP to match what the phone sees.

### Target Hardware

- **SIP Server**: Gigaset N670 IP DECT base station
- **Default Target**: `**610@192.168.1.100:5060`
- **Local Port**: 5062 (to avoid conflicts with other SIP software)

## Reference Files

- `invite_haustuer_clean.sip` - Working INVITE message capture that displays caller ID correctly on the Gigaset phone

## Testing Notes

### POC Script Usage
```bash
# Basic test - ring for 5 seconds
python poc_sip.py --target-host 192.168.1.100 --target-user **610

# Longer ring
python poc_sip.py --duration 10

# Wait for answer then send BYE
python poc_sip.py --wait-answer
```

### Expected Behavior
1. Phone should ring with "Klingel (Haustür)" displayed
2. After duration, ringing should stop (CANCEL sent)
3. If answered, BYE should be sent and call terminated

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ring/{uuid-or-slug}` | Trigger ring |
| GET | `/ring/{uuid-or-slug}/cancel` | Cancel active ring |
| GET | `/ring/{uuid-or-slug}/status` | Check ring status |
| GET | `/api/configs` | List all configs |
| POST | `/api/configs` | Create config |
| GET | `/api/configs/{uuid}` | Get config |
| PUT | `/api/configs/{uuid}` | Update config |
| DELETE | `/api/configs/{uuid}` | Delete config |
| POST | `/api/configs/{uuid}/test` | Test ring (3s) |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SIPRING_DATA_DIR` | `/data` | Directory for config.json |
| `SIPRING_PORT` | `8080` | HTTP server port |
| `SIPRING_LOG_LEVEL` | `INFO` | Logging level |
| `SIPRING_USERNAME` | - | Basic auth username (optional) |
| `SIPRING_PASSWORD` | - | Basic auth password (optional) |
| `SIPRING_EVENT_RETENTION_DAYS` | `90` | Days to keep events (0 = forever) |

## User Preferences

1. **No AI Attribution in Commits**: Do not include "Co-Authored-By: Claude" or similar AI mentions in git commits.

2. **GitHub Releases for Version Changes**: When changing the version, create a GitHub release after pushing the commit.

## Learnings

1. **SIP Message Format**: Extra blank lines in SIP messages can cause issues. The format in `invite_haustuer_clean.sip` has specific placement of headers.

2. **Timezone-aware Datetimes**: Python 3.12+ deprecates `datetime.utcnow()`. Use `datetime.now(timezone.utc)` instead.

3. **FastAPI Lifespan**: `@app.on_event("startup/shutdown")` is deprecated. Use `lifespan` context manager.

4. **Pydantic V2**: `json_encoders` in model_config is deprecated. Models serialize correctly by default.

5. **Unicode in Slugs**: German umlauts (ü → u) need `unicodedata.normalize('NFKD')` for proper ASCII conversion.
