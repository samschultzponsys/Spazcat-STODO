# NOTES

Open items and follow-ups. Delete entries once they're done.

## Pending

- **Private-repo update checks haven't been tested end to end.**
  - Only checked against simulated GitHub responses: the sandbox proxy injects its own GitHub auth.
  - Worth one real test with a fine-grained token (Contents: Read-only) on a private fork, using Settings → Updates → Check for updates.
- **Issues panel (v2.8) hasn't been tested against real GitHub writes.**
  - The sync engine and UI were tested against a fake in-memory GitHub, and a read-only sync against the real repo, which had 0 issues.
  - Still to check with the owner's token (Issues: Read and write): submit, comment, close and reopen once, then confirm the result on github.com.

## Follow-ups worth doing

- **Fonts mount:** the owner's compose mounts a host folder over `/app/static/fonts`, which hides the bundled Ethnocentric font, so the title falls back to Orbitron.
  - Either copy `ethnocentric_rg*.otf` into that folder, or drop the mount.
  - Also consider loading fonts from a separate path so mounting one can't hide the bundled files.
- **CI warning:** `actions/checkout@v4` warns about the Node 20 deprecation. Bump it to a newer major when convenient.
- **Tests:** there's no automated test suite.
  - The quickest win: a small pytest file covering `parse_changelog`, `parse_version`, `is_lan`/`get_real_ip` (incl. spoofed `X-Forwarded-For`), and secret stripping in `/api/config`.
  - Then run it in CI before building.
- **IPv6 LAN trust:** since v2.7, private IPv6 (ULA, `::1`) counts as LAN. Before, IPv6 was never trusted. Revisit if that's unwanted.
- **Credentials:** the owner was advised to rotate the IMAP app password, `TOKEN` and `INGEST_SECRET` from their deployment, because they were pasted into a chat. Confirm it's done.
