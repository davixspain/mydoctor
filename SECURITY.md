# Security Policy

## Reporting a vulnerability

If you discover a security issue in MyDoctor, please **do not open a public
GitHub issue**. Instead:

📧 Email: **davixspain@gmail.com** with subject `[mydoctor security]`

Include:

- A description of the issue
- Steps to reproduce (if applicable)
- Affected versions
- Your assessment of impact (low / medium / high / critical)
- Any proof-of-concept code (without including health data)

You will receive an acknowledgement within **72 hours**. For critical issues,
expect a coordinated disclosure timeline of **30 days max** before public
disclosure.

## Scope

In scope for security reports:

- ✅ Bot.py — input validation, ACL bypass, command injection
- ✅ install.py — privilege escalation, path traversal during install
- ✅ proactive_review.py — secret leakage in logs, prompt injection
- ✅ Vault path traversal in attachment routing
- ✅ Skill prompts that could be hijacked to exfiltrate vault data
- ✅ Telegram token / chat_id leakage in logs or telemetry

Out of scope:

- ❌ Vulnerabilities in third-party services (Telegram, Anthropic API,
  Obsidian) — report to those vendors directly
- ❌ Issues requiring local root access on the user's machine (out of
  threat model — MyDoctor assumes the user controls their own machine)
- ❌ Social engineering of the user (e.g., user pasting malicious links
  into the bot)
- ❌ Denial-of-service via excessive Claude API calls (Anthropic enforces
  rate limits server-side)

## Threat model

MyDoctor is **local-first**. The threat model assumes:

- The user controls their own machine
- The `.env` file (containing tokens) has filesystem permissions `600`
- The vault is under the user's home directory and not accessible by other
  users on shared systems
- The Telegram bot is configured with a single OWNER chat_id ACL

**Trusted parties** (data passes through them):

- The user themselves
- Telegram FZ-LLC (for messaging transit)
- Anthropic PBC (for LLM inference)

**Untrusted parties** (must not be able to access vault data):

- Other users on the same machine (mitigated by file permissions)
- Network attackers (mitigated by HTTPS for Telegram + Anthropic)
- The author of MyDoctor (no telemetry, no phone-home)

## Coordinated disclosure

- **Day 0**: vulnerability reported privately via email
- **Day ≤ 3**: acknowledgement
- **Day ≤ 30**: fix released or coordinated disclosure date set
- **Day 30+**: public CVE assignment if applicable, public advisory

For critical issues affecting user health data integrity, faster timeline
applies. We coordinate good-faith reporters with credit in the advisory if
they wish.

## Out-of-band rotation

If you discover that secrets have been leaked (e.g., a Telegram bot token
is committed to git history accidentally):

1. Immediately revoke via @BotFather (Telegram) or
   https://github.com/settings/tokens (GitHub PATs)
2. Rotate the secret in `~/MyDoctor/.env`
3. Restart the service
4. Optionally rewrite git history with `git filter-repo` if the secret
   was committed publicly

## Bug bounty

There is currently **no monetary bounty program**. This is a personal
open-source project with no commercial revenue. Recognition in the security
advisory and the changelog is offered as thanks.
