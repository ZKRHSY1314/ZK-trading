# M3-03 diagnostic wording clarification

Same task and unchanged verdicts. In D007, no PositionState was supplied, so no_trade/no_open_position_state is a result under absent declared position input. It does not establish that an actual account held nothing or that no fill occurred. Correct the sentence "no_trade therefore records that nothing was held or filled" to distinguish missing declared state from verified real-world absence. No account access is required or authorized.

Some diagnostic bindings mention later C-case roles or later markup/failed-markup states for the symbol. These are collection navigation references, not facts available at the diagnostic cutoff. Keep any such references explicitly in a separate retrospective collection cross-reference field, excluded from diagnostic support/evidence and label judgment, or omit them from the final diagnostic assessment. The named diagnostic semantics should rely only on its embedded current core. Do not inspect additional data or revise the frozen core.

Preserve original diagnostic notes by hash and append the clarification. Include the corrected wording and original-note link in final serialization/report, preserve the source in the manifest, finish validation and ready_for_review, then stop. No new task or consensus request.
