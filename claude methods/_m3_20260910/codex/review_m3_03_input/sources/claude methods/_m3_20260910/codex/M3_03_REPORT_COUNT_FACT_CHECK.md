# M3-03 report count correction

The working report section5 says 20/32 prefixes have a deciding margin below0.01. Codex recomputed all96 embedded prefix records directly using your stated criterion: min across the three members of (0.65-position250), (0.09-ma_spread), and (0.25-return120), followed by strict margin<0.01. The actual union is **15/32**, not20/32, so "most episode starts" is also unsupported by this statistic.

* Position: C021, C025, C027, C029, C032 (5).
* Spread: C001, C007, C008, C014, C015, C016, C019, C028 (8).
* return_120: C026, C030 (2).

The sets are disjoint. For example C010's minimum position margin is0.025342465753424914, and C031's minimum return120 margin is0.010674157303370846: neither meets your stated <0.01 criterion. C019 has a thin spread but not a thin return120 margin; C026 has a thin return120 margin but not a thin position margin.

Also reconcile the negative narrative groups: the listed advance/rebound negatives C002,C003,C006,C008,C009,C018,C019 number7, while C004,C012,C013,C016,C020,C022,C032 are7 break/decline/possible-lock negatives. The report currently says8 advances and6 breaks while listing7 in each grouping. These groups total the unchanged14 negative verdicts.

Preserve the working report as superseded draft history, correct the summary counts and membership lists, and include a small executed arithmetic check or equivalent source-backed calculation in final validation. This does not request any verdict change, confidence threshold change, new data or policy change. Same task, finish the already requested effective serialization and final report, deliver ready_for_review and stop.
