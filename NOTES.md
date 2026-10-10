# NOTES

Open items and follow-ups. Delete entries once they're done.

## Pending

- **v1.1 and v1.2 have no tags, images or releases yet.**
  - Why: CI's `GITHUB_TOKEN` can't create those tags, because their old `docker.yml` isn't on any ref (see CLAUDE.md, "Backfilled releases"). Every other version (v1.0, v2.0–v2.7) is tagged, imaged and released.
  - Fix (owner, from their own clone):
    ```bash
    git fetch origin
    GIT_COMMITTER_DATE="$(git show -s --format=%cI 8f8626b)" git tag -a v1.1 -m "STODO v1.1" 8f8626b
    GIT_COMMITTER_DATE="$(git show -s --format=%cI b6d42f6)" git tag -a v1.2 -m "STODO v1.2" b6d42f6
    git push origin v1.1 v1.2
    ```
    Then re-run "Build, Push and Release" from the Actions tab.
  - Alternative a Claude session could do, with the owner's OK:
    1. Push a commit restoring the v1.x `.github/workflows/docker.yml`.
    2. Run the workflow on main.
    3. Push a commit restoring the current file.
- **Private-repo update checks haven't been tested end to end.**
  - Only checked against simulated GitHub responses: the sandbox proxy injects its own GitHub auth.
  - Worth one real test with a fine-grained token (Contents: Read-only) on a private fork, using Settings → Updates → Check for updates.

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
