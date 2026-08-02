# Proof-cycle contradiction regression

The validator must reject both of these mutations:

1. A cycle-level `research_verdict` that differs from the verdict of
   `tested_operator_id`.
2. A `tested_operator_id` repeated in `supporting_operator_ids`.

The canonical ledger remains unchanged. The regression runner creates temporary
mutated copies so user verdicts and promotion progress can never be overwritten.
