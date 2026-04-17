# Demo Narration Script — Talking Points

**Demo:** Demo Runtime Viewer — EDA Workflow Visualization  
**Presenter:** Sean Lewis  
**Date:** April 17, 2026

Three versions below: elevator pitch, full walkthrough, and anticipated Q&A.

---

## Version 1: 2-Minute Elevator Pitch (If Rushed)

> "What you're looking at is a live replay of a real machine learning workflow. We're building a multi-agent data science platform that orchestrates specialized agents — exploratory analysis, data engineering, model development — to automate the end-to-end ML pipeline.
>
> This demo shows you the **preparation stage**: raw data comes in, an EDA agent profiles it, engages a data engineer to draft a prep plan, collects feedback from downstream reviewers, executes the approved transformations, and hands off cleaned data to the modeling stage.
>
> Watch the runtime visualization. The orange indicator shows active work; green means done. The whole flow — including three parallel reviewer agents in production — completes in about a minute, which is critical for keeping iteration cycles fast.
>
> And notice: all of this runs autonomously. No manual tweaking between steps. That's the promise of multi-agent orchestration in data science."

**Runtime:** ≈ 90 seconds.

---

## Version 2: 4-Minute Full Walkthrough (Recommended)

### Page 1: Configuration (30 seconds)

> "Let's start with the experiment setup. On the left side, you see the data parameters: we're working with a dataset of **500,000 rows and 19 features** — a classification problem where about 27% of samples are the positive class. That's a typical imbalance you'd find in real-world datasets.
>
> On the right, the hyperparameter search configuration: **5-fold cross-validation, four ML algorithms**, a budget of **100 trials**, and a **30-minute timeout** to keep things reasonable. These are the knobs that control the modeling stage later on.
>
> [Click RUN] Now let's move to the raw data."

---

### Page 2: Input Preview (45 seconds)

> "Here's what the raw dataset looks like — 500k rows, 19 columns. The metrics tell the story: we have **13 numeric features, 5 categorical features, and about 2% missing data** scattered across several columns.
>
> The class breakdown is interesting: **27% positive, 73% negative**. That imbalance matters downstream — the data engineer will account for it when we design the prep plan.
>
> The table below shows a sample of 10 random rows so you can see the feature mix and data types.
>
> [Click CONTINUE] Now we're going to watch the workflow execute in real time."

---

### Page 3: Runtime Replay (≤ 90 seconds at 1.5× speed — the main event)

> "Here comes the EDA workflow. Watch the orchestrator band at the top. It's going to move through five states:
>
> **STARTING** — system initializes.
>
> **EDA RUNNING** — this is the most interesting part. The EDA agent profiles the raw data: generates histograms, correlation matrices, univariate summaries, and flagged problems like high cardinality or missing patterns. In parallel — and you can't see it in this demo because we recorded a simplified path — three reviewer agents would be analyzing the EDA insights from different angles: the ML Modeler looks at modeling implications, the ML Reviewer checks mathematical rigor, the Business Stakeholder asks 'does this make sense for the business?'
>
> **HANDOFF** — the reviews feed back to the EDA agent, who synthesizes a **data preparation plan**. The prep plan is a structured sequence of transformations: drop low-variance features, impute missing values, encode categories, scale numerics, and so on.
>
> **DATA ENGINEER RUNNING** — now the data engineer takes the plan. They provide feasibility feedback — 'yes, we can do this in under 10 seconds' — and then execute the transformations. The engine chains pandas and scikit-learn operators, applies the plan once, and produces the **processed dataset**.
>
> **COMPLETE** — workflow done, data ready for modeling.
>
> [If running long, mention the speed selector:] The replay is running at 1.5× speed by default — keeps things snappy. If you want to see detail, I can slow it to 1×. If we're tight on time, 2× works too.
>
> [Watch replay complete and auto-advance.]"

---

### Page 4: Output & Summary Drawer (60 seconds)

> "The processed dataset is ready. At the top, you see the first 10 rows — notice how clean the data is now. Missing values imputed, categories encoded as numeric, everything normalized to the same scale.
>
> The four metric cards below give you a summary: **row count stayed the same (500k), column count dropped slightly** as we removed low-variance features, **missing data is now zero**, and the **whole workflow took about 40 seconds**.
>
> Now let's look inside the workflow. Each of these seven agent cards on the left — Orchestrator, EDA, Data Engineer, and the reviewers — holds their contribution. Click on any one to see the details.
>
> [Click Orchestrator.] This pane shows the workflow timeline. Timestamps, the sequence of node executions, and the final state. Think of it as the black box log.
>
> [BACK. Click EDA.] This is the EDA report: the profiling insights that drove the prep plan. Distributions, correlations, and flagged issues.
>
> [BACK. Click Data Engineer.] And here's the transformation summary: what transformations we applied, in what order, and validation that each one succeeded.
>
> [BACK. Click ML Modeler.] This one shows a SCRIPTED badge. In a real production run, the ML Modeler agent would execute in parallel during the initial EDA phase and produce live insights about model implications. For the demo, we show a representative output so you understand the structure.
>
> [BACK. And that's the workflow.] In production, all three reviewers would execute in parallel, and the loop might iterate if feedback is critical enough to revise the prep plan. But for the demo, we highlighted the critical path: EDA profiling, data engineering execution, and handoff to modeling."

---

## Version 3: Anticipated Q&A

### Q: "Why are some panes marked SCRIPTED?"

> "Good question. The demo recording captures a simplified 2-node execution: EDA and Data Engineer. In production, the ML Modeler, ML Reviewer, and Business Stakeholder agents would fire in parallel during the initial EDA phase and produce live outputs based on the real data and the real EDA insights.
>
> For the demo, we pre-populated those panes with representative content so you can visualize the full approval stage without the overhead of running 13 nodes and waiting for multiple LLM calls. The structure and layout are real — the content is illustrative."

---

### Q: "How many LLM API calls happen per demo run?"

> "The recorded run makes about 4 API calls to OpenAI:
>
> 1. EDA Analyst profiles the raw data.
> 2. EDA Analyst drafts the prep plan based on the raw reviews.
> 3. Data Engineer provides feasibility feedback.
> 4. If the plan needs tweaking, one more call to refine it.
>
> Total cost is roughly $0.02–0.05 per run, depending on token counts.
>
> The full 13-node workflow with all three live reviewers would be about 12 calls and closer to $0.10–0.20. We're monitoring those costs closely — part of the value prop is that the agents are cheaper and faster than manual analysis, but we're also exploring caching and prompt optimization to drive costs down further."

---

### Q: "Can you run this against our real dataset?"

> "Absolutely. The `demo_recorder` is a CLI tool:
>
> ```bash
> uv run python -m multi_agent_ds.orchestration.demo_recorder \
>   --parquet <your-file.parquet> \
>   --output <output.json>
> ```
>
> Point it at your CSV or Parquet, wait ~60 seconds for the workflow to run, and you get a fresh recording. The viewer adapts automatically — all the row counts, column names, stats, and EDA insights pull from your data. The UI structure stays the same; the data updates.
>
> We've tested it on datasets up to 1M rows. Anything bigger and the EDA agent might need more time, but it scales."

---

### Q: "What if the replay takes longer than 90 seconds?"

> "The replay speed is configurable. Default is 1.5× — a good balance between seeing state transitions and keeping pace. If you're tight on time during the presentation, switch to 2×. If someone asks for detail, drop to 1×.
>
> Also: the replay duration depends on the recorded JSON, which comes from the actual LLM latency. On a slow network or during API congestion, the recording might take longer. But the demo is designed to run in <60 seconds on a typical laptop with normal API response times."

---

### Q: "What happens if Streamlit crashes during the demo?"

> "We have a backup. There's a screen recording of the full 4-page flow at `project_planning/design_plans/2026-04-16-demo-runtime-viewer/backup.mov`. If anything goes wrong with the live app, I can play the video instead. The content is identical — you'll see the same workflow, same UI, same agent outputs."

---

### Q: "Can the workflow loop back and refine the prep plan?"

> "Yes. The Data Engineer can provide feedback that the current plan isn't feasible (e.g., 'this transformation is too slow'). When that happens, the workflow loops back to the EDA agent to revise the plan. The system will iterate up to a configured max (usually 3–5 times) before giving up.
>
> In the demo, the plan was approved on the first try, so you don't see a loop. But in production, that flexibility is key — it means the system can adapt when initial plans don't work out."

---

### Q: "How does this integrate with the rest of your ML pipeline?"

> "This is the pre-modeling stage. After the Data Engineer hands off the processed dataset, it flows into the modeling orchestrator, which runs algorithm selection, hyperparameter tuning, and cross-validation. That's a separate agent system that we'll demo separately.
>
> The point of splitting EDA and modeling is that you can run the prep stage independently and cache the results. If your dataset doesn't change, you reuse the same processed data for multiple modeling experiments, saving compute and time."

---

### Q: "What's the difference between the EDA agent and the Data Engineer?"

> "EDA agent (eda_analyst in the workflow) is the analyst. They profile the data, generate insights, propose the prep plan, and synthesize feedback from reviewers.
>
> Data Engineer (data_engineer in the workflow) is the executor. They don't propose; they critique and execute. Their job is to make sure the plan is *feasible* — that the transformations can run in acceptable time and don't break downstream modeling.
>
> The two work together: EDA proposes, Data Engineer validates, EDA refines if needed. This separation of concerns keeps the system modular and testable."

---

### Q: "Is all of this code-generated or manually written?"

> "The **orchestration system** — the workflow graph, the agent prompts, the routing logic — is hand-written by us. The orchestrator uses LangGraph, a state machine framework for multi-agent workflows.
>
> The **agent outputs** — the EDA insights, the data transformations, the feedback — are LLM-generated. We prompt the models (OpenAI GPT-4 in this case) with domain context and let them produce the analysis.
>
> So it's a hybrid: the structure and rules are code, the content is AI-generated. That's why this is a 'multi-agent data science platform' rather than a pure AI system — we need both deterministic orchestration and creative problem-solving."

---

## Closing

> "That's the demo. The takeaway: **multi-agent orchestration can automate and accelerate the data preparation stage**, which is typically 40–60% of ML project time. This system runs in ~60 seconds and produces audit trails, so you know exactly what transformations were applied and why.
>
> Questions?"

---

## Timing Targets

| Segment | Duration | Notes |
|---------|----------|-------|
| Page 1 (Config) | 30 s | Scan the config cards, click RUN. |
| Page 2 (Input) | 45 s | Explain data shape, pill metrics, sample rows. Click CONTINUE. |
| Page 3 (Replay) | 45–90 s | Watch orchestrator cycle at 1.5×–2×. Total depends on recorded duration. |
| Page 4 (Output) | 60 s | Walk through 7 agent cards (click, read, BACK). |
| **Total** | **3:00–4:00** | Buffer: 90 s. Soft target: 3:30. |

**Pro tip:** If you're behind after Page 2, skip some agent cards on Page 4 or bump replay to 2×. The critical cards are Orchestrator (shows timeline), EDA (shows insights), and Data Engineer (shows transformations). ML Modeler, ML Reviewer, and Business Stakeholder are nice-to-have for showing the full approval flow, but you can skim them if time is tight.
