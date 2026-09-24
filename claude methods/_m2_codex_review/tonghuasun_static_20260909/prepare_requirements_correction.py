"""Prepare reviewable Markdown corrections without overwriting Claude's files."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
METHODS = HERE.parents[1]


def replace_once(text, old, new):
    assert text.count(old) == 1, f"Expected one match: {old!r}"
    return text.replace(old, new, 1)


map_name = "M2_REMAINING_DEPENDENCY_DECISIONS.md"
draft_name = "M2_BOUNDARY2_EVIDENCE_REQUIREMENTS_DRAFT.md"
originals = {name: (METHODS / name).read_bytes() for name in (map_name, draft_name)}
for name, raw in originals.items():
    assert raw == (HERE / ("received_" + name)).read_bytes(), "Delivery changed since snapshot"

mapping = originals[map_name].decode("utf-8").replace("\r\n", "\n")
mapping = replace_once(mapping,
    "**I** — no isolation or constraint for those paths exists for a staging run",
    "**I** — no isolation or constraint for those paths was established in the inspected code for the intended staging run; this is not a repository-wide absence claim")
mapping = mapping.replace("per-symbol expected keys for the **49** unobserved instruments",
    "observed source coverage and historical identity for the **49** unobserved instruments")
# Revision 3/4 entries remain historical. Supersede their claims in a dated note.
mapping = replace_once(mapping,
    "candidate **does** exist and is now in progress under the current continuous offline\nauthorization: the **D13 requirements draft**",
    "candidate **does** exist and has now been delivered under the current continuous offline\nauthorization, with Codex's bounded residual corrections recorded: the **D13 requirements draft**")
mapping += "\n## Codex takeover correction — 2026-09-09\n\n" \
    "The requirements analysis has been delivered and reviewed with bounded residual corrections. " \
    "Earlier revision entries describe their historical state. Unknown source coverage does not " \
    "make the eligible-key contract unknown: manifest, listing dates and calendar define it, with " \
    "unknown listing dates retained as UNRESOLVED under the existing rules. The 49-instrument " \
    "gap is observational coverage and historical identity, not permission to shrink that contract. " \
    "A revised request can already state contractual expected keys and mark source coverage/identity " \
    "as unobserved; acquiring those 49 instruments first is not a prerequisite to drafting the request. " \
    "Those observations are outputs of later authorized acquisition and acceptance. " \
    "The user has assigned subsequent M2 work to Codex and suspended further Claude delegation. " \
    "No capture, policy, eligibility, staging, production or service permission is granted by this correction.\n"

draft = originals[draft_name].decode("utf-8").replace("\r\n", "\n")
draft = replace_once(draft,
    "symbols in the approved population are **unobserved**, so their expected first dates are\n  **unknown**, and a rev. 3 must express them as *unknown until observed*, per symbol.",
    "symbols in the approved population are **unobserved**, so their first served dates, observed\n  coverage and historical identity remain **unknown**. Their expected eligible keys still come\n  from (c), the manifest/listing/calendar contract; unknown listing dates retain UNRESOLVED.")
draft = replace_once(draft,
    "* **Unknown must not be padded.** An unobserved symbol's expected keys cannot be filled in\n  by analogy with `BJ920000`, and a later missing observation must not be accepted as\n  explained merely because this one symbol behaved this way.",
    "* **Unknown availability must not be padded.** Do not infer served coverage or historical\n  identity by analogy with `BJ920000`. Expected eligible keys remain contractual; a later\n  missing observation is not explained by this one symbol's behaviour.")
draft = replace_once(draft,
    "* **Per-symbol expected keys for the 49 unobserved instruments** — expressible today only as\n  the (c) contract from manifest, listing dates and calendar; the served coverage against it\n  is unobserved.",
    "* **Observed source coverage and historical identity for the 49 unobserved instruments**\n  remain unknown. Their expected eligible research/warm-up keys are already defined by the\n  (c) manifest/listing/calendar contract; unknown listing stays UNRESOLVED under existing rules.")
draft = replace_once(draft, "other 51 instruments", "other 49 instruments")
draft = replace_once(draft,
    "purpose would be to restate it. What a later operational request would still have to\ncontain, and cannot yet, is named here so the blockage is explicit rather than deferred:",
    "purpose would be to restate it. A revised request can already state the contractual\nexpected keys and mark served coverage/historical identity as unobserved; collecting the\n49 instruments is not a prerequisite to drafting that request. Those observations are\noutputs of later authorized acquisition and acceptance. The following separates those\nfuture observations from still-undecided operational details:")
draft = draft.replace(hashlib.sha256(originals[map_name]).hexdigest(),
    hashlib.sha256(mapping.encode("utf-8")).hexdigest())
draft += "\n## Codex takeover correction — 2026-09-09\n\n" \
    "The current-body corrections above supersede residual claims in the historical revision record: " \
    "the unobserved population is 49, and the missing evidence is served coverage and historical " \
    "identity, not the definition of expected eligible keys. BQ-R2's unverified audit-only state " \
    "and all inherited M2 gates remain unchanged. These textual corrections do not establish " \
    "data-source capability, close P1/U-6, or authorize capture or a staging backfill.\n"

corrected = {map_name: mapping, draft_name: draft}
patch = []
for name, text in corrected.items():
    before = originals[name].decode("utf-8").replace("\r\n", "\n")
    patch.extend(difflib.unified_diff(before.splitlines(True), text.splitlines(True),
        fromfile="a/claude methods/" + name, tofile="b/claude methods/" + name))
(HERE / "requirements_correction.patch").write_text("".join(patch), encoding="utf-8")
receipt = {"status": "prepared_not_applied", "originals_untouched": True,
    "before_sha256": {n: hashlib.sha256(b).hexdigest() for n, b in originals.items()},
    "proposed_utf8_lf_sha256": {n: hashlib.sha256(t.encode("utf-8")).hexdigest() for n, t in corrected.items()}}
for name, original in originals.items():
    assert (METHODS / name).read_bytes() == original
(HERE / "requirements_correction_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, indent=2))
