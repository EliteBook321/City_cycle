// Local demo connects to FastAPI on port 8000. Set the deployed API origin before deployment.
const isLocalCityCycle = ["localhost", "127.0.0.1"].includes(window.location.hostname);
window.CITYCYCLE_CONFIG = Object.freeze({
  API_BASE_URL: isLocalCityCycle ? "http://127.0.0.1:8000" : "",
  AUTO_SETUP_ON_MISSING: isLocalCityCycle,
  REQUEST_TIMEOUT_MS: 12000
});
