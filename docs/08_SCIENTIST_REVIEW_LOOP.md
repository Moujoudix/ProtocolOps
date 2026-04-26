# Scientist Review Loop

## Purpose

The review layer turns ProtocolOps from a one-shot planner into a review-aware planning workflow.

Instead of treating generated plans as final, ProtocolOps treats them as:

- review-ready experiment plans
- operational plans for expert review

Scientist feedback is captured in a structured form and can be reused in future generations for similar experiment types.

## Review sessions

A review session is the top-level record of scientist feedback on a run.

Stored fields include:

- `run_id`
- `reviewer_name`
- `summary`
- `review_state`
- timestamps

Review states currently supported:

- `generated`
- `reviewed`
- `revised`
- `approved_for_proposal`

## Review items

Each review session contains one or more review items.

Each review item stores:

- target type
- target key
- action
- comment
- replacement text
- optional confidence override

Current target types include:

- `section`
- `protocol_step`
- `material`
- `budget_item`
- `timeline`
- `validation`
- `risk`

Current actions include:

- `approve`
- `reject`
- `edit`
- `replace`
- `unrealistic`
- `missing_dependency`
- `comment`

## Structured corrections

The review layer is intentionally structured rather than freeform-only. This allows ProtocolOps to:

- identify what part of a plan was corrected
- identify what kind of correction was made
- rank previous feedback for reuse
- show a legible comparison between baseline and revised plans

## Persisted review memory

Review sessions and review items are stored in SQLite through SQLModel tables:

- `ReviewSession`
- `ReviewItem`

They are tied back to runs and can be retrieved later for similar hypotheses.

## Retrieval ranking for future generation

Before generating a new plan, ProtocolOps ranks prior runs using:

- preset match
- domain-route match
- overlap in parsed key terms
- review-state strength

Only generation-ready prior runs are considered. The current retrieval logic prefers the strongest similar run rather than mixing many weak examples.

## Prompt-time reuse

Retrieved review memory is injected into the plan-generation prompt as structured prior corrections.

This means:

- the planner can prefer previously reviewed corrections
- a revised plan can visibly differ from the baseline
- the system can improve consistency without claiming model training

## Memory-applied visibility

When review memory influences a plan:

- applied memory is attached to the generated plan payload
- the frontend surfaces it in the plan workspace
- revised plans can be compared against their baseline using the comparison endpoint

## What is not implemented

The current review loop is **not**:

- model fine-tuning
- a training pipeline
- autonomous scientific learning
- multi-reviewer collaboration
- a formal approval workflow across teams

Accurate wording:

- review memory is prompt-time retrieval of structured scientist corrections

Inaccurate wording:

- the model has been fine-tuned
- the system trains itself from scientist feedback

