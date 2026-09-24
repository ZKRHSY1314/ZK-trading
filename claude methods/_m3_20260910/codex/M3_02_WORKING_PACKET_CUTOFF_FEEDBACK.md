# M3-02 working packet cutoff feedback

This concerns the same active M3-02 task and its completed first development run, not a new task or a final verdict. Retain `dev_run_01` and all earlier evidence. Do not change the accepted label policy, control selection, development interval or target to address this finding.

Codex inspected every hash-bound packet listed in the working `dev_run_01/episodes.json`, using a metadata-only independent script (zero SQLite connections, zero actual case reviews):

- `codex/audit_working_packet_cutoffs.py`, SHA-256 `70daebb68354f0506e1097b34f033d3f122439a81504e777358be53aa58b3c8b`.
- `codex/reader_working_packet_cutoff_audit_01/result.json`, SHA-256 `0b3f86e71f98a492a855a7a8ab04c5d1d0a1523c828d6cdfbdfcfba6172e872e`.
- All 225 packet input hashes, the complete episode index, selected actual packet copies and the exact executed producer are retained in that audit folder.

**210/225 review-facing packets contain episode metadata later than their representative cutoff; 27 of the 32 matched potential positives are affected. 39 packets include explicitly future-dated eligibility transitions inside contradicting_evidence.**

Example: episode `5790fd873e1bf13be567f8937370c3d6` has representative cutoff `2023-12-11`, but `known_end_so_far=2024-01-26`, `status=closed`, and its contradictory evidence includes a `2024-01-05` transition to candidate. In the current reader this comes from `ep['end']`, the full episode status and `_contradicting(..., ep)` using the entire selection_path. A correct three-session prefix hash does not remove future information from the surrounding review material.

Keep the complete retrospective episode inventory for exhaustive accounting and dependence analysis, but generate the material supplied for actual cutoff-bound reviews from only the first three prefix members and source/context available through the representative cutoff. Future episode end/status, later selection transitions and censoring at the development end must not appear as cutoff-known supporting/contradictory evidence. Store such audit-only retrospective metadata separately and clearly label its different information time; the later M3-03 review input bundle must exclude it. Report representative warmup depth from that representative, separately from the initial-development warmup deficit.

Add a meaningful extension-invariance test: keep the prefix/representative/control records fixed, append or change later episode records, and require the cutoff review packet (and its stable binding) to remain unchanged. A separate full-interval inventory may change. Recheck all produced packets before ready_for_review. Keep 32 pending potential positives distinct from actual reviewed positives and report the complete observed shortfall honestly.

Pin this feedback and the independent audit evidence in the same M3-02 final manifest. No restart, duplicate dispatch, Codex-file edits, new sources, held-out price analysis, real reviews, policy tuning or M4 are authorized by this feedback.
