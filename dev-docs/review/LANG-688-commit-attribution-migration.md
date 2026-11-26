# LANG-688 commit attribution cleanup: migration proposal

## Purpose

Remove the erroneous `Co-authored-by: multica-agent <github@multica.ai>` message
trailer from LangBot's existing commit history. This is a trailer cleanup only:
retain every commit's Git author and committer identities, commit trees, and all
other message content. Do not substitute random identities or redistribute
authorship.

## Verified against

- Original `master` tip: `cd89dd42e72cf1d0c7be4a5b9fc682c7df7df485`
- Original commit count: 5,942
- Matching trailer count: 415
- Rewritten local tip: `a4ebd1dec935c064fa7d3736da5aae0dc93b59c2`
- Rewritten tree: `d0a58a937c93fe6bcfb9e4ead69109be0dc13a10` (same as original)
- Verification: zero matching trailers after rewrite; aggregate author name/email
  counts unchanged; commit count unchanged.

The rewritten tip is local to the preparation environment and is not published
by this proposal PR. GitHub rejected updating `master`: force-push is prohibited
by the active repository rules, and the branch requires three status checks.

## Proposed maintainer-run migration

1. Approve a maintenance window and notify contributors that all local branches
   based on the old `master` will need to be rebased or recloned afterwards.
2. Preserve the current `master` tip in a named backup ref and record it in the
   migration log.
3. Review the generated history and verify the checks above from the exact
   selected source tip. Remove only the exact trailer line; preserve other
   commit message lines and all author/committer fields.
4. Have a repository administrator temporarily authorize the history update
   under the active branch rules, then atomically update `master` to the reviewed
   rewritten tip. Do not weaken protections outside the approved window.
5. Verify the published `master` tree and author metadata, confirm the trailer
   count is zero, and restore branch protections immediately.
6. Publish contributor resynchronization instructions and retain the backup ref
   until maintainers confirm recovery is no longer needed.

This document is a proposal and verification record, not authorization to
rewrite or force-update the shared branch. The branch update must be performed
by an administrator during the agreed maintenance window.
