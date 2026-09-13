# BUILDLOG.md — AI Usage & Engineering Decisions

**Student:** Deepak R  
**Project:** Multi-Platform Social Campaign Publisher (Social Media Studio)  
**Program:** FlyRank Backend Internship Capstone  

---

## 1. Overview of AI Partnership

This project was developed under the **4D AI Fluency Framework** (Delegation, Description, Discernment, Diligence). AI was used as a rapid scaffolding assistant for image variant math, cryptographic boilerplate, and database schemas, while critical architectural choices regarding idempotency keys, durable job resumption, and trust boundaries were manually designed and verified.

---

## 2. Where AI Helped Most

1. **Pillow Aspect-Ratio & Safe-Zone Calculations:**
   - AI formulated the center-weighted crop and scale math (`src_ratio vs target_ratio`) ensuring images scale cleanly without stretching or distortion to $1080\times1080$ and $1600\times900$.
2. **AES-GCM Authenticated Encryption Boilerplate:**
   - Rapidly generated the Python `cryptography.hazmat.primitives.ciphers.aead.AESGCM` implementation with separate 96-bit random nonces for each token stored.
3. **Composable Prompt Fragment Architecture:**
   - Created the modular structure separating brand voice, platform rules, and content summaries, mirroring FlyRank's `config/social-prompts.config.ts`.

---

## 3. Where AI Was Wrong or Hallucinated (And What I Fixed)

### Error 1: Re-Publishing Variants After Worker Crash
* **What AI initially suggested:** When restarting an interrupted scheduled job, the AI simply re-looped through `campaign.variants` and called `publisher.publish(...)` for each one, assuming the platform's idempotency key would handle it.
* **Why it failed:** While the external platform did return `idempotent_replay: True`, the local adapter blindly logged another `PublishHistory` success entry for the already-posted variant. This resulted in 3 history entries for 2 variants (violating Probe 3).
* **My fix:** Implemented persistent step memoization in `services/scheduler.py`:
  ```python
  # Check if variant step was already committed prior to crash
  existing_record = db.query(IdempotencyRecord).filter(
      IdempotencyRecord.idempotency_key == idemp_key
  ).first()
  if existing_record:
      results.append({
          "campaign_id": campaign.id,
          "platform": variant.platform,
          "post_id": existing_record.external_post_id,
          "idempotent_replay": True
      })
      continue
  ```
  The worker now detects already-finished steps locally and skips re-invoking the network adapter, guaranteeing zero redundant calls and accurate history logging.

### Error 2: Timing Attacks on Webhook Signature Comparison
* **What AI generated:** AI initially checked HMAC signatures using standard equality: `if signature_header == expected_sig:`.
* **Why it failed:** Standard string comparison (`==`) is vulnerable to timing side-channel attacks, where an attacker measures slight differences in response times to guess valid HMAC bytes.
* **My fix:** Swapped to `hmac.compare_digest(signature_header, expected_sig)`, ensuring constant-time verification across all delivery payloads.

### Error 3: Python 3.12+ `datetime.utcnow()` Deprecation Warnings
* **What AI generated:** Used `datetime.datetime.utcnow()` across models and scheduling routines.
* **Why it failed:** Python 3.12+ flags `utcnow()` as deprecated and scheduled for removal.
* **My fix:** Standardized on `datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)` with a centralized helper `utc_now()`, keeping SQLite naive datetime compatibility with zero warnings.

---

## 4. Explaining Key Code Lines (Evaluator Spot-Check Prep)

* **Adapter Seam & Dependency Inversion (`services/adapters/__init__.py:15-30`):**
  > *"The core application has zero knowledge of concrete platform APIs. It interacts solely with the `SocialPublisher` abstract interface via `get_publisher(platform)`. When we need to swap Telegram for `mock_x`, we register the adapter in configuration without altering any business logic or scheduling code."*

* **AES-GCM Token Encryption at Rest (`services/crypto.py:25-35`):**
  > *"We never store plaintext OAuth tokens. Each token is encrypted using AES-GCM with a fresh 96-bit cryptographically secure random nonce (`os.urandom(12)`). The nonce is stored alongside the ciphertext. Even with identical tokens, ciphertexts differ every time. Grepping the database yields zero plaintext credentials."*

* **Pre-Review Constraint Enforcement (`services/caption_composer.py:20-48`):**
  > *"Rather than relying on hope or human vigilance, `validate_caption_constraints()` validates character length and hashtag boundaries immediately upon ingestion. If an X variant exceeds 280 characters or lacks hashtags, it is automatically marked 'rejected' with the specific rule violation recorded, preventing it from ever reaching the review queue."*
