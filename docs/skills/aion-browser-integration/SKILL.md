---
name: aion-browser-integration
description: Use when browser automation on macOS opens and closes unexpectedly, behaves differently from the normal browser session, or may be mediated by Aion/灵汐 protection.
---

# Aion Browser Integration

## Overview
Use this skill when an automated browser on macOS appears to be intercepted by Aion/灵汐 and needs to cooperate with Aion's public lease lifecycle instead of fighting it.

For the full integration notes and the concrete `garmin-sync` implementation, read [references/garmin-sync-aion-integration.md](references/garmin-sync-aion-integration.md).

## When to Use
- The automated browser opens and closes immediately.
- The automated browser behaves differently from the user's normal Chrome session.
- A protected site keeps resetting the automation session without a clear page-level error.
- You need a reusable pattern for Playwright plus Aion lease management.

Do not use this skill for ordinary browser QA when the automated session is already stable.

## Workflow
1. Reuse the current browser session when possible.
2. Only use Aion's public Unix socket contract.
3. For Playwright Chrome, derive the `appKey` from the actual temporary Chrome profile when available.
4. Create a real browser page before `lease.begin`.
5. Renew the lease in the background and answer close checks with `extend_lease`.
6. End the lease when the automated session is done.

## Quick Checklist
- Socket path: `~/Library/Application Support/Aion/ipc/ai-protection.sock`
- Handshake: `session.hello -> session.ready -> lease.begin`
- Keepalive: `lease.renew`
- Shutdown: `lease.end`
- Close negotiation: `lease.can_close.request -> lease.can_close.reply`
- Preferred Chrome key order:
  - `com.google.Chrome#profile:<playwright_profile>`
  - `com.google.Chrome`
  - `com.google.Chrome#automation`
