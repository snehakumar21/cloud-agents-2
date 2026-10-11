// All backend calls live here. The backend is the FastAPI app on port 8000.
const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function call(path, method = "GET") {
  const res = await fetch(API + path, { method });
  if (!res.ok) {
    throw new Error(`${method} ${path} failed with status ${res.status}`);
  }
  return res.json();
}

export const getState = () => call("/api/state");
export const getAwsInventory = () => call("/api/aws/instances");
export const getAgents = () => call("/api/agents");
export const getLogs = () => call("/api/logs");
export const setScenario = (name) => call(`/api/scenario/${name}`, "POST");
export const stepCycle = () => call("/api/step", "POST");
export const resetDemo = () => call("/api/reset", "POST");
export const API_URL = API;
