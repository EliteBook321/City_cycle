"""Optional Groq-powered explanations over server-computed aggregates."""
import json
import httpx
from backend.config import GROQ_API_KEY, GROQ_MODEL

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


def get_ai_status() -> dict:
    """Report availability without revealing the configured credential."""
    return {"available": bool(GROQ_API_KEY), "provider": "Groq" if GROQ_API_KEY else None, "model": GROQ_MODEL if GROQ_API_KEY else None, "message": None if GROQ_API_KEY else "AI summaries are optional. Configure GROQ_API_KEY in the backend environment to enable them."}


def explain_date_range(summary: dict) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("AI is not configured. Set GROQ_API_KEY in the backend environment; never put it in frontend files.")
    if not summary.get("available"):
        raise RuntimeError(summary.get("message", "There is no date-range data to explain."))

    safe_summary = {
        "selected_range": {"start": summary["start_date"], "end": summary["end_date"]},
        "source_observation_period": summary["source_period"],
        "days_with_data": summary["days_with_data"],
        "hourly_rows": summary["hourly_rows"],
        "total_historical_rentals": summary["total_rentals"],
        "average_daily_rentals": summary["average_daily_rentals"],
        "peak_day": summary["peak_day"],
        "workingday_daily_averages": summary["workingday_daily_averages"],
        "largest_category_spreads": summary["largest_observed_category_spreads"],
    }
    prompt = (
        "Explain this selected-range bike-share summary for an operations manager. "
        "Return short plain text with: what changed or stands out, two cautious operations suggestions, and one limitation. "
        "Use only provided numbers. Distinguish association from causation. Never claim live conditions, reservations, "
        "station-level availability, exact bikes to move, or today's actual demand. The CSV contains completed citywide hourly rentals.\n\n"
        f"Aggregate data (JSON): {json.dumps(safe_summary, separators=(',', ':'))}"
    )
    try:
        with httpx.Client(timeout=httpx.Timeout(18.0, connect=5.0)) as client:
            response = client.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "temperature": 0.2,
                    "max_tokens": 450,
                    "messages": [
                        {"role": "system", "content": "You are a cautious bike-share operations analyst. Never invent facts or present correlation as causation."},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException as exc:
        raise RuntimeError("The AI provider timed out. The historical date-range summary is still available.") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (401, 403):
            raise RuntimeError("Groq rejected the configured credential. Rotate it and update the backend environment variable.") from exc
        raise RuntimeError(f"Groq returned HTTP {status}. Historical analytics remain available.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("Could not reach Groq. Historical date-range analytics remain available.") from exc

    try:
        text = payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError("Groq returned an unexpected response format.") from exc
    if not text:
        raise RuntimeError("Groq returned an empty explanation.")
    return {"available": True, "provider": "Groq", "model": GROQ_MODEL, "explanation": text, "range": safe_summary["selected_range"], "disclaimer": "AI-generated explanation of historical aggregates; review before operational use."}
