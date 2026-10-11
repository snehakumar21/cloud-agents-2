# Multi-Agent AI for Cloud Resource Allocation

A university case-study prototype: four cooperating software agents monitor **simulated** cloud servers, forecast CPU overload, place and migrate workloads, and optimize utilization and **estimated** cost.

> **What this is:** a rule-based multi-agent prototype with lightweight predictive analytics (a least-squares linear trend).
> **What this is not:** there is no LLM, no reinforcement learning, no machine-learning model, and no real AWS or any other cloud. All servers, jobs and prices are simulated in Python memory.

## Folder structure

```
cloud-agents/
  README.md
  backend/
    requirements.txt
    app/
      config.py        thresholds and policy numbers (all in one place)
      models.py        Job and Server
      scenarios.py     3 deterministic seeded scenarios
      state.py         shared in-memory cloud + the only functions that change it
      agents.py        Monitoring, Prediction, Allocation, Optimization agents
      orchestrator.py  monitor -> predict -> allocate -> optimize -> record
      main.py          FastAPI app + CORS
    tests/test_agents.py
  frontend/
    package.json, vite.config.js, index.html
    src/ main.jsx, App.jsx, api.js, styles.css, components/*.jsx
```

## Setup and run

Requirements: Python 3.10+ and Node.js 18+.

### Terminal 1: backend

**macOS / Linux**
```bash
cd cloud-agents/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Windows (PowerShell)**
```powershell
cd cloud-agents\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
(If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope Process Bypass` first, or use `venv\Scripts\activate.bat` in cmd.)

### Terminal 2: frontend
```bash
cd cloud-agents/frontend
npm install
npm run dev
```

### URLs
- Dashboard: http://localhost:5173
- API: http://127.0.0.1:8000 (interactive docs at http://127.0.0.1:8000/docs)

### Run the logic tests (backend only, no extra packages)
```bash
cd cloud-agents/backend
python -m unittest discover -s tests -v
```

### What CORS means here
The page is served from `http://localhost:5173` and calls the API on `http://127.0.0.1:8000`. A browser treats a different host or port as a different *origin* and blocks the response unless the API says it is allowed. `main.py` adds FastAPI's `CORSMiddleware` allowing the two Vite dev origins (`localhost:5173` and `127.0.0.1:5173`). If you change the frontend port, add the new origin in `main.py`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/state` | Servers, jobs, KPIs, chart history, latest before/after |
| GET | `/api/agents` | Each agent's latest observation, action, recommendations, JSON output |
| GET | `/api/logs` | Decision log (agent, decision, explanation, result) |
| POST | `/api/scenario/{normal\|spike\|underused}` | Load a seeded scenario |
| POST | `/api/step` | Run one orchestrated cycle |
| POST | `/api/reset` | Reload the current scenario's seeded start |

All state changes happen inside one lock, so a request never sees a half-finished cycle.

## How the system works

**Capacity arithmetic.** Each server is 16 vCPU / 32 GB RAM. Usage is always `baseline + sum(assigned jobs)`, never an independent random percentage. Jobs are indivisible. A tiny seeded background CPU wobble (at most 0.15 vCPU) is added to *observed* CPU only, so the chart moves a little; every capacity decision uses the exact job arithmetic. The only functions that change the cloud re-check capacity and raise an error rather than exceed it.

**The four agents** (each returns a structured JSON "envelope": observation, recommendations, action results):

| Agent | Rule |
|---|---|
| Monitoring | Records a metric sample each cycle. Flags `high` (CPU >= 75% or RAM >= 85%), `overloaded` (CPU >= 90% or RAM >= 92%), `underutilized` (CPU < 30% and RAM < 40%). Never changes anything. |
| Prediction | Least-squares line through the last 5 CPU samples, extended 2 cycles ahead, clamped to 0-100%. Fewer than 4 samples means it reports *insufficient history* and produces no number. Forecast >= 85% is "predicted overload". |
| Allocation | Places pending jobs and relieves hotspots. A destination must be powered on and stay within 85% CPU **and** 85% RAM. Among feasible options it picks the lowest projected maximum utilization across source and destination. At most 2 migrations per cycle, a job cannot move again for 3 cycles, and a move must lower the maximum by at least 2 points. If nothing is feasible it logs exactly why. |
| Optimization | **Scale out** (power on a standby server) only when Allocation reports it could not safely fix pressure. **Consolidate** (drain and power off) only when calm, no overload is forecast, at least 2 servers stay on, and every job of the candidate fits elsewhere under stricter limits (CPU 70%, RAM 75%). Scaling actions share a 3-cycle cooldown. Load imbalance is reported as a recommendation only. |

**Cost** is a made-up flat $0.40/hour per powered-on server ($0 when off). It is not AWS pricing.

**Seeded warm-up history.** Each scenario starts with 6 simulated past samples (labelled -5 to 0, generated from a fixed seed, ending exactly at the starting state) so the Prediction Agent can forecast on cycle 1. A server powered on mid-run has no history yet and the agent says so.

**Cooldowns and anti-oscillation.** Job migration cooldown (3 cycles), shared scale cooldown (3 cycles), a minimum of 2 active servers, and consolidation limits stricter than placement limits. The test suite runs 30 cycles of every scenario and checks there is no flip-flopping.

## Test walkthroughs (real numbers from the seeded scenarios)

Percentages include the small background wobble, so the last decimal may differ by about 1 point from the pure job arithmetic. Same scenario button means same numbers every time.

### 1. Normal Load (seed 11)
Start: Server 1 49% CPU, Server 2 58%, Server 3 41%; cost $1.20/hour; one pending job `nightly-report` (2 vCPU, 4 GB).
1. **Run One Cycle.** Monitoring: all healthy. Prediction: flat trends, no overload. Allocation places `nightly-report` on Server 3 (lowest projected max, about 54% CPU / 52% RAM). Optimization: holds, because allocation just changed something.
2. **Run One Cycle again.** Allocation: no allocation needed. Optimization: no server is under 30% CPU, so no consolidation candidate.
Expected: no migrations, no scaling, cost stays $1.20.

### 2. Traffic Spike (seed 42)
Start: Server 1 93.8% CPU / 75.0% RAM (4 jobs), Server 2 48.8% / 65.6% (3 jobs), Server 3 powered off. Cost $0.80/hour.
1. **Run One Cycle.**
   - Monitoring: hotspot on srv-1 (about 93% CPU, overloaded).
   - Prediction: rising about +5.7 points per cycle, forecast clamped to 100%, predicted overload.
   - Allocation: moves `img-resize` srv-1 to srv-2 (lowest projected max, 78.8%). Then logs *no safe migration*: `checkout-api` needs 4 vCPU but Server 2 has 3.4 free under the 85% limit; `ml-inference` needs 8 GB but Server 2 has too little RAM; Server 3 is powered off.
   - Optimization: scales out and powers on Server 3. Cost rises $0.80 to $1.20/hour (shown honestly).
   - Before/After: hottest server CPU about 93.8% to 77.9%; average CPU falls partly because a third server is now counted.
2. **Run One Cycle again.** Server 1 is still high (about 78%). Allocation moves `checkout-api` to Server 3. Hottest server is now Server 2 at about 64%. Server 3 forecast says *insufficient history* (only 1-2 samples), not a made-up number.
3. Further cycles: no changes. Consolidation does not undo the scale-out because Server 3 is above 30% CPU and the scaling cooldown applies.

### 3. Underutilization (seed 77)
Start: Server 1 31% CPU, Server 2 24%, Server 3 16%; cost $1.20/hour.
1. **Run One Cycle.** Monitoring: low utilization on Server 2 and Server 3. Prediction: no overload. Allocation: nothing to do. Optimization: all of Server 3's jobs fit elsewhere under the 70% CPU / 75% RAM limits, so it moves `batch-etl` to Server 1 and `cron-jobs` to Server 2 and powers Server 3 off.
2. Before/After: cost $1.20 to $0.80 per hour (saves $0.40). Average CPU *rises* (about 24% to 32%) and the log says so: the remaining servers run hotter, that is the trade-off.
3. Further cycles: Optimization reports the minimum of 2 active servers is reached and stops.
(If the jobs did not fit, the log would say "Consolidation blocked" and no saving would be claimed. A unit test covers this.)

## 90-second faculty demo script

- **0:00-0:10** "This is a simulated cloud with three servers. It is a rule-based multi-agent system with a simple trend forecast, not an LLM or real AWS."
- **0:10-0:25** Click **Traffic Spike**. "Server 1 is at about 94% CPU and Server 3 is powered off. Each bar is baseline plus individual jobs, so the numbers come from real capacity arithmetic. The red tick is the 85% placement limit."
- **0:25-0:55** Click **Run One Cycle**. "Monitoring Agent observed and flagged the hotspot. Prediction Agent fitted a linear trend over recent samples and forecast overload. Allocation Agent moved one job to Server 2, checking CPU and RAM, and explains why the other jobs could not move. Optimization Agent saw that allocation was stuck and powered on the standby server."
- **0:55-1:10** Point at **Before and after**. "The hottest server dropped from about 94% to 78%, and cost rose from $0.80 to $1.20 per hour. It does not claim every metric improves."
- **1:10-1:25** Click **Run One Cycle** once more, then **Underutilization**, then Run One Cycle. "Now Optimization drained a nearly idle server and powered it off, cutting simulated cost by $0.40 per hour, only because every job fit elsewhere."
- **1:25-1:30** "Each agent's structured JSON output is in its panel. Thank you."

## Likely viva questions

**1. Why call this multi-agent and not just four functions?**
Each agent has its own responsibility, observes the shared environment, keeps no hidden access to other agents' internals, and communicates only through structured outputs (observations, recommendations, action results). The orchestrator runs a sense-predict-decide-act loop with explicit policies and state (cooldowns, history). The agents are simple and rule-based, so we describe it honestly as a rule-based multi-agent prototype; one agent does call the Allocation Agent's planning function ("can this server be drained?") as a service request.

**2. How does prediction work and how reliable is it?**
It is ordinary least-squares linear regression over the last 5 CPU samples, extrapolated 2 cycles and clamped to 0-100%. It assumes the recent trend continues, so it cannot anticipate sudden changes, seasonality or bursts. With fewer than 4 samples it refuses to forecast. The demo's first six points are seeded simulated warm-up data. It is lightweight predictive analytics, not machine learning.

**3. How do you guarantee capacity is never exceeded and avoid thrashing?**
Utilization is derived from jobs, and all place/migrate calls re-check CPU and RAM and raise an error instead of exceeding capacity; the orchestrator also asserts invariants after every cycle and tests run 30 cycles per scenario. Placement uses an 85% limit (leaving headroom), consolidation uses a stricter 70%/75%, migrations need a minimum 2-point gain, jobs have a 3-cycle migration cooldown, scaling has a shared 3-cycle cooldown, and at least 2 servers stay on.

## Limitations

- Everything is simulated in memory; restarting the backend resets it. Single user, no persistence, no authentication.
- Job demand is fixed; only a tiny seeded CPU wobble varies, so there is no realistic traffic generation.
- Prediction is a straight-line fit with seeded warm-up history; it is not validated against real workloads.
- Greedy one-job-at-a-time placement, not an optimal bin-packing solver; it can leave a server a little hot when no single move qualifies.
- Migration is instantaneous and free (no live-migration cost, network or downtime modelling).
- Cost is a flat made-up rate, not real cloud pricing, and ignores storage, network and licensing.
- Only CPU and RAM are modelled, with identical servers. No disk, network, affinity or SLA rules.
- The frontend and the FastAPI layer were written but could not be executed in the authoring sandbox (no internet to install packages); the agent logic and its 11 unit tests were run there. If anything fails on first run, check the browser console and the backend terminal.
