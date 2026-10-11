"""
scenarios.py - three deterministic demo scenarios.

Every scenario is built from fixed numbers plus a fixed random seed, so pressing
the same button always gives the same starting state and the same warm-up history.

Hardware for every server: 16 vCPU, 32 GB RAM, simulated rate $0.40/hour.
"""
import random
from .models import Job, Server

CPU_CAP = 16.0
MEM_CAP = 32.0
RATE = 0.40


def _server(n, base_cpu, base_mem, jobs, on=True):
    """Build 'srv-n'. jobs is a list of (name, cpu, mem) tuples."""
    return Server(
        id=f"srv-{n}", name=f"Server {n}",
        cpu_capacity=CPU_CAP, mem_capacity=MEM_CAP,
        base_cpu=base_cpu, base_mem=base_mem, hourly_rate=RATE,
        powered_on=on, jobs=[Job(*j) for j in jobs],
    )


def _seed_history(servers, seed, slopes):
    """
    Create 6 seeded warm-up samples (labels -5 .. 0).
    The sample labelled 0 equals the current state exactly. Earlier samples walk
    backwards using a per-server slope (points per sample) plus small seeded noise.
    These are SIMULATED warm-up telemetry, so the Prediction Agent has data on cycle 1.
    """
    rows = []
    for k in range(5, -1, -1):
        row = {"label": str(-k), "seeded": True, "servers": {}}
        for idx, s in enumerate(servers):
            if not s.powered_on:
                row["servers"][s.id] = {"cpu": None, "mem": None, "on": False}
                continue
            rng = random.Random(seed * 100 + idx * 10 + k)   # deterministic noise
            cpu, mem = s.nominal_cpu_pct(), s.nominal_mem_pct()
            if k > 0:
                cpu = cpu - slopes.get(s.id, 0.0) * k + rng.uniform(-1.0, 1.0)
                mem = mem + rng.uniform(-0.5, 0.5)
            row["servers"][s.id] = {
                "cpu": round(min(100.0, max(0.0, cpu)), 2),
                "mem": round(min(100.0, max(0.0, mem)), 2),
                "on": True,
            }
        rows.append(row)
    return rows


def _normal():
    servers = [
        _server(1, 1.6, 3.0, [("web-frontend", 3.0, 4.0), ("api-gateway", 2.2, 3.0), ("cache-service", 1.0, 6.0)]),
        _server(2, 1.4, 3.0, [("orders-api", 3.4, 5.0), ("task-worker", 2.4, 4.0), ("search-index", 2.0, 6.0)]),
        _server(3, 1.2, 2.5, [("auth-service", 1.6, 2.0), ("batch-etl", 2.8, 6.0), ("metrics-collector", 1.0, 2.0)]),
    ]
    pending = [Job("nightly-report", 2.0, 4.0)]
    meta = {
        "key": "normal", "title": "Normal Load", "seed": 11,
        "description": "Three balanced servers (41-58% CPU) and one new job waiting for placement. "
                       "Expect healthy monitoring, one placement, and no migrations or scaling.",
    }
    return meta, servers, pending, {"srv-1": 0.3, "srv-2": -0.2, "srv-3": 0.1}


def _spike():
    servers = [
        _server(1, 1.8, 3.5, [("checkout-api", 4.0, 5.0), ("web-frontend", 3.6, 4.5),
                              ("ml-inference", 3.2, 8.0), ("img-resize", 2.4, 3.0)]),
        _server(2, 1.4, 3.0, [("orders-api", 3.0, 5.0), ("analytics-worker", 2.0, 9.0),
                              ("search-index", 1.4, 4.0)]),
        _server(3, 1.2, 2.5, [], on=False),   # standby server, powered off
    ]
    meta = {
        "key": "spike", "title": "Traffic Spike", "seed": 42,
        "description": "Server 1 is at 93.8% CPU and climbing, Server 2 has room but is RAM-limited, "
                       "and Server 3 is powered off. Expect a migration, a rejected move with reasons, "
                       "then a scale-out.",
    }
    return meta, servers, [], {"srv-1": 7.5, "srv-2": 0.0}


def _underused():
    servers = [
        _server(1, 1.4, 2.5, [("web-frontend", 2.0, 3.0), ("api-gateway", 1.6, 2.5)]),
        _server(2, 1.2, 2.5, [("task-worker", 1.8, 3.5), ("cache-service", 0.8, 4.0)]),
        _server(3, 1.0, 2.0, [("batch-etl", 1.0, 2.0), ("cron-jobs", 0.6, 1.0)]),
    ]
    meta = {
        "key": "underused", "title": "Underutilization", "seed": 77,
        "description": "All three servers are lightly used (16-31% CPU). Expect Server 3 to be drained "
                       "and powered off because all of its jobs fit elsewhere, lowering simulated cost.",
    }
    return meta, servers, [], {"srv-1": -0.4, "srv-2": -0.3, "srv-3": -0.2}


_BUILDERS = {"normal": _normal, "spike": _spike, "underused": _underused}


def scenario_keys():
    return list(_BUILDERS.keys())


def build_scenario(key):
    """Return a fresh, independent copy of the scenario (raises KeyError if unknown)."""
    meta, servers, pending, slopes = _BUILDERS[key]()
    history = _seed_history(servers, meta["seed"], slopes)
    return {"meta": meta, "servers": servers, "pending": pending, "history": history}
