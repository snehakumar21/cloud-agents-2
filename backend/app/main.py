"""
main.py - FastAPI app. Run with:  uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

CORS: the React dev server runs on http://localhost:5173 and the API on http://127.0.0.1:8000.
Browsers treat those as different origins, so the API explicitly allows the Vite origins.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .orchestrator import Orchestrator
from .scenarios import scenario_keys
from .state import CloudState, AGENT_KEYS

app = FastAPI(title="Multi-Agent AI Cloud Resource Allocator (simulated)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

state = CloudState()
orchestrator = Orchestrator(state)


@app.get("/")
def root():
    return {"service": "simulated multi-agent cloud allocator", "docs": "/docs"}


@app.get("/api/state")
def get_state():
    with state.lock:
        return state.to_dict()


@app.get("/api/agents")
def get_agents():
    with state.lock:
        return {"cycle": state.cycle, "agents": [state.agent_status[k] for k in AGENT_KEYS]}


@app.get("/api/logs")
def get_logs():
    with state.lock:
        return {"logs": list(state.logs)}


@app.post("/api/scenario/{scenario_name}")
def set_scenario(scenario_name: str):
    if scenario_name not in scenario_keys():
        raise HTTPException(status_code=404, detail=f"Unknown scenario. Use one of {scenario_keys()}")
    orchestrator.load_scenario(scenario_name)
    with state.lock:
        return state.to_dict()


@app.post("/api/step")
def step():
    result = orchestrator.run_cycle()
    with state.lock:
        return {"result": result, "state": state.to_dict()}


@app.post("/api/reset")
def reset():
    orchestrator.reset()
    with state.lock:
        return state.to_dict()
