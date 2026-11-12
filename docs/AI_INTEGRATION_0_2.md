# FREEDOM 0.2 — AI integration plan

Status: design only; no AI provider connected and no new APK produced by this document.

## Product requirements

- Open-source Android client, no hidden moderation of ordinary conversation.
- The user can choose between on-device inference and an optional remote AI service; app must clearly indicate which mode is active.
- Never present canned responses as AI-generated responses.
- Memory is off by default; user can inspect, export, delete, and revoke stored memories.
- Do not grant unrestricted device permissions; each external action requires narrowly scoped Android grants and high-impact actions require confirmation.
- Immutable baseline safety policy: self-improvement cannot change permissions or safety rules.
- No background microphone capture, file indexing, or remote upload without explicit separate opt-in.
- No secrets hard-coded in the APK, manifest, repo, or workflow logs.
- For remote inference, use HTTPS, secure authentication mediated by a user-controlled backend, transparent data-transfer disclosure, and clear failure/offline states.
- Local inference requires a separately obtained and verified model file whose license permits the intended use; do not misrepresent an open-weights model as fully open-source.
- Model output must never be treated as authorization to execute phone actions.

## Implementation milestones

1. Audit debug APK and Google Play Protect warning before any new privileges or network access. Verify build provenance and APK permissions and review dependencies. A successful CI build is not a malware clearance.
2. Create an AIEngine interface supporting offline and remote implementations; make network mode explicitly disabled until selected by the user.
3. Build an opt-in settings screen for provider selection, privacy disclosures, and memory controls.
4. Add real conversational response rendering with lifecycle-safe asynchronous calls, cancellation, error reporting and basic tests.
5. Add user-controlled local memory with encryption and clear/delete/export.
6. Test on Android and publish a signed release only after security review and successful device testing.

## Current state

FREEDOM 0.1 is a local UI shell. The send button appends a fixed message, the voice button launches system speech recognition (which may have its own data practices), and the file button opens Android's document picker without reading file contents.

The existing Play Protect warning remains unresolved; do not encourage bypassing it or sharing sensitive user data.
