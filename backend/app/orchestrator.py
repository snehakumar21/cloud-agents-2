"""
orchestrator.py - runs one decision cycle:

    monitor -> predict -> allocate -> optimize -> record decisions

Agents talk to each other only through the structured dictionaries they return
(observations, recommendations, action results). There is no chat between agents.
"""
from .agents import MonitoringAgent, PredictionAgent, AllocationAgent, OptimizationAgent


def _delta(a, b):
    return round(b - a, 1)


class Orchestrator:
    def __init__(self, state):
        self.state = state
        self.monitor = MonitoringAgent()
        self.predictor = PredictionAgent()
        self.allocator = AllocationAgent()
        self.optimizer = OptimizationAgent(self.allocator)

    # ---- API helpers -------------------------------------------------------
    def load_scenario(self, key):
        with self.state.lock:
            self.state.load_scenario(key)

    def reset(self):
        with self.state.lock:
            self.state.load_scenario(self.state.scenario["key"])

    # ---- one full cycle ----------------------------------------------------
    def run_cycle(self):
        st = self.state
        with st.lock:                      # whole cycle is atomic for API readers
            st.cycle += 1
            st.tick_environment()
            before = st.snapshot()

            mon = self.monitor.run(st)
            pred = self.predictor.run(st, mon)
            alloc = self.allocator.run(st, mon, pred)
            opt = self.optimizer.run(st, mon, pred, alloc)
            st.assert_invariants()         # safety net: capacity can never be exceeded

            after = st.snapshot()
            changes = [a for env in (alloc, opt) for a in env["actions"]]
            changed = len(changes) > 0

            # remember each agent's latest report for the dashboard
            for key, env in (("monitoring", mon), ("prediction", pred), ("allocation", alloc), ("optimization", opt)):
                st.agent_status[key].update({
                    "cycle": st.cycle, "observation": env["observation_text"], "action": env["action_text"],
                    "recommendations": env["recommendations"], "data": env,
                })

            comparison = {
                "cycle": st.cycle, "before": before, "after": after, "changes": changes,
                "delta": {"max_cpu": _delta(before["max_cpu"], after["max_cpu"]),
                          "avg_cpu": _delta(before["avg_cpu"], after["avg_cpu"]),
                          "avg_mem": _delta(before["avg_mem"], after["avg_mem"]),
                          "hourly_cost": round(after["hourly_cost"] - before["hourly_cost"], 2),
                          "active_servers": after["active_servers"] - before["active_servers"]},
            }
            st.last_cycle = {"cycle": st.cycle, "changed": changed, "num_changes": len(changes)}
            if changed:
                st.last_change = comparison
            return {"cycle": st.cycle, "changed": changed, "comparison": comparison}
