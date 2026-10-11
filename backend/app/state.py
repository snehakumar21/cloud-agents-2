"""
state.py - the shared in-memory "cloud" that every agent reads and changes.

There is no database. Everything below lives in Python memory and resets when the
backend restarts. The state also owns the ONLY functions that change the cloud
(place / migrate / power on / power off), and each one re-checks capacity, so no
agent can ever push a server past 100% by mistake.
"""
import random
import threading
from datetime import datetime

from . import config as C
from . import scenarios

AGENT_KEYS = ["monitoring", "prediction", "allocation", "optimization"]
AGENT_ROLES = {
    "monitoring": ("Monitoring Agent", "Observes every server, records a metric sample each cycle, flags high and low utilization."),
    "prediction": ("Prediction Agent", "Fits a least-squares linear trend to recent CPU samples and forecasts a few cycles ahead."),
    "allocation": ("Allocation Agent", "Places pending jobs and migrates jobs off hotspots, checking CPU and RAM of every destination."),
    "optimization": ("Optimization Agent", "Scales out when allocation cannot fix pressure, consolidates idle servers, and estimates simulated cost."),
}


def classify(server):
    """Turn raw utilization into a status word (used by the Monitoring Agent and the UI)."""
    if not server.powered_on:
        return "off"
    cpu, mem = server.cpu_pct(), server.mem_pct()
    if cpu >= C.CRITICAL_CPU or mem >= C.CRITICAL_MEM:
        return "overloaded"
    if cpu >= C.HIGH_CPU or mem >= C.HIGH_MEM:
        return "high"
    if cpu < C.LOW_CPU and mem < C.LOW_MEM:
        return "underutilized"
    return "healthy"


class CloudState:
    def __init__(self):
        self.lock = threading.RLock()     # one lock so a request never sees half-updated state
        self.load_scenario("normal")

    # ------------------------------------------------------------------ setup
    def load_scenario(self, key):
        data = scenarios.build_scenario(key)          # KeyError if unknown
        self.scenario = data["meta"]
        self.servers = data["servers"]
        self.pending = data["pending"]
        self.history = data["history"]
        self.cycle = 0
        self.logs = []
        self._log_id = 0
        self.last_scale_cycle = -100
        self.agent_status = {
            k: {"key": k, "name": AGENT_ROLES[k][0], "role": AGENT_ROLES[k][1], "cycle": 0,
                "observation": "Waiting for the first cycle.", "action": "No action yet.",
                "recommendations": [], "data": None}
            for k in AGENT_KEYS
        }
        self.last_change = None     # before/after snapshot of the latest cycle that changed something
        self.last_cycle = None
        self.log("System", f"Scenario loaded: {self.scenario['title']}",
                 self.scenario["description"], f"Seed {self.scenario['seed']}, cycle 0.", "info")

    # --------------------------------------------------------------- lookups
    def get_server(self, server_id):
        for s in self.servers:
            if s.id == server_id:
                return s
        raise KeyError(server_id)

    def active_servers(self):
        return [s for s in self.servers if s.powered_on]

    def hourly_cost(self):
        return round(sum(s.hourly_cost() for s in self.servers), 2)

    def scale_cooldown_remaining(self):
        return max(0, C.SCALE_COOLDOWN - (self.cycle - self.last_scale_cycle))

    # ------------------------------------------------------------- environment
    def tick_environment(self):
        """Apply a tiny seeded background CPU wobble (same seed + cycle -> same value)."""
        for s in self.servers:
            if s.powered_on:
                rng = random.Random(f"{self.scenario['seed']}:{self.cycle}:{s.id}")
                s.jitter_cpu = round(rng.uniform(-C.JITTER_CORES, C.JITTER_CORES), 3)
            else:
                s.jitter_cpu = 0.0

    # ------------------------------------------------------------------ metrics
    def record_sample(self):
        """Append one metric row (used by the Monitoring Agent)."""
        row = {"label": str(self.cycle), "seeded": False, "servers": {}}
        for s in self.servers:
            if s.powered_on:
                row["servers"][s.id] = {"cpu": round(s.cpu_pct(), 2), "mem": round(s.mem_pct(), 2), "on": True}
            else:
                row["servers"][s.id] = {"cpu": None, "mem": None, "on": False}
        self.history.append(row)
        del self.history[:-C.HISTORY_LIMIT]
        return row

    def cpu_samples(self, server_id):
        """Most recent unbroken run of CPU samples taken while the server was powered on."""
        out = []
        for row in reversed(self.history):
            cell = row["servers"].get(server_id)
            if not cell or not cell["on"] or cell["cpu"] is None:
                break
            out.append(cell["cpu"])
        out.reverse()
        return out

    def snapshot(self):
        """A compact picture of the cloud, used for before/after comparison."""
        active = self.active_servers()
        cpus = [s.cpu_pct() for s in active]
        mems = [s.mem_pct() for s in active]
        return {
            "cycle": self.cycle,
            "active_servers": len(active),
            "avg_cpu": round(sum(cpus) / len(cpus), 1) if cpus else 0.0,
            "avg_mem": round(sum(mems) / len(mems), 1) if mems else 0.0,
            "max_cpu": round(max(cpus), 1) if cpus else 0.0,
            "hourly_cost": self.hourly_cost(),
            "servers": [
                {"id": s.id, "name": s.name, "powered_on": s.powered_on,
                 "cpu_pct": round(s.cpu_pct(), 1), "mem_pct": round(s.mem_pct(), 1),
                 "status": classify(s), "jobs": len(s.jobs)}
                for s in self.servers
            ],
        }

    # -------------------------------------------------------------------- log
    def log(self, agent, decision, explanation, result, level="info"):
        self._log_id += 1
        self.logs.append({
            "id": self._log_id, "cycle": self.cycle,
            "time": datetime.now().strftime("%H:%M:%S"),
            "agent": agent, "decision": decision, "explanation": explanation,
            "result": result, "level": level,        # level: info | success | warning | action
        })
        del self.logs[:-C.LOG_LIMIT]

    # ------------------------------------------- the only functions that mutate
    def _check_capacity(self, server, extra_cpu, extra_mem):
        if not server.powered_on:
            raise ValueError(f"{server.id} is powered off")
        if server.nominal_cpu() + extra_cpu > server.cpu_capacity + 1e-9:
            raise ValueError(f"{server.id} would exceed CPU capacity")
        if server.nominal_mem() + extra_mem > server.mem_capacity + 1e-9:
            raise ValueError(f"{server.id} would exceed RAM capacity")

    def place_pending(self, job_name, dest_id):
        job = next(j for j in self.pending if j.name == job_name)
        dest = self.get_server(dest_id)
        self._check_capacity(dest, job.cpu, job.mem)
        self.pending.remove(job)
        job.last_migrated_cycle = self.cycle
        dest.jobs.append(job)

    def migrate_job(self, job_name, src_id, dest_id):
        src, dest = self.get_server(src_id), self.get_server(dest_id)
        job = src.find_job(job_name)
        if job is None:
            raise ValueError(f"{job_name} is not on {src_id}")
        self._check_capacity(dest, job.cpu, job.mem)
        src.jobs.remove(job)
        dest.jobs.append(job)
        job.last_migrated_cycle = self.cycle

    def power_on(self, server_id):
        self.get_server(server_id).powered_on = True
        self.last_scale_cycle = self.cycle

    def power_off(self, server_id):
        s = self.get_server(server_id)
        if s.jobs:
            raise ValueError(f"{server_id} still has jobs")
        s.powered_on = False
        s.jitter_cpu = 0.0
        self.last_scale_cycle = self.cycle

    def assert_invariants(self):
        """Used by tests: no server may exceed capacity; off servers hold no jobs."""
        for s in self.servers:
            assert s.nominal_cpu() <= s.cpu_capacity + 1e-9, f"{s.id} CPU over capacity"
            assert s.nominal_mem() <= s.mem_capacity + 1e-9, f"{s.id} RAM over capacity"
            if not s.powered_on:
                assert not s.jobs, f"{s.id} is off but holds jobs"

    # ---------------------------------------------------------------- serialise
    def to_dict(self):
        servers = []
        for s in self.servers:
            servers.append({
                "id": s.id, "name": s.name, "powered_on": s.powered_on, "status": classify(s),
                "cpu_capacity": s.cpu_capacity, "mem_capacity": s.mem_capacity,
                "base_cpu": s.base_cpu, "base_mem": s.base_mem,
                "cpu_used": round(s.cpu_used(), 2), "mem_used": round(s.nominal_mem(), 2),
                "cpu_pct": round(s.cpu_pct(), 1), "mem_pct": round(s.mem_pct(), 1),
                "hourly_rate": s.hourly_rate, "hourly_cost": s.hourly_cost(),
                "jobs": [j.to_dict() for j in s.jobs],
            })
        snap = self.snapshot()
        chart = []
        for row in self.history:
            point = {"label": row["label"], "seeded": row["seeded"]}
            for sid, cell in row["servers"].items():
                point[sid] = cell["cpu"]
            chart.append(point)
        return {
            "environment": C.ENV_LABEL,
            "cost_note": C.COST_NOTE,
            "scenario": self.scenario,
            "cycle": self.cycle,
            "servers": servers,
            "pending_jobs": [j.to_dict() for j in self.pending],
            "kpis": {"active_servers": snap["active_servers"], "total_servers": len(self.servers),
                     "avg_cpu": snap["avg_cpu"], "avg_mem": snap["avg_mem"],
                     "hourly_cost": snap["hourly_cost"]},
            "history": chart,
            "last_change": self.last_change,
            "last_cycle": self.last_cycle,
            "cooldowns": {"scale_remaining": self.scale_cooldown_remaining(),
                          "scale_total": C.SCALE_COOLDOWN, "migration_total": C.MIGRATION_COOLDOWN},
            "thresholds": {"high_cpu": C.HIGH_CPU, "critical_cpu": C.CRITICAL_CPU, "high_mem": C.HIGH_MEM,
                           "low_cpu": C.LOW_CPU, "place_limit_cpu": C.PLACE_LIMIT_CPU,
                           "place_limit_mem": C.PLACE_LIMIT_MEM},
        }
