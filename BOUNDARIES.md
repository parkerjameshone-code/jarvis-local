# Boundaries

These are enforced in code, not just promised in prompts. Tests cover each one.

## Needs your yes (shown in full, never cut off)

- Running a terminal command that is not on the short read-only list (`ollama list`, `git status`, `dir` ...).
  Approved commands open in their own visible window so you can watch them.
- Pulling or removing a model.
- Sending files to the Recycle Bin.
- Building or promoting a pack.
- Sending approved outreach email.

If the arguments are too long to show you in full, the action is refused instead of shortened.

## Never allowed, even if you say yes

- Disk formatting or partition changes, recursive deletes, registry edits, firewall or antivirus changes,
  shutdown, boot settings, changing the PowerShell execution policy.
- Encoded or obfuscated commands (carets, backticks, encoded PowerShell, piping downloads into a shell).
- Deleting your home folder, drive roots, system folders, user folders (Documents, Desktop, Pictures,
  app data), anything inside a git project, or folders listed in `project_dirs`. Deletion is Recycle Bin only.
- Sending a social media message. It only drafts; you copy and send.
- Contacting anyone on the do-not-contact list, or drafting again for a lead you already sent, booked or closed.
- Email without an approved template, a postal address, a from address and an unsubscribe line,
  or above the daily cap (20 per day, rising slowly).
- Offering anything that is not in your own `[[offers]]` config. The model cannot invent offers.

## Privacy

- Talks only to the Ollama on this machine (loopback).
- Config, memory, leads and the audit log live in `~/.jarvis/`, outside this repo.
- Do not put API keys, passwords, addresses or prices in the repo. Use environment variables and your private config.

## Your responsibility

You are responsible for following the terms of any site you collect leads from and the email and
privacy laws where you and your recipients live. Keep volume low and always honor opt-outs.
