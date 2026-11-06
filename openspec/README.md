# OpenSpec planning diary

This directory is the project's OpenSpec planning tree: `specs/` (current
capability contracts), `changes/` (active changes) and
`changes/archive/` (completed changes), plus `config.yaml`. It is kept in the
repo on purpose so anyone can read how the project evolved and *why*
decisions were made.

## Confidentiality — MANDATORY

**This repository is PUBLIC and customer-driven.** Users of these packages
file bug reports and share requirements, complaints, excerpts from real log
data, and real formatters/forwarders. During the OpenSpec process we
brainstorm with that real-life data. A single leaked hostname or ticket
number can put the author in deep trouble.

**Redact before you write.** Never put real customer data into any OpenSpec
artifact (proposal, spec, design, tasks). When an example needs a concrete
value, replace it with a fictional or obviously-safe placeholder *first*,
then write.

| Do NOT write | Replace with |
|---|---|
| A real hostname / host group | a fictional name (e.g. `srvblub`) |
| A public or customer IP | `127.0.0.1` / `localhost` / an obviously private range |
| A customer domain, URL, or email | none — do not include it |
| A ticket / incident / `sys_id` number | omit it or use a placeholder (`INC-0000`) |
| Credentials, API keys, tokens, Nostr `nsec`/private keys | never — not even redacted examples of the real value |

Safe by default: loopback (`127.0.0.1`), `localhost`, the project's own public
site (`omd.consol.de`), and invented names. If you are unsure whether a value
is safe, treat it as confidential and redact it.

### Why two layers

1. **Process (primary):** the redact-before-writing rule above. This is what
   actually protects you, because a pasted block of raw customer log text can
   contain confidential detail that no pattern matcher recognises.
2. **Guard (safety net):** a local `pre-push` hook (in `.git/hooks/pre-push`,
   deliberately *not* committed or pushed) scans every push's added lines for
   public IPs, email addresses, non-allowlisted hostnames, and key material,
   and blocks the push if it finds any. It catches the mechanical leak (a
   stray hostname/IP) but **does not replace redacting first.**

   If the guard fires on a false positive, review the matched lines, then
   `git push --no-verify`. Never bypass it to push a real leak.

### Audits performed

- **2026-11-06:** before re-tracking this tree, the current 133 files and all
  291 historical blobs were scanned for public IPs, emails, non-allowlisted
  domains/hostnames, ticket numbers, and key material. Result: clean — only
  loopback/`localhost`, fictional demo names (`srvblub`), and the author's
  own public email (already in `pyproject.toml`).

Re-run an audit before any large re-track: `git rev-list --objects --all --
openspec/` then scan each blob with the same patterns.
