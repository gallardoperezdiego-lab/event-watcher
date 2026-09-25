# Handover & ownership

## Statement

Event Watcher does not depend on the original developer in any way. It uses no developer-owned account, email address, password, subscription, API key, hosting, cloud database, Google, Firebase, Gemini, OpenAI, Microsoft or Apple service, and no telemetry. If the developer disappeared today, every installed copy would keep working exactly the same.

The only network traffic it creates goes to the public web addresses listed in your watchers.

## Why the person who downloads it owns it

The code is published under the **MIT licence** (see [LICENSE](LICENSE)). Anyone who receives a copy gets permanent permission to use, copy, modify and share it, free of charge. A downloaded copy does not phone home, has no licence key and cannot be disabled remotely. Keeping this GitHub repository is useful for updates, but a copy works without it.

## Checklist

- [x] **No developer API keys embedded.** The project contains no API keys. (An unused Google AI Studio `.env` file and the `@google/genai` package, left over from the original template, were removed.)
- [x] **No developer email embedded.**
- [x] **No Firebase dependency.**
- [x] **No Google account dependency.**
- [x] **No Gemini API dependency.** Matching uses deterministic rules on your computer.
- [x] **No external database dependency.** Local SQLite file.
- [x] **No external authentication dependency.** No logins. The app only listens on `127.0.0.1`, so other devices on the network cannot reach it.
- [x] **No telemetry.** No analytics, tracking or error-reporting services. Fonts are bundled, so even the interface loads nothing from the internet.
- [x] **All data stored locally**, in one data folder (see README, "Keeping your data safe").
- [x] **Backup/export supported:** Backup & transfer → Download full backup, plus automatic daily backups.
- [x] **Restore/import supported:** Backup & transfer → Import backup. The archive is checked before anything is replaced, and the previous database is kept.
- [x] **Application can run after developer account deletion.** The packaged apps need nothing installed. The source needs only Python 3.9+.

## What the business should keep (for example in its 1Password vault)

Event Watcher itself has no credentials, so nothing needs to be stored for it to keep working. To be able to reinstall it anywhere, keep:

1. **The apps:** `EventWatcher.exe` and/or `EventWatcher-mac.zip` from the Releases page.
2. **A copy of the code:** GitHub → **Code → Download ZIP**.
3. **A recent backup ZIP**, or set **Automatic daily backups → extra folder** to a location the business owns.

With those three things, anyone can reinstall and restore Event Watcher on any computer without contacting the developer or using GitHub.

## About this repository

This repository is private and currently hosted on the developer's GitHub account. To download from it, the business needs a GitHub account (create it with a business email address and keep the login in the business's 1Password), and the developer invites that account as a collaborator. At any time the developer can also transfer the repository to the business's account (GitHub → Settings → Transfer ownership), so the business controls updates too.

## Moving to another computer

1. On the old computer: **Backup & transfer → Download full backup**.
2. On the new computer: open `EventWatcher.app` / `EventWatcher.exe`.
3. **Backup & transfer → Import backup** and choose the ZIP. Watchers, events and settings are restored.
4. Optionally tick **Settings → Start Event Watcher when I log in** again. This is a per-computer choice and is not copied by backups.

## Things the owner may need to maintain

- **Websites change.** If a source stops working, the Sources screen shows it and a "needs attention" notification is sent. Edit the watcher's address or replace it. Some sites block automated readers entirely (for example WhatsOnStage returns "403 Forbidden"); choose another source for those.
- **Keywords.** Venue watchers report every new event at that venue. Add words to look for (e.g. "Belfast") or words to ignore (e.g. "tribute") to narrow them down.
- **Boucher Road.** Belfast City Council has approved ending concerts there after 2027. That watcher can be deleted then.
- **The computer must be on.** Missed checks are caught up a few seconds after the app starts again.
- **Rebuilding the apps** after code changes: see [BUILD.md](BUILD.md). Only free tools are needed.
- **Unsigned apps.** Signing requires a paid Apple or Microsoft developer account owned by someone. The apps are deliberately unsigned, so the operating system asks for confirmation the first time.

## Remaining dependencies

| Needed for | What | Account needed? |
|---|---|---|
| Using the apps | Nothing | No |
| Running from source | Python 3.9+ (python.org) | No |
| Building the apps | PyInstaller + certifi, or GitHub Actions (automatic) | No / GitHub account for Actions |
| Changing the interface | Node.js 20+ and `npm install` in `web/` | No |
| Notifications | Built into macOS, Windows and Linux | No |
