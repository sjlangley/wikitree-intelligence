# TODOs

## Safe WikiTree Write-Back From Sync Review

What:
Add a future workflow for applying approved later sync-review items back into WikiTree
in a deliberate, traceable way.

Why:
Version 1 can identify matched profiles where GEDCOM contains useful facts or sources
that WikiTree does not yet have. Without a follow-up write-back flow, that value stops at
review instead of improving the real tree.

Pros:
- Turns review findings into real WikiTree improvements
- Keeps import and enrichment separate
- Creates a clear path from evidence packet to user-approved update

Cons:
- Needs careful auth and API boundary design
- Requires audit history and rollback thinking
- Raises trust and correctness requirements compared with read-only review

Context:
This should not be part of the initial import pipeline. Import resolves identity,
produces evidence packets, and populates the later sync-review queue. A future write-back
workflow would take human-approved deltas from that queue and convert them into explicit
WikiTree updates with traceability.

Depends on / blocked by:
- Version 1 later sync-review queue
- Stable evidence packet format
- Confirmed WikiTree authentication and update capabilities
