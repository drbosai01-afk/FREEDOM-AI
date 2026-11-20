# FREEDOM — initial architecture (Android)

## Objective
A user-controlled personal assistant with voice, memory and extensible tools. The eventual deliverable is an installable Android APK. This branch is a foundation, **not** a compiled APK.

## Components
- **UI** — native Android application with conversational interface and visible action confirmations.
- **Orchestrator** — routes an intent to a registered tool; no direct privileged filesystem access.
- **PermissionBroker** — checks per-tool user consent and Android runtime permissions, requiring confirmation for consequential operations.
- **LocalMemory** — encrypted local store with view/edit/delete/export controls (implementation pending).
- **Voice** — optional speech-to-text and text-to-speech, only on deliberate activation (implementation pending).
- **Tools** — explicit Android integrations for selected files, share intents, calendar etc.; each limited to user-granted scope.
- **Policy** — non-editable safety invariants, enforced outside the learning mechanism.

## Milestones
1. Create native Android project and unit-tested permission broker.
2. Add a basic chat UI and explicit tool-confirmation prompts.
3. Add local opt-in memory and export/delete.
4. Add voice input/output.
5. Add file access via Android Storage Access Framework, selected by the user.
6. Add supported integrations, one at a time.
7. Build and sign an APK; test installation and permission-denial scenarios on Android 16.

## Explicit limitations
Android sandboxing prevents arbitrary access to *all* data in *all* apps. FREEDOM will not attempt to bypass that protection. An APK needs a trusted signing key and validation before installation.
