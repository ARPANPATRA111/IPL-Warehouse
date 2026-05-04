# Future Changes

This project already answers structured IPL questions well, but it still behaves like a polished statistics dashboard plus a natural-language SQL wrapper. That means many answers are still only marginally better than a good Google search. To beat normal search consistently, the product has to become an answer engine, not just a search surface.

## What Should Change

### 1. Move from "show me data" to "solve my intent"

Right now the system mostly returns charts, tables, and SQL answers. A stronger product should understand what the user is really trying to do.

Examples:

- "Who is the best death-over bowler against left-hand heavy batting lineups?"
- "What changed in KKR's chase strategy between 2023 and 2025?"
- "If the pitch is slow and dew is expected, what should the captain prefer after winning the toss?"

This requires:

- intent classification before SQL generation
- entity resolution for players, venues, franchises, eras, phases, match conditions, and roles
- answer templates tuned for scouting, commentary, fantasy, coaching, and fan analysis
- multi-step reasoning instead of one-shot SQL generation

### 2. Add a semantic retrieval layer on top of the warehouse

Google wins when users ask contextual questions. The warehouse wins when users ask structured questions. The project should do both.

Add a retrieval layer for:

- commentary text
- match reports
- squad news
- injury updates
- pitch reports
- toss trends
- player role descriptions
- expert analysis notes

Then answer with a hybrid engine:

- structured metrics from SQL
- unstructured evidence from retrieval
- a final grounded response with citations

This makes the answer richer than a standard search result because the system can combine facts, context, and explanation in one place.

### 3. Build opinionated expert workflows

A strong domain product wins by solving repeated user jobs better than the open web.

Recommended modes:

- Fan mode: quick answers, highlights, records, rivalry summaries
- Fantasy mode: matchup edges, recent role changes, venue fit, risk score
- Analyst mode: deeper comparisons, season-over-season change, clustering, trend explanation
- Team strategy mode: phase-wise tactics, bowling plan suggestions, toss scenarios, matchup exploitation
- Broadcaster mode: ready-to-say storylines with facts, anomalies, and historical context

Each mode should change the prompt scaffolding, chart defaults, explanation style, and the evidence included in the answer.

### 4. Add proactive intelligence instead of reactive search

Users should not always need to ask the perfect question.

Add:

- daily insight generation
- anomaly detection across players, venues, and teams
- "what changed since yesterday / last match / last season" summaries
- storyline surfacing before big fixtures
- personalized alerts for tracked players or teams

This is where the product starts to feel smarter than Google because it tells the user what matters before the user searches for it.

## Product Features Worth Building

### Explainable answers

Every important answer should include:

- the short answer
- why the system believes it
- supporting metrics
- the comparison baseline
- the exact evidence source
- confidence or uncertainty when data is thin

### Matchup simulator

Create a simulation layer that answers questions like:

- how a batting order change affects projected powerplay score
- how a venue shift changes expected win conditions
- how a spinner-heavy attack performs against a boundary-dependent batting unit

This is much harder than search and immediately more valuable.

### Player role graph

Track evolving player roles over time:

- anchor
- finisher
- powerplay aggressor
- middle-over enforcer
- death specialist
- control bowler
- wicket hunter

This lets the system answer role-based questions that plain scorecards cannot answer well.

### Match context engine

Model the game in phases, pressure states, and conditions instead of only totals.

Examples:

- batting under scoreboard pressure
- wickets in clusters
- chasing with dew
- strike rotation collapse in middle overs
- death-over execution under high required rate

That creates deeper, non-obvious answers.

## Data and Modeling Upgrades

### Expand the data model

Add datasets beyond ball-by-ball warehouse facts:

- playing XIs and squad availability
- batting handedness and bowling style metadata
- fielding impact and catch efficiency
- venue condition history
- toss and decision context
- weather and dew proxies
- player workload and recency
- injury or absence signals

### Create precomputed intelligence tables

The app will feel faster and smarter if important derived metrics are precomputed.

Recommended additions:

- player_form_snapshot
- venue_phase_profile
- team_matchup_profile
- pressure_state_metrics
- role_classification_history
- lineup_balance_snapshot
- narrative_highlights

These should be refreshed incrementally so first paint stays fast.

### Add embeddings and search indexes

For the retrieval layer, create:

- embeddings for commentary and article chunks
- player and team alias dictionaries
- hybrid BM25 + vector retrieval
- citation metadata with source, date, and competition context

## Technical Roadmap

### Near term

- Split the frontend into route-level chunks instead of keeping most views in one file
- Add server-side response compression and cache headers for stable reference endpoints
- Introduce materialized views for the homepage, team overview, and venue aggregates
- Add API timing instrumentation per endpoint so slow queries are visible immediately
- Add an async precompute job for leaderboard and narrative summary refreshes

### Mid term

- Build a semantic retrieval service beside the SQL assistant
- Add a metrics layer with named business definitions to keep answers consistent
- Introduce a job queue for heavy analysis, narrative generation, and scheduled insight production
- Add user sessions, saved workspaces, and personalized watchlists
- Add evaluation datasets for common cricket questions and track answer quality over time

### Long term

- Build a multi-agent analyst that can plan, query, retrieve, compare, and explain
- Add match prediction, matchup simulation, and scenario testing
- Support voice or conversational copilot workflows for analysts and broadcasters
- Add video and image grounding from match clips or scorecard graphics

## What Will Make This Better Than Google

Google is great at finding documents. This product can be better by doing the work the user would otherwise do manually.

To win, the system should:

- combine structured and unstructured evidence in one answer
- understand cricket-specific intent instead of generic keyword matching
- explain why the answer matters
- compare across seasons, roles, conditions, and pressure states automatically
- remember user context and preferences
- generate proactive insights instead of only returning links

If the product gets those six things right, it stops being a dashboard and becomes an IPL intelligence system.

## Suggested Success Metrics

- Time to first meaningful answer
- Percentage of prompts answered without manual reformulation
- Percentage of answers with at least one citation and one supporting metric
- User return rate for saved players, teams, and rivalries
- Number of proactive insights opened per user per week
- Human evaluation score for usefulness versus a Google search result page