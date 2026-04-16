# EDA LangGraph Workflow

This document explains the expanded pre-modeling EDA step and how the current LangGraph routing works.

## Purpose

The EDA step is no longer a single `eda_analyst -> data_engineer -> ml_modeler` handoff.

It now does four things before modeling starts:

1. profile the raw dataset
2. collect EDA opinions from multiple downstream agents
3. iterate on a preparation plan between `eda_analyst` and `data_engineer`
4. approve the processed dataset before handing it to `ml_modeler`

## Prompt Architecture

The workflow is a hybrid:

- `Sequential / Pipeline` at the top level
- `Parallel / Fan-Out -> Fan-In` conceptually for the three EDA reviewers
- `Reflection / Self-Critique` for the `eda_analyst <-> data_engineer` loop
- `Planning + Execution` because `eda_analyst` proposes the prep plan and `data_engineer` executes it once approved

The current graph now implements the raw and processed review stages as true LangGraph fan-out/fan-in joins.

### Sequential / Pipeline

```text
+-------------+      +-------------------+
| raw dataset | ---> | eda_raw           |
| input only  |      | agent: eda_analyst|
+-------------+      +-------------------+
                          |
                          v
                    +-------------------+      +----------------------+
                    | eda_prep_plan     | ---> | data_engineer_execute|
                    | agent: eda_analyst|      | agent: data_engineer |
                    +-------------------+      +----------------------+
                                                       |
                                                       v
      +-------------------+ <------------------- +-------------------+
      | ml_modeler_handoff|                      | eda_processed     |
      | agent: ml_modeler |                      | agent: eda_analyst|
      +-------------------+                      +-------------------+
```

### Parallel / Fan-Out -> Fan-In

```text
+-----------+    +-------------------------+    +-------------------+
| eda_raw   | -> | ml_modeler_raw_review   | --\
| agent:    |    | agent: ml_modeler       |   \
| eda_analyst|   +-------------------------+   \
+-----------+                                   \
      |                                         \
      +-------> +-------------------------+ -----+--> +-------------------+
      |         | ml_reviewer_raw_review  | ----/     | eda_prep_plan     |
      |         | agent: ml_reviewer      |           | agent: eda_analyst|
      |         +-------------------------+           +-------------------+
      |                                         /
      +-------> +--------------------------------------+
                | business_stakeholder_raw_review      |--/
                | agent: business_stakeholder          |
                +--------------------------------------+
```

### Reflection / Self-Critique

```text
                    +-----------------------+
                    | eda_prep_plan         |
                    | propose / revise plan |
                    | agent: eda_analyst    |
                    +-----------------------+
                               |
                               v
                    +-----------------------+
                    | data_engineer_feedback|
                    | feasibility critique  |
                    | agent: data_engineer  |
                    +-----------------------+
                               |
                 revise <------+------ approved
                               |
                               v
                    +-----------------------+
                    | data_engineer_execute |
                    | agent: data_engineer  |
                    +-----------------------+
```

### Planning + Execution

```text
      +-------------------+        +-----------------------------+
      | raw review inputs | -----> | eda_prep_plan              |
      | inputs only       |        | planning / action selection|
      +-------------------+        | agent: eda_analyst         |
                                   +-----------------------------+
                                                  |
                                                  v
                                   +-----------------------------+
                                   | data_engineer_feedback      |
                                   | execution feasibility check |
                                   | agent: data_engineer        |
                                   +-----------------------------+
                                                  |
                                                  v
+-------------------+     <----------------- +-----------------------------+
| processed review  |                        | data_engineer_execute       |
| review stage only |                        | run approved plan once      |
+-------------------+                        | agent: data_engineer        |
                                             +-----------------------------+
```

## LangGraph Nodes

Current pre-modeling LangGraph nodes:

- `eda_raw`
- `ml_modeler_raw_review`
- `ml_reviewer_raw_review`
- `business_stakeholder_raw_review`
- `eda_prep_plan`
- `data_engineer_feedback`
- `data_engineer_execute`
- `eda_processed`
- `ml_modeler_processed_review`
- `ml_reviewer_processed_review`
- `business_stakeholder_processed_review`
- `eda_processed_approval`
- `ml_modeler_handoff`

## Unicode Diagram

```text
ENTRY
  |
  v
+-------------------+
| eda_raw           |
| profile raw data  |
| agent: eda_analyst|
+-------------------+
      |
      +-------> +-----------------------------+ -----------\
      |         | ml_modeler_raw_review       |            \
      |         | modeling implications       |             \
      |         | agent: ml_modeler           |              \
      |         +-----------------------------+              \
      |                                                       +--> +-------------------------------+
      +-------> +-----------------------------+ --------------/    | eda_prep_plan                 |
      |         | ml_reviewer_raw_review      |                   | synthesize prep plan          |
      |         | mathematical critique       |                   | agent: eda_analyst           |
      |         | agent: ml_reviewer          |                   +-------------------------------+
      |         +-----------------------------+                                 |
      |                                                                         +------ prep_approved = false -----+
      |                                                                         |                                   |
      +-------> +--------------------------------------+ ----------------------/                                    |
                | business_stakeholder_raw_review      |                                                           |
                | business realism review              |                                                           v
                | agent: business_stakeholder          |                                             +-------------------------------+
                +--------------------------------------+                                             | data_engineer_feedback        |
                                                                                                    | feasibility feedback          |
                                                                                                    | agent: data_engineer         |
                                                                                                    +-------------------------------+
                                                                                                                  |
                                                                                                                  +--------- back to eda_prep_plan
                                                                                                                  |
                                                                                                                  +------ prep_approved = true
                                                                                                                                 |
                                                                                                                                 v
                                                                                                    +-------------------------------+
                                                                                                    | data_engineer_execute         |
                                                                                                    | execute approved prep once    |
                                                                                                    | agent: data_engineer         |
                                                                                                    +-------------------------------+
                                                                                                                                 |
                                                                                                                                 v
                                                                                                    +-------------------------------+
                                                                                                    | eda_processed                 |
                                                                                                    | profile processed data        |
                                                                                                    | agent: eda_analyst           |
                                                                                                    +-------------------------------+
                                                                                                                                 |
                                                                                                    +-------------------------------+ ------------------\
                                                                                                    | ml_modeler_processed_review   |                   \
                                                                                                    | agent: ml_modeler             |                    \
                                                                                                    +-------------------------------+                    \
                                                                                                                                                          +--> +-----------------------------------+
                                                                                                    +-------------------------------+ ------------------/    | eda_processed_approval            |
                                                                                                    | ml_reviewer_processed_review  |                       | final pre-modeling approval       |
                                                                                                    | agent: ml_reviewer            |                       | agent: eda_analyst               |
                                                                                                    +-------------------------------+                       +-----------------------------------+
                                                                                                                                                                         |
                                                                                                    +------------------------------------------+ -----------/                                      +-- approved = false and iteration < max --> back to eda_prep_plan
                                                                                                    | business_stakeholder_processed_review    |                                                  |
                                                                                                    | agent: business_stakeholder              |                                                  +-- approved = true
                                                                                                    +------------------------------------------+                                                  |
                                                                                                                                                                                                    v
                                                                                                    +-------------------------------+
                                                                                                    | ml_modeler_handoff            |
                                                                                                    | final modeling context        |
                                                                                                    | agent: ml_modeler             |
                                                                                                    +-------------------------------+
                                                                                                                                 |
                                                                                                                                 v
                                                                                                                                END
```

## Conceptual Fan-In

The raw-data review stage is conceptually:

```text
                  /-> ml_modeler review ---------\
eda_raw -----------> ml_reviewer review -----------> eda_prep_plan
                  \-> business review -----------/
```

The processed-data review stage is conceptually the same:

```text
                     /-> ml_modeler review ---------\
eda_processed --------> ml_reviewer review -----------> eda_processed_approval
                     \-> business review -----------/
```

In the current graph, those three reviews execute as parallel branches and then fan back in to the `eda_analyst` node.

## Routing Rules

### Raw EDA

- `eda_raw -> ml_modeler_raw_review`
- `ml_modeler_raw_review -> ml_reviewer_raw_review`
- `ml_reviewer_raw_review -> business_stakeholder_raw_review`
- `business_stakeholder_raw_review -> eda_prep_plan`

### Prep Loop

- if `prep_approved = false`, route `eda_prep_plan -> data_engineer_feedback`
- `data_engineer_feedback -> eda_prep_plan`
- if `prep_approved = true`, route `eda_prep_plan -> data_engineer_execute`

This means:

- `eda_analyst` owns the plan
- `data_engineer` owns feasibility feedback and execution
- execution happens once per approved plan, not on every loop iteration

### Processed EDA

- `data_engineer_execute -> eda_processed`
- `eda_processed -> ml_modeler_processed_review`
- `ml_modeler_processed_review -> ml_reviewer_processed_review`
- `ml_reviewer_processed_review -> business_stakeholder_processed_review`
- `business_stakeholder_processed_review -> eda_processed_approval`

### Final Approval

- if `processed_eda_approved = true`, route to `ml_modeler_handoff`
- if `processed_eda_approved = false` and iteration budget remains, reopen the prep loop at `eda_prep_plan`
- if the iteration budget is exhausted, route to `END`

## State Handed To Modeling

When the workflow reaches `ml_modeler_handoff`, the state includes:

- processed dataset path
- processed EDA insights
- raw EDA reviews from:
  - `ml_modeler`
  - `ml_reviewer`
  - `business_stakeholder`
- processed EDA reviews from:
  - `ml_modeler`
  - `ml_reviewer`
  - `business_stakeholder`

This gives the modeling step approved data plus the full upstream reasoning context.

## Config Control

The preparation loop budget is controlled in:

- `config/workflows.yaml`

Current key:

- `workflows.eda_preparation.max_iterations`

That config controls how many times the workflow can reopen the prep loop before it stops.
