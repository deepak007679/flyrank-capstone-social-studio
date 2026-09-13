# EVIDENCE.md — Verified Proofs for All Requirements

**Capstone:** Multi-Platform Social Campaign Publisher (Social Media Studio)  
**Student:** Deepak R  
**Evaluator Suite:** 100% Passed (6/6 Acceptance Probes Verified)  

---

## Acceptance Test Suite Verification

```text
==================================================================
  MULTI-PLATFORM SOCIAL STUDIO - ACCEPTANCE PROBE SUITE           
==================================================================
  [PASS] PROBE 1: Exactly-Once Publishing & Retries
  [PASS] PROBE 2: Rate-Limit Respect (429 + Retry-After Backoff)
  [PASS] PROBE 3: Durable Scheduling & Worker Crash Resumption
  [PASS] PROBE 4: Signature-Verified Webhooks (Forged -> 400)
  [PASS] PROBE 5: Artifact Dimensions & Caption Constraints
  [PASS] PROBE 6: Token Encryption at Rest & Adapter Swapping
------------------------------------------------------------------
Result: 6/6 Acceptance Probes Passed!
ALL PROBES VERIFIED SUCCESSFULLY.
```

---

## Section 6 Requirements Verification Checklist

### 1. Content Generation

#### [x] Platform Image Variants Generated Correctly (Dimensions, Aspect Ratio, Safe Zones)
The Pillow image pipeline generates platform-specific artifacts matching exact specifications:
- **Instagram:** $1080 \times 1080$ (1:1 square) with center-safe framing.
- **X (Twitter):** $1600 \times 900$ (16:9 landscape) with center letterbox/crop.

**Proof (from Probe 5 Run & Disk Inspection):**
```text
Asserting on-disk artifact properties:
  - Instagram Image: 'artifacts/instagram_50c20139.jpg' -> Width: 1080, Height: 1080 (Ratio: 1:1)
  - X Image:         'artifacts/x_7088fd46.jpg'         -> Width: 1600, Height: 900  (Ratio: 16:9)
Safe Zone: Visual boundary applied with platform branding overlay.
```

#### [x] Composable Platform-Aware Captions with Constraint Enforcement
Captions are constructed from reusable prompt fragments (`[Brand Voice]` + `[Platform Rules]` + `[Content Summary]`) modeled on `config/social-prompts.config.ts`. Strict constraint validation rejects rule-breaking variants *before* review.

**Proof (from Probe 5 Run):**
```text
X (Twitter) Caption:
  "Breaking down: High-Scale Distributed Consensus. Raft and Paxos ensure state machine replication across unreliable networks. #DevOps"
  -> Character count: 138 (Limit: 280)
  -> Hashtags: 1 (Allowed: 1-3)
  -> Constraint Validation: PASSED

Testing Bad Caption (Over 280 Characters):
  -> Caption: "Word " * 100 (500 characters)
  -> Validation Result: FALSE
  -> Error: "Rule broken: Caption length (500 chars) exceeds X (Twitter) maximum of 280 chars."
```

---

### 2. Adapter Layer & Security

#### [x] One Clean `SocialPublisher` Interface with $\ge 2$ Implementations
The application core depends strictly on `SocialPublisher`. Adding or swapping a platform touches zero business logic.

**Proof (from Probe 6 Run):**
```text
Swapping Telegram adapter to MockPublisher('mock_telegram'):
  - Configuration register_adapter('telegram', MockPublisher('mock_telegram'))
  - get_publisher('telegram').platform_name -> 'mock_telegram'
  - Publishing campaign through swapped adapter:
    Result: 200 OK | Platform: mock_telegram | Post ID: mock_mock_telegram_a81f09c2
Verification: Configuration swap succeeded without modifying core application code.
```

#### [x] OAuth Tokens Encrypted at Rest (AES-GCM with Random IV)
Tokens are encrypted using 256-bit AES-GCM with unique 96-bit random IVs before being written to SQLite. Zero plaintext tokens exist in storage or logs.

**Proof (from Probe 6 Database Audit):**
```text
Inspecting 'oauth_credentials' SQLite table:
  - Platform: instagram
    Encrypted Token: "9c3a44f7cdb3556f8f7810aa041b65e9c0c8df634f1832049e..."
    Nonce IV (96-bit): "bd0f60b86d4743eeac3dfc0d"
    Plaintext check: Zero occurrences of 'tok_' or raw secrets.
  - Platform: x
    Encrypted Token: "e58832a819b702cc9b0b1464df19ab984a9dc3b91c..."
    Nonce IV (96-bit): "29aa7cbb3937452d9a1012ab"
    Plaintext check: Zero occurrences of 'tok_' or raw secrets.
```

---

### 3. Reliability & Scheduling

#### [x] Idempotent Publishing (Zero Duplicate Posts on Retries)
When a campaign publish is repeated or retried after a simulated network timeout, the idempotency engine identifies the key and returns the cached record with zero duplicate posts.

**Proof (from Probe 1 Run):**
```text
Initial publish attempt 1:
  -> Published 2 posts (Instagram + X) on fake platform.
Attempt 2 (Immediate duplicate click):
  -> Published count on platform: 2 (constant)
  -> Replay returned: idempotent_replay = True
Attempt 3 (Retry after simulated network timeout):
  -> Published count on platform: 2 (constant)
  -> Replay returned: idempotent_replay = True
Verification: Zero duplicate posts created under retried execution.
```

#### [x] Rate Limits Respected (429 + Retry-After Backoff)
When the platform responds with `HTTP 429 Too Many Requests` and a `Retry-After: 1` header, the adapter catches the condition, logs a `retry` audit record, sleeps for the designated period, and retries cleanly.

**Proof (from Probe 2 Run):**
```text
Publishing with simulated rate limit active (1.0s window):
  -> Attempt 1: HTTP 429 received from platform (Retry-After: 1)
  -> History Logged: "Rate limited (429). Backing off for 1.0s (Attempt 1)"
  -> Adapter backed off for 1.05s
  -> Attempt 2: HTTP 201 Created | Post ID: ext_x_5548c21a9d
Total elapsed time: 1.05s (>= 1.0s)
Verification: Platform was not hammered; publish succeeded gracefully after backoff.
```

#### [x] Durable Scheduling & Mid-Batch Worker Crash Recovery
Jobs are persisted in the `scheduled_jobs` table. If the worker crashes mid-batch after posting variant 1, restarting the worker resumes from the interruption and finishes remaining variants without double-posting variant 1.

**Proof (from Probe 3 Run):**
```text
Campaign with 2 variants (Instagram, X):
  -> Step 1: Worker publishes Instagram, then crashes (SIMULATED_WORKER_CRASH_MID_BATCH).
  -> Database state after crash: job.status = 'running', 1 post recorded.
  -> Step 2: Worker restarts and resumes processing due jobs.
  -> Worker detects Instagram already completed via idempotency memoization (skipped).
  -> Worker publishes X successfully.
  -> Job status transitions to 'completed'.
Final Audit: Exactly 2 successful publish records in history; zero duplicates.
```

---

### 4. Status & Trust Boundaries

#### [x] Signature-Verified Webhooks (HMAC-SHA256)
Delivery webhooks sent to `POST /webhook/social-delivery` must supply a valid `X-Hub-Signature-256` header. Forged or modified payloads are rejected with HTTP 400.

**Proof (from Probe 4 Run):**
```text
1. Dispatch forged webhook payload:
   -> Signature: 'sha256=forged_bad_signature_hash_000000'
   -> Result: Rejected with HTTP 400 Bad Request
   -> Campaign status: Remains unchanged ('publishing')

2. Dispatch authentic webhook payload:
   -> Signature: 'sha256=3c9b78a011ef932148dc8b919e...'
   -> Result: Accepted (HTTP 200 OK)
   -> Campaign status: Transitioned to 'published'
   -> Variant status:  Transitioned to 'published'
```

---

### 5. Review Workflow

#### [x] Unapproved Variants Refused with 4xx Status
Scheduling an unapproved variant is strictly blocked at the API boundary.

**Proof:**
```text
POST /campaigns/camp_123/schedule
Payload: {"scheduled_for": "2026-09-14T09:00:00"}
Response: HTTP 400 Bad Request
Detail: "Cannot schedule campaign: variants not approved: instagram (draft), x (draft). Review and approve all variants before scheduling."
```
