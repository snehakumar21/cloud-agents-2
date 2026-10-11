"""
agents.py - the four agents.

Each agent is a plain Python class with a run() method. It receives the shared
CloudState plus the structured JSON-style dictionaries produced by earlier agents,
and returns its own "envelope":

    {
      "agent": "Monitoring Agent", "cycle": 3,
      "observation": {...},        # what it saw (structured data)
      "recommendations": [...],    # what it suggests
      "actions": [...],            # what it actually changed (action results)
      "observation_text": "...",   # one-line human summaries for the dashboard
      "action_text": "..."
    }

This is a RULE-BASED multi-agent prototype. No LLM, no machine learning, no real cloud.
The only "prediction" is a least-squares straight line over recent samples.
"""
from . import config as C
from .state import classify


def _envelope(name, cycle, observation, recommendations, actions, observation_text, action_text):
    return {"agent": name, "cycle": cycle, "observation": observation,
            "recommendations": recommendations, "actions": actions,
            "observation_text": observation_text, "action_text": action_text}


# =============================================================================
# 1. MONITORING AGENT - looks, records, flags. It never moves anything.
# =============================================================================
class MonitoringAgent:
    name = "Monitoring Agent"

    def run(self, state):
        state.record_sample()                       # store this cycle's metrics
        observed, hot, low = [], [], []
        for s in state.servers:
            status = classify(s)
            flags = []
            if status == "off":
                flags.append("powered_off")
            else:
                if s.cpu_pct() >= C.CRITICAL_CPU:
                    flags.append("cpu_critical")
                elif s.cpu_pct() >= C.HIGH_CPU:
                    flags.append("cpu_high")
                if s.mem_pct() >= C.HIGH_MEM:
                    flags.append("mem_high")
                if status == "underutilized":
                    flags.append("underutilized")
                    low.append(s.id)
                if "cpu_critical" in flags or "cpu_high" in flags or "mem_high" in flags:
                    hot.append(s.id)
            observed.append({"server_id": s.id, "status": status, "cpu_pct": round(s.cpu_pct(), 1),
                             "mem_pct": round(s.mem_pct(), 1), "jobs": len(s.jobs), "flags": flags})

        on = [o for o in observed if o["status"] != "off"]
        if hot:
            parts = [f"{o['server_id']} CPU {o['cpu_pct']}% / RAM {o['mem_pct']}% ({o['status']})"
                     for o in on if o["server_id"] in hot]
            decision = "Hotspot detected: " + ", ".join(hot)
            explanation = "; ".join(parts) + f". Thresholds: CPU >= {C.HIGH_CPU:.0f}% or RAM >= {C.HIGH_MEM:.0f}%."
            level = "warning"
        elif low:
            decision = "Low utilization detected: " + ", ".join(low)
            explanation = (f"CPU below {C.LOW_CPU:.0f}% and RAM below {C.LOW_MEM:.0f}% on these servers. "
                           "Passing the observation to the other agents.")
            level = "info"
        else:
            decision = "All active servers healthy"
            explanation = "CPU/RAM " + ", ".join(f"{o['server_id']} {o['cpu_pct']}%/{o['mem_pct']}%" for o in on) + "."
            level = "success"
        state.log(self.name, decision, explanation, f"Recorded metric sample {state.cycle}.", level)

        obs_text = "; ".join(f"{o['server_id']}: {o['status']} (CPU {o['cpu_pct']}%, RAM {o['mem_pct']}%)" for o in observed)
        return _envelope(self.name, state.cycle,
                         {"servers": observed, "hotspots": hot, "underutilized": low}, [],
                         [{"type": "record_sample", "label": str(state.cycle)}],
                         obs_text, f"{decision}. Metric sample {state.cycle} recorded.")


# =============================================================================
# 2. PREDICTION AGENT - simple linear trend. Honest about missing history.
# =============================================================================
def linear_forecast(samples):
    """
    Least-squares straight line through the last PRED_WINDOW samples,
    extended PRED_HORIZON cycles ahead. Returns (forecast, slope).
    """
    window = samples[-C.PRED_WINDOW:]
    n = len(window)
    mean_x = (n - 1) / 2.0
    mean_y = sum(window) / n
    denom = sum((i - mean_x) ** 2 for i in range(n))
    slope = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(window)) / denom
    forecast = mean_y + slope * ((n - 1 + C.PRED_HORIZON) - mean_x)
    return forecast, slope


class PredictionAgent:
    name = "Prediction Agent"
    METHOD = (f"Linear trend (least squares) over the last {C.PRED_WINDOW} CPU samples, "
              f"{C.PRED_HORIZON} cycles ahead")

    def run(self, state, monitoring):
        forecasts, flagged, lines = {}, [], []
        for s in state.servers:
            if not s.powered_on:
                forecasts[s.id] = {"status": "powered_off", "method": self.METHOD}
                lines.append(f"{s.id}: powered off, no forecast")
                continue
            samples = state.cpu_samples(s.id)
            if len(samples) < C.MIN_HISTORY:
                forecasts[s.id] = {"status": "insufficient_history", "samples": len(samples),
                                   "needed": C.MIN_HISTORY, "method": self.METHOD}
                lines.append(f"{s.id}: insufficient history ({len(samples)}/{C.MIN_HISTORY} samples)")
                continue
            raw, slope = linear_forecast(samples)
            forecast = min(100.0, max(0.0, raw))
            trend = "flat" if abs(slope) < C.TREND_FLAT_BAND else ("rising" if slope > 0 else "falling")
            overload = forecast >= C.PRED_HIGH
            forecasts[s.id] = {"status": "ok", "method": self.METHOD, "samples_used": min(len(samples), C.PRED_WINDOW),
                               "current_cpu": round(samples[-1], 1), "slope_per_cycle": round(slope, 2),
                               "trend": trend, "forecast_cpu": round(forecast, 1),
                               "clamped": raw != forecast, "horizon_cycles": C.PRED_HORIZON,
                               "predicted_overload": overload}
            lines.append(f"{s.id}: {samples[-1]:.1f}% now, trend {trend} ({slope:+.1f}/cycle), "
                         f"forecast {forecast:.1f}%" + (" PREDICTED OVERLOAD" if overload else ""))
            if overload:
                flagged.append(s.id)

        if flagged:
            decision = "Predicted overload: " + ", ".join(flagged)
            explanation = (f"{self.METHOD}. Forecast >= {C.PRED_HIGH:.0f}% on these servers. "
                           "Forecasts are clamped to 0-100% and are estimates only.")
            level = "warning"
        elif any(f["status"] == "insufficient_history" for f in forecasts.values()):
            decision = "Forecast limited: insufficient history on some servers"
            explanation = "Need at least %d samples; no fake forecast is produced for the others." % C.MIN_HISTORY
            level = "info"
        else:
            decision = "No overload predicted"
            explanation = f"{self.METHOD}. All forecasts stay below {C.PRED_HIGH:.0f}%."
            level = "success"
        state.log(self.name, decision, explanation, "; ".join(lines), level)

        recs = [{"type": "predicted_overload", "server_id": sid} for sid in flagged]
        return _envelope(self.name, state.cycle, {"forecasts": forecasts, "predicted_overload": flagged},
                         recs, [], "; ".join(lines), decision + ".")


# =============================================================================
# 3. ALLOCATION AGENT - decides WHERE jobs go. Checks CPU and RAM.
# =============================================================================
class AllocationAgent:
    name = "Allocation Agent"

    # ---- feasibility check shared by placement, migration and draining ----
    def check_fit(self, server, job, cpu_limit, mem_limit, extra_cpu=0.0, extra_mem=0.0):
        """Return (True, "") or (False, reason). extra_* lets plans reserve space in advance."""
        if not server.powered_on:
            return False, "is powered off (no capacity available)"
        cpu_room = server.cpu_capacity * cpu_limit / 100.0 - (server.nominal_cpu() + extra_cpu)
        mem_room = server.mem_capacity * mem_limit / 100.0 - (server.nominal_mem() + extra_mem)
        if job.cpu > cpu_room + 1e-9:
            return False, f"CPU: needs {job.cpu:g} vCPU but only {max(0.0, cpu_room):.1f} vCPU free under the {cpu_limit:.0f}% limit"
        if job.mem > mem_room + 1e-9:
            return False, f"RAM: needs {job.mem:g} GB but only {max(0.0, mem_room):.1f} GB free under the {mem_limit:.0f}% limit"
        return True, ""

    def best_destination(self, state, job):
        """Pending job: choose the feasible server with the lowest projected max(CPU%, RAM%)."""
        best, reasons = None, []
        for dst in state.servers:
            ok, why = self.check_fit(dst, job, C.PLACE_LIMIT_CPU, C.PLACE_LIMIT_MEM)
            if not ok:
                reasons.append(f"{dst.id} {why}")
                continue
            cpu_after = 100.0 * (dst.nominal_cpu() + job.cpu) / dst.cpu_capacity
            mem_after = 100.0 * (dst.nominal_mem() + job.mem) / dst.mem_capacity
            cand = (max(cpu_after, mem_after), dst.id, cpu_after, mem_after)
            if best is None or cand < best:
                best = cand
        return best, reasons

    def best_migration(self, state, src):
        """
        Try every (job on src) x (other server) pair. Keep feasible ones and score them by
        the projected maximum utilization of BOTH servers afterwards. Lowest score wins.
        """
        cur_max = max(src.nominal_cpu_pct(), src.nominal_mem_pct())
        best, reasons = None, []
        for job in sorted(src.jobs, key=lambda j: j.name):
            if state.cycle - job.last_migrated_cycle < C.MIGRATION_COOLDOWN:
                reasons.append(f"{job.name}: migration cooldown (moved at cycle {job.last_migrated_cycle})")
                continue
            why_not, feasible = [], False
            for dst in state.servers:
                if dst.id == src.id:
                    continue
                ok, why = self.check_fit(dst, job, C.PLACE_LIMIT_CPU, C.PLACE_LIMIT_MEM)
                if not ok:
                    why_not.append(f"{dst.id} {why}")
                    continue
                feasible = True
                src_cpu = 100.0 * (src.nominal_cpu() - job.cpu) / src.cpu_capacity
                src_mem = 100.0 * (src.nominal_mem() - job.mem) / src.mem_capacity
                dst_cpu = 100.0 * (dst.nominal_cpu() + job.cpu) / dst.cpu_capacity
                dst_mem = 100.0 * (dst.nominal_mem() + job.mem) / dst.mem_capacity
                score = max(src_cpu, src_mem, dst_cpu, dst_mem)
                cand = (score, job.name, dst.id, src_cpu, src_mem, dst_cpu, dst_mem)
                if best is None or cand < best:
                    best = cand
            if not feasible:
                reasons.append(f"{job.name} ({job.cpu:g} vCPU, {job.mem:g} GB): " + "; ".join(why_not))
        if best and best[0] <= cur_max - C.MIN_GAIN:
            return {"move": {"job": best[1], "from": src.id, "to": best[2], "projected_max": round(best[0], 1),
                             "src_cpu_after": round(best[3], 1), "dst_cpu_after": round(best[5], 1)},
                    "reasons": reasons}
        if best:
            reasons.append(f"best feasible move would not lower the maximum utilization by {C.MIN_GAIN:g}+ points")
        return {"move": None, "reasons": reasons}

    def plan_drain(self, state, source):
        """
        Used by the Optimization Agent (agent-to-agent request): can EVERY job on `source`
        be placed on the other powered-on servers under the stricter consolidation limits?
        Returns {"ok": True, "moves": [...]} or {"ok": False, "reason": "..."}.
        Nothing is changed here; it only plans.
        """
        extra = {s.id: [0.0, 0.0] for s in state.servers}
        moves = []
        for job in sorted(source.jobs, key=lambda j: (-j.cpu, j.name)):
            if state.cycle - job.last_migrated_cycle < C.MIGRATION_COOLDOWN:
                return {"ok": False, "reason": f"{job.name} moved recently (migration cooldown)"}
            best, why_not = None, []
            for dst in state.servers:
                if dst.id == source.id:
                    continue
                ok, why = self.check_fit(dst, job, C.CONSOLIDATE_LIMIT_CPU, C.CONSOLIDATE_LIMIT_MEM,
                                         extra[dst.id][0], extra[dst.id][1])
                if not ok:
                    why_not.append(f"{dst.id} {why}")
                    continue
                cpu_after = 100.0 * (dst.nominal_cpu() + extra[dst.id][0] + job.cpu) / dst.cpu_capacity
                mem_after = 100.0 * (dst.nominal_mem() + extra[dst.id][1] + job.mem) / dst.mem_capacity
                cand = (max(cpu_after, mem_after), dst.id)
                if best is None or cand < best:
                    best = cand
            if best is None:
                return {"ok": False, "reason": f"{job.name} does not fit elsewhere: " + "; ".join(why_not)}
            extra[best[1]][0] += job.cpu
            extra[best[1]][1] += job.mem
            moves.append({"job": job.name, "from": source.id, "to": best[1], "projected_max": round(best[0], 1)})
        return {"ok": True, "moves": moves}

    # ---- servers that deserve relief ----
    def hotspots(self, state, forecasts):
        out = []
        for s in state.active_servers():
            f = forecasts.get(s.id, {})
            predicted = f.get("predicted_overload", False)
            if s.cpu_pct() >= C.HIGH_CPU or s.mem_pct() >= C.HIGH_MEM or (predicted and s.cpu_pct() >= C.RELIEF_TARGET):
                out.append(s)
        return sorted(out, key=lambda s: (-s.cpu_pct(), s.id))

    @staticmethod
    def needs_relief(server):
        return server.cpu_pct() > C.RELIEF_TARGET or server.mem_pct() >= C.HIGH_MEM

    # ---- the agent's turn ----
    def run(self, state, monitoring, prediction):
        forecasts = prediction["observation"]["forecasts"]
        actions, unresolved, notes = [], [], []

        # Part 1: place pending jobs
        for job in list(state.pending):
            best, reasons = self.best_destination(state, job)
            if best is None:
                unresolved.append({"type": "pending_job", "job": job.name, "reasons": reasons})
                state.log(self.name, f"Cannot place pending job {job.name}",
                          f"Needs {job.cpu:g} vCPU / {job.mem:g} GB. " + "; ".join(reasons),
                          "Job stays pending; capacity was not violated.", "warning")
                continue
            score, dst_id, cpu_after, mem_after = best
            state.place_pending(job.name, dst_id)
            actions.append({"type": "place", "job": job.name, "to": dst_id, "projected_max": round(score, 1)})
            state.log(self.name, f"Placed {job.name} on {dst_id}",
                      f"Both CPU and RAM fit. Projected {dst_id} CPU {cpu_after:.1f}% / RAM {mem_after:.1f}% "
                      f"(max {score:.1f}% is the lowest among feasible servers).",
                      "Pending job assigned.", "action")

        # Part 2: relieve hotspots
        migrations = 0
        for src in self.hotspots(state, forecasts):
            while migrations < C.MAX_MIGRATIONS_PER_CYCLE and self.needs_relief(src):
                before_cpu = src.cpu_pct()
                result = self.best_migration(state, src)
                if result["move"] is None:
                    unresolved.append({"type": "hotspot", "server": src.id, "reasons": result["reasons"]})
                    state.log(self.name, f"No safe migration available for {src.id}",
                              f"{src.id} is at CPU {before_cpu:.1f}% but nothing can move without breaking limits. "
                              + " | ".join(result["reasons"]),
                              "No change made; capacity rules respected.", "warning")
                    break
                m = result["move"]
                state.migrate_job(m["job"], m["from"], m["to"])
                migrations += 1
                actions.append({"type": "migrate", **m})
                state.log(self.name, f"Migrated {m['job']}: {m['from']} -> {m['to']}",
                          f"{m['from']} was at CPU {before_cpu:.1f}%. After the move: {m['from']} CPU ~{m['src_cpu_after']}%, "
                          f"{m['to']} CPU ~{m['dst_cpu_after']}%. Projected max utilization {m['projected_max']}% "
                          "is the lowest of all feasible moves (CPU and RAM both checked).",
                          "Migration applied.", "action")
            else:
                if self.needs_relief(src):
                    notes.append(f"{src.id} still hot; migration limit of {C.MAX_MIGRATIONS_PER_CYCLE} per cycle reached")

        if not actions and not unresolved:
            state.log(self.name, "No allocation needed",
                      "No pending jobs and no server needs relief.", "No change.", "success")

        if actions:
            action_text = "; ".join(
                (f"placed {a['job']} on {a['to']}" if a["type"] == "place" else f"moved {a['job']} {a['from']} -> {a['to']}")
                for a in actions)
        elif unresolved:
            action_text = "Could not safely place/move: " + "; ".join(
                u.get("job", u.get("server", "?")) for u in unresolved)
        else:
            action_text = "No allocation needed."
        obs_text = (f"{len(state.pending)} pending job(s) left; "
                    f"hotspots considered: {', '.join(m['server_id'] for m in monitoring['observation']['servers'] if m['server_id'] in monitoring['observation']['hotspots']) or 'none'}.")
        return _envelope(self.name, state.cycle,
                         {"unresolved": unresolved, "migrations_applied": migrations,
                          "placements_applied": sum(1 for a in actions if a["type"] == "place"), "notes": notes},
                         [], actions, obs_text, action_text)


# =============================================================================
# 4. OPTIMIZATION AGENT - scaling, consolidation, waste and cost. Deterministic rules.
# =============================================================================
class OptimizationAgent:
    name = "Optimization Agent"

    def __init__(self, allocator):
        self.allocator = allocator      # used to ask "can this server be drained safely?"

    def run(self, state, monitoring, prediction, allocation):
        active = state.active_servers()
        cost_before = state.hourly_cost()
        idle_cost = sum(s.hourly_rate * (1.0 - s.cpu_pct() / 100.0) for s in active)
        alloc_obs = allocation["observation"]
        forecasts = prediction["observation"]["forecasts"]
        cooldown = state.scale_cooldown_remaining()
        recs, actions = [], []

        pressure = [s for s in active if s.cpu_pct() >= C.HIGH_CPU or s.mem_pct() >= C.HIGH_MEM]
        any_predicted = any(f.get("predicted_overload") for f in forecasts.values())

        # ---- Rule 1: scale out when Allocation could not fix pressure ----
        if alloc_obs["unresolved"]:
            standby = [s for s in state.servers if not s.powered_on]
            if not standby:
                decision = "Scale-out needed but no standby server exists"
                explanation = "Allocation reported unresolved pressure and every server is already on."
                state.log(self.name, decision, explanation, "No change.", "warning")
                recs.append({"type": "scale_out_blocked", "reason": "no standby server"})
            elif cooldown > 0:
                decision = "Scale-out postponed (cooldown)"
                explanation = f"A scaling action happened recently; {cooldown} more cycle(s) before the next one (prevents flip-flopping)."
                state.log(self.name, decision, explanation, "No change.", "info")
                recs.append({"type": "scale_out_postponed", "cooldown_remaining": cooldown})
            else:
                target = standby[0]
                state.power_on(target.id)
                after_cost = state.hourly_cost()
                decision = f"Scaled out: powered on {target.id}"
                explanation = ("Allocation could not place/move work safely on the active servers"
                               + (" and the forecast predicts overload" if any_predicted else "") +
                               f". {target.id} adds {target.cpu_capacity:g} vCPU / {target.mem_capacity:g} GB. "
                               "Allocation can use it from the next cycle.")
                result = f"Hourly cost ${cost_before:.2f} -> ${after_cost:.2f} (+${after_cost - cost_before:.2f}, simulated). Cooldown {C.SCALE_COOLDOWN} cycles."
                state.log(self.name, decision, explanation, result, "action")
                actions.append({"type": "power_on", "server": target.id, "cost_before": cost_before, "cost_after": after_cost})
        elif pressure:
            decision = "Pressure remains; waiting for Allocation"
            explanation = ("Allocation still has feasible moves for the hot server(s), so no extra server is powered on yet: "
                           + ", ".join(s.id for s in pressure) + ".")
            state.log(self.name, decision, explanation, "No change.", "info")
        # ---- Rule 2: consolidate when everything is calm ----
        elif state.pending or alloc_obs["migrations_applied"] or alloc_obs["placements_applied"]:
            decision = "Holding: allocation changed things this cycle"
            explanation = "Optimization waits one calm cycle before consolidating so changes do not stack up."
            state.log(self.name, decision, explanation, "No change.", "info")
        elif any_predicted:
            decision = "Holding: overload is predicted"
            explanation = "A forecast predicts overload somewhere, so removing capacity would be unsafe."
            state.log(self.name, decision, explanation, "No change.", "info")
        elif len(active) <= C.MIN_ACTIVE_SERVERS:
            decision = "Minimum server count reached"
            explanation = (f"Only {len(active)} server(s) are on; the policy keeps at least "
                           f"{C.MIN_ACTIVE_SERVERS} running for redundancy, so no further consolidation.")
            state.log(self.name, decision, explanation, "No change.", "info")
        else:
            candidates = sorted([s for s in active if s.cpu_pct() < C.LOW_CPU and s.mem_pct() < C.LOW_MEM],
                                key=lambda s: (s.cpu_pct(), s.id))
            if not candidates:
                decision = "No consolidation candidate"
                explanation = (f"No server is below {C.LOW_CPU:.0f}% CPU, so every active server is justified. "
                               f"Idle capacity is worth about ${idle_cost:.2f}/hour (simulated).")
                state.log(self.name, decision, explanation, "No change.", "success")
            elif cooldown > 0:
                decision = f"Consolidation of {candidates[0].id} postponed (cooldown)"
                explanation = f"{cooldown} more cycle(s) before the next scaling action."
                state.log(self.name, decision, explanation, "No change.", "info")
                recs.append({"type": "consolidate_postponed", "server": candidates[0].id})
            else:
                decision, explanation = None, None
                blocked = []
                for cand in candidates:
                    plan = self.allocator.plan_drain(state, cand)
                    if not plan["ok"]:
                        blocked.append(f"{cand.id}: {plan['reason']}")
                        continue
                    cand_cpu = cand.cpu_pct()
                    for mv in plan["moves"]:
                        state.migrate_job(mv["job"], mv["from"], mv["to"])
                    state.power_off(cand.id)
                    after_cost = state.hourly_cost()
                    decision = f"Consolidated: drained and powered off {cand.id}"
                    explanation = (f"{cand.id} was at CPU {cand_cpu:.1f}%. "
                                   "All of its jobs fit on other servers within the consolidation limits "
                                   f"(CPU <= {C.CONSOLIDATE_LIMIT_CPU:.0f}%, RAM <= {C.CONSOLIDATE_LIMIT_MEM:.0f}%): "
                                   + ", ".join(f"{m['job']} -> {m['to']}" for m in plan["moves"]) + ".")
                    result = (f"Hourly cost ${cost_before:.2f} -> ${after_cost:.2f} (saves ${cost_before - after_cost:.2f}/hour, simulated). "
                              "Remaining servers now run hotter, which is the trade-off.")
                    state.log(self.name, decision, explanation, result, "action")
                    actions.append({"type": "power_off", "server": cand.id, "moves": plan["moves"],
                                    "cost_before": cost_before, "cost_after": after_cost})
                    break
                if decision is None:
                    decision = "Consolidation blocked"
                    explanation = "Idle server(s) found but their jobs do not all fit elsewhere: " + " | ".join(blocked)
                    state.log(self.name, decision, explanation, "No change; no cost saving claimed.", "info")
                    recs.append({"type": "consolidate_blocked", "reasons": blocked})

        # ---- Advisory: load imbalance (recommendation only) ----
        active = state.active_servers()
        if len(active) >= 2:
            hi = max(active, key=lambda s: s.cpu_pct())
            lo = min(active, key=lambda s: s.cpu_pct())
            if hi.cpu_pct() - lo.cpu_pct() >= C.IMBALANCE_SPREAD:
                recs.append({"type": "load_imbalance", "high": hi.id, "low": lo.id,
                             "spread": round(hi.cpu_pct() - lo.cpu_pct(), 1)})

        cost_after = state.hourly_cost()
        observation = {"hourly_cost": cost_after, "hourly_cost_before": cost_before,
                       "idle_capacity_cost_per_hour": round(idle_cost, 2), "active_servers": len(active),
                       "scale_cooldown_remaining": state.scale_cooldown_remaining(),
                       "cost_note": C.COST_NOTE}
        obs_text = (f"Cost ${cost_after:.2f}/hour for {len(active)} active server(s); idle capacity ~${idle_cost:.2f}/hour "
                    f"(simulated). Scaling cooldown: {state.scale_cooldown_remaining()} cycle(s).")
        for r in recs:
            if r["type"] == "load_imbalance":
                obs_text += f" Load spread {r['spread']} pts ({r['high']} vs {r['low']})."
        action_text = decision + ("." if actions else " (no change applied).")
        return _envelope(self.name, state.cycle, observation, recs, actions, obs_text, action_text)
