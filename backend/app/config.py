"""
config.py - every threshold and policy number lives here.

Keeping the numbers in one place makes the system easy to explain in a viva:
"the agents are rule-based, and these are the rules."
All CPU / RAM thresholds are percentages of a server's capacity.
"""

# ---- Monitoring Agent thresholds -------------------------------------------
HIGH_CPU = 75.0          # CPU % at or above this -> server is "high"
CRITICAL_CPU = 90.0      # CPU % at or above this -> server is "overloaded"
HIGH_MEM = 85.0          # RAM % at or above this -> "high"
CRITICAL_MEM = 92.0      # RAM % at or above this -> "overloaded"
LOW_CPU = 30.0           # CPU % below this (and RAM below LOW_MEM) -> "underutilized"
LOW_MEM = 40.0

# ---- Prediction Agent ------------------------------------------------------
MIN_HISTORY = 4          # fewer samples than this -> "insufficient history"
PRED_WINDOW = 5          # use the most recent 5 samples
PRED_HORIZON = 2         # forecast this many cycles ahead
PRED_HIGH = 85.0         # forecast at or above this -> "predicted overload"
TREND_FLAT_BAND = 0.75   # |slope| below this (pts per cycle) is called "flat"

# ---- Allocation Agent ------------------------------------------------------
PLACE_LIMIT_CPU = 85.0   # never fill a server beyond 85% CPU when placing/migrating
PLACE_LIMIT_MEM = 85.0   # ...or 85% RAM (leaves headroom; hard capacity is 100%)
RELIEF_TARGET = 70.0     # keep moving jobs off a hot server until CPU <= this
MIN_GAIN = 2.0           # a migration must lower the pair's max utilization by >= 2 pts
MAX_MIGRATIONS_PER_CYCLE = 2
MIGRATION_COOLDOWN = 3   # a job that just moved cannot move again for 3 cycles

# ---- Optimization Agent ----------------------------------------------------
SCALE_COOLDOWN = 3                # cycles between power-on / power-off actions
MIN_ACTIVE_SERVERS = 2            # never consolidate below 2 running servers (redundancy)
CONSOLIDATE_LIMIT_CPU = 70.0      # stricter limits when draining a server,
CONSOLIDATE_LIMIT_MEM = 75.0      # so we do not create a new hotspot
IMBALANCE_SPREAD = 35.0           # max-min CPU gap (points) that triggers a balancing note

# ---- Simulation ------------------------------------------------------------
JITTER_CORES = 0.15      # tiny seeded background CPU wobble per cycle (cores)
HISTORY_LIMIT = 40
LOG_LIMIT = 300
ENV_LABEL = "SIMULATED CLOUD ENVIRONMENT"
COST_NOTE = "Simulated estimate (flat $/hour per powered-on server). Not real AWS pricing."
