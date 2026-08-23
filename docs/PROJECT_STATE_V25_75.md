# HMS-AI-ROUTER — Project State v25.75

Date: 2026-08-23
Status: ACTIVE DEVELOPMENT CHECKPOINT
Authority: `main` on `hoangminhsang989/HMS-AI-ROUTER`

## Baseline

- Migration baseline: v25.74
- Cockpit Tools parity baseline: v1.3.27
- Product scope: Codex-only
- Product branding: HMS-AI-ROUTER
- Historical v25.74 evidence is immutable and may retain former product branding where it is part of frozen evidence.

## Evidence boundary carried forward

- Feature evidence score: 93.0%
- Production evidence score: 55.2%
- Windows runtime certified: false
- External Windows target evidence imported: false
- Real Codex effects executed: false
- Windows signing executed: false
- Automatic production certification: false
- Production score promotion eligible: false

These values MUST NOT be promoted without new real Windows/current-Codex evidence.

## v25.75 objectives

1. Enforce HMS-AI-ROUTER branding for all new product-facing source, launcher, UI, docs and newly generated evidence.
2. Preserve only technically required legacy compatibility identifiers and explicit Cockpit Tools parity references.
3. Audit the imported runtime tree for product-facing former-brand strings before changing them.
4. Prepare and execute the seven-case Windows/current-Codex certification packet.
5. Keep raw runtime evidence immutable, digest-bound and append-only.
6. Require dual review and baseline-drift reconciliation before any production evidence promotion.
7. Keep production score mutation human-authorized only.

## Windows/current-Codex certification gate

The next production gate remains blocked until real target execution exists for the required runtime/parity cases, including:

- foreign-port rebind behavior;
- duplicate-account occupancy / account switching safety;
- client-auth and API-service split;
- official-account continuity across supported auth storage modes;
- WebSocket persistence/refresh/switch behavior;
- bounded credential-backup retention and recovery;
- remaining multi-account, multi-instance, quota/plan, image and profile-takeover runtime gates.

## Change policy

- Do not rewrite frozen v25.74 manifests merely to rename historical product strings.
- Do not claim Windows certification from synthetic/Linux/CI-only evidence.
- Do not auto-promote production scores.
- Do not force-push `main`.
- Source and development checkpoints live in GitHub; ChatGPT File Library is not a development source authority.

## Immediate next action

Perform a read-only branding/legacy audit of current runtime source, classify every former-brand occurrence as one of:

- product-facing rename required;
- Cockpit Tools parity reference allowed;
- legacy compatibility identifier required;
- immutable historical evidence retained.

Only after classification should source mutations be committed.
