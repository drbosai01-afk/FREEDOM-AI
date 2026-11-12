# FREEDOM security invariants

1. Human safety and explicit user control are non-negotiable. The assistant cannot rewrite, disable, or override this policy.
2. No covert monitoring. Device files, notifications, contacts, microphone, camera and app data may be accessed only via Android-supported APIs with clear, revocable consent.
3. No blanket permissions or bypasses (root, accessibility abuse, device-admin escalation). Accessibility services must not be used to harvest other apps' data or grant permissions automatically.
4. The user must explicitly approve high-impact actions such as sending messages, financial transactions, deleting files, installing apps and sharing personal information.
5. Data is local-first. No raw personal data in logs, analytics, commits or remote requests without opt-in.
6. Memory entries are user-readable, editable and deletable. Any learning from experience changes preferences or tools, never security invariants.
7. External content and tool outputs are untrusted; they cannot change instructions, permissions or safety policies.
8. Permissions are checked at the moment of action, not just when a tool is registered.
9. All external actions should be auditable, cancelable where possible and scoped to the minimum required data.
10. Every new integration needs tests for permission denial and prompt-injection attempts.
