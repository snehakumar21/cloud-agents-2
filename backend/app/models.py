"""
models.py - the two basic objects: Job and Server.

CPU is measured in vCPU cores and memory in GB.
A Job is indivisible: it runs on exactly one server and needs fixed cpu + mem.
A Server's usage is ALWAYS computed from its baseline + the jobs assigned to it,
so utilization percentages can never disagree with the workloads.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Job:
    name: str                       # unique name, also used as the id
    cpu: float                      # vCPU cores required
    mem: float                      # GB of RAM required
    last_migrated_cycle: int = -100  # used for the migration cooldown

    def to_dict(self):
        return {"name": self.name, "cpu": self.cpu, "mem": self.mem}


@dataclass
class Server:
    id: str
    name: str
    cpu_capacity: float             # total vCPU cores
    mem_capacity: float             # total GB RAM
    base_cpu: float                 # baseline (OS / agents) CPU when powered on
    base_mem: float                 # baseline memory when powered on
    hourly_rate: float              # simulated $/hour while powered on
    powered_on: bool = True
    jitter_cpu: float = 0.0         # tiny background CPU wobble (cores), display only
    jobs: List[Job] = field(default_factory=list)

    # ---- nominal usage = baseline + jobs (used for every capacity decision) ----
    def nominal_cpu(self) -> float:
        if not self.powered_on:
            return 0.0
        return self.base_cpu + sum(j.cpu for j in self.jobs)

    def nominal_mem(self) -> float:
        if not self.powered_on:
            return 0.0
        return self.base_mem + sum(j.mem for j in self.jobs)

    def nominal_cpu_pct(self) -> float:
        return 100.0 * self.nominal_cpu() / self.cpu_capacity

    def nominal_mem_pct(self) -> float:
        return 100.0 * self.nominal_mem() / self.mem_capacity

    # ---- observed usage = nominal + small jitter (what the Monitoring Agent sees) ----
    def cpu_used(self) -> float:
        if not self.powered_on:
            return 0.0
        return min(self.cpu_capacity, max(0.0, self.nominal_cpu() + self.jitter_cpu))

    def cpu_pct(self) -> float:
        return 100.0 * self.cpu_used() / self.cpu_capacity

    def mem_pct(self) -> float:
        return self.nominal_mem_pct()

    def hourly_cost(self) -> float:
        return self.hourly_rate if self.powered_on else 0.0

    def find_job(self, name: str):
        for j in self.jobs:
            if j.name == name:
                return j
        return None
