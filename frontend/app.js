/* CityCycle UI: all observed values come from the API; no synthetic demand is shown. */
(() => {
  const config = window.CITYCYCLE_CONFIG || { API_BASE_URL: "", REQUEST_TIMEOUT_MS: 12000 };
  const base = (config.API_BASE_URL || "").replace(/\/$/, "");
  const state = { insights: null, metrics: null, health: null, actions: [], charts: {}, lastForecast: "No request yet", setupAttempted: false, autoForecastAttempted: false, todayForecast: null, calendar: { year: 2012, month: 12, days: [], selectedDay: null }, rangeSummary: null, aiAvailable: false };
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;", "'":"&#39;"}[ch]));
  const fmt = value => Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });
  const hourLabel = hour => `${String(hour).padStart(2, "0")}:00`;
  const localDateValue = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  async function api(path, options = {}) {
    const controller = new AbortController();
    const { timeoutMs, ...fetchOptions } = options;
    const timer = setTimeout(() => controller.abort(), timeoutMs || config.REQUEST_TIMEOUT_MS || 12000);
    try {
      const response = await fetch(`${base}${path}`, { ...fetchOptions, signal: controller.signal, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || body.message || `API request failed (${response.status})`);
      return body;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("The API took too long to respond. Try again in a moment.");
      throw error;
    } finally { clearTimeout(timer); }
  }
  function toast(message, error = false) {
    const target = $("#global-toast"); target.textContent = message; target.classList.toggle("error", error); target.classList.remove("hidden");
    clearTimeout(toast.timer); toast.timer = setTimeout(() => target.classList.add("hidden"), 3500);
  }
  function showPage(name) {
    $$(".page").forEach(page => page.classList.toggle("active", page.id === `page-${name}`));
    $$(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.page === name));
    const button = $(`.nav-item[data-page="${name}"]`); $("#current-module").textContent = button?.querySelector("b")?.textContent.trim() || button?.textContent.trim() || "CityCycle";
    $("#sidebar").classList.remove("open");
    if (name === "actions") loadActions();
    if (name === "dashboard" && state.todayForecast) renderTodayForecast(state.todayForecast);
    if (name === "optimizer") {
      const amount = $("#forecast-form [name=forecast_demand]")?.value;
      if (amount) $("#optimizer-form [name=forecast_demand]").value = amount;
    }
  }
  function pill(status, text) { const node = $("#api-pill"); node.className = `status-pill ${status}`; node.querySelector("em").textContent = text; }
  function applyTheme(theme) {
    const light = theme === "light";
    document.body.dataset.theme = light ? "light" : "dark";
    $("#theme-label").textContent = light ? "Light" : "Dark";
    $("#theme-toggle").setAttribute("aria-checked", String(light));
    $("#theme-switch-knob").classList.toggle("on", light);
    const label = light ? "Switch to dark theme" : "Switch to light theme";
    $("#theme-toggle").setAttribute("aria-label", label);
    $("#theme-toggle").title = label;
  }
  function initializeTheme() {
    let preference = "dark";
    try { preference = localStorage.getItem("citycycle-theme") || "dark"; } catch { /* Storage can be disabled in private browsing. */ }
    applyTheme(preference);
  }
  function createChart(id, labels, values, label = "Average rentals", color = "#43d6c3") {
    const canvas = $("#" + id); if (!canvas) return;
    if (!window.Chart) { showChartFallback(canvas, "Chart library unavailable. API data and other dashboard features remain available."); return; }
    hideChartFallback(canvas);
    state.charts[id]?.destroy();
    const textColor = document.body.dataset.theme === "light" ? "#51656d" : "#718995";
    const gridColor = document.body.dataset.theme === "light" ? "#193b4c12" : "#ffffff0c";
    state.charts[id] = new Chart(canvas, { type: "line", data: { labels, datasets: [{ label, data: values, borderColor: color, backgroundColor: `${color}20`, borderWidth: 2, pointRadius: 2, pointHoverRadius: 5, fill: true, tension: .34 }] }, options: { maintainAspectRatio: false, responsive: true, plugins: { legend: { display: false }, tooltip: { backgroundColor: document.body.dataset.theme === "light" ? "#ffffff" : "#0b1a25", titleColor: "#eaf2f6", bodyColor: "#a9bbc2", borderColor: "#29404d", borderWidth: 1 } }, scales: { x: { grid: { color: gridColor }, ticks: { color: textColor, font: { size: 9 }, maxRotation: 0, autoSkip: true } }, y: { beginAtZero: true, grid: { color: gridColor }, ticks: { color: textColor, font: { size: 9 } } } } } });
  }
  function createComparisonChart(id, labels, datasets) {
    const canvas = $("#" + id); if (!canvas) return;
    if (!window.Chart) { showChartFallback(canvas, "Chart library unavailable. Evaluation metrics remain available above."); return; }
    hideChartFallback(canvas);
    state.charts[id]?.destroy();
    const textColor = document.body.dataset.theme === "light" ? "#51656d" : "#718995";
    const gridColor = document.body.dataset.theme === "light" ? "#193b4c12" : "#ffffff0c";
    state.charts[id] = new Chart(canvas, { type: "line", data: { labels, datasets: datasets.map(dataset => ({ ...dataset, borderWidth: 2, pointRadius: 0, pointHoverRadius: 3, tension: .18 })) }, options: { maintainAspectRatio: false, responsive: true, plugins: { legend: { display: true, labels: { color: textColor, boxWidth: 10, font: { size: 9 } } } }, scales: { x: { grid: { color: gridColor }, ticks: { color: textColor, font: { size: 8 }, maxRotation: 0, autoSkip: true } }, y: { beginAtZero: true, grid: { color: gridColor }, ticks: { color: textColor, font: { size: 9 } } } } } });
  }
  function renderTodayForecast(result) {
    state.todayForecast = result;
    $("#hero-title").textContent = `Today, ${result.weekday}`;
    $("#hero-subtitle").textContent = `A 24-hour citywide scenario for ${new Date(`${result.forecast_date}T12:00:00`).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })}.`;
    $("#metric-forecast").textContent = fmt(result.peak_demand);
    $("#metric-forecast-foot").textContent = `${hourLabel(result.peak_hour)} · scenario peak · 24h total ${fmt(result.total_predicted_rentals)}`;
    $("#metric-peak").textContent = hourLabel(result.peak_hour);
    $("#metric-peak-foot").textContent = `${fmt(result.peak_demand)} rentals · today scenario`;
    $("#today-weather-label").textContent = result.weather_context?.label || "Historical typical conditions";
    $("#today-weather-note").textContent = result.weather_context?.note || result.weather_scenario;
    $("#today-chart-caption").textContent = result.estimate_note;
    $("#today-uncertainty").textContent = result.uncertainty_note || "No prediction range is available; review holdout error on the Model Trust page.";
    const suggestions = result.operational_suggestions || [];
    $("#today-suggestions").innerHTML = suggestions.map((item, index) => `<div class="signal"><span class="signal-icon">${index ? "↗" : "◷"}</span><div><b>${esc(item.title)}</b><p>${esc(item.detail)}</p><span class="priority-badge ${String(item.priority).toLowerCase()}">${esc(item.priority)} PRIORITY</span></div></div>`).join("") || '<div class="empty-mini">No elevated-hour suggestions for this scenario.</div>';
    const labels = result.predictions.map(item => hourLabel(item.hour));
    const threshold = result.historical_high_demand_threshold;
    const todayDatasets = [
      { label: "Predicted rentals", data: result.predictions.map(item => item.predicted_rentals), borderColor: "#43d6c3", backgroundColor: "#43d6c326", fill: true },
      { label: "Historical high-demand guide", data: labels.map(() => threshold), borderColor: "#f0b96b", backgroundColor: "#f0b96b", borderDash: [5, 5] }
    ];
    if (result.predictions[0]?.lower_bound != null) {
      todayDatasets.splice(1, 0,
        { label: "Empirical lower range", data: result.predictions.map(item => item.lower_bound), borderColor: "#48c8df77", backgroundColor: "#48c8df00", fill: false },
        { label: "Empirical upper range", data: result.predictions.map(item => item.upper_bound), borderColor: "#48c8df77", backgroundColor: "#48c8df22", fill: "-1" }
      );
    }
    createComparisonChart("today-chart", labels, todayDatasets);
    $("#forecast-form [name=forecast_date]").value = result.forecast_date;
    deriveCalendarInputs(result.forecast_date);
    $("#forecast-form [name=holiday]").checked = false;
    $("#forecast-form [name=weather]").value = String(result.weather_context?.weather || 1);
    ["temperature", "feels_like", "humidity", "windspeed"].forEach(name => {
      const control = $(`#forecast-form [name="${name}"]`);
      control.value = String(result.weather_context?.[name] ?? 0.5);
      $(`#forecast-form output[data-for="${name}"]`).textContent = Number(control.value).toFixed(2);
    });
    const peakPrediction = result.predictions.find(item => item.hour === result.peak_hour);
    $("#forecast-form [name=hour]").value = String(result.peak_hour);
    $("#optimizer-form [name=forecast_demand]").value = String(result.peak_demand);
    $("#optimizer-form [name=threshold]").value = String(Math.ceil(result.recommended_ops_threshold));
    $("#optimizer-form [name=period]").value = `${result.forecast_date} ${result.weekday} ${hourLabel(result.peak_hour)} (scenario peak)`;
    $("#optimizer-form").requestSubmit();
    $("#last-forecast-status").textContent = `Today scenario · ${result.forecast_date}`;
    $("#forecast-meta").textContent = `${result.model_name} · v${result.model_version} · ${result.data_period}`;
    $("#forecast-number").textContent = fmt(peakPrediction?.predicted_rentals ?? result.peak_demand);
    $("#forecast-result").classList.add("hidden"); $("#forecast-output").classList.remove("hidden");
    $("#forecast-output .result-label").textContent = `ESTIMATED RENTALS · ${hourLabel(result.peak_hour)} SCENARIO PEAK`;
    $("#forecast-suggestions").innerHTML = suggestions.map(item => `<div class="suggestion-pill"><b>${esc(item.title)}</b><span>${esc(item.priority)} priority · ${esc(item.detail)}</span></div>`).join("");
    $("#forecast-suggestions").classList.toggle("hidden", suggestions.length === 0);
  }
  function showChartFallback(canvas, message) {
    let fallback = $(".chart-fallback", canvas.parentElement);
    if (!fallback) { fallback = document.createElement("div"); fallback.className = "chart-fallback"; canvas.parentElement.append(fallback); }
    fallback.textContent = message; fallback.classList.remove("hidden");
  }
  function hideChartFallback(canvas) { $(".chart-fallback", canvas.parentElement)?.classList.add("hidden"); }
  async function loadCalendarMonth(year, month) {
    state.calendar.year = year; state.calendar.month = month;
    $("#calendar-month-label").textContent = new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
    $("#calendar-grid").innerHTML = '<div class="calendar-loading">Loading daily rentals…</div>';
    try {
      const response = await api(`/api/insights/calendar?year=${year}&month=${month}`);
      state.calendar.days = response.days || [];
      state.calendar.response = response;
      state.calendar.selectedDay = null;
      renderCalendar(response);
      if (response.available && response.days.length) selectCalendarDay(response.days[0].day);
      else $("#calendar-day-detail").innerHTML = `<div class="detail-date-icon">◷</div><span class="detail-eyebrow">NO SOURCE ROWS</span><h3>${esc(response.month_name || "Selected month")}</h3><p>${esc(response.message || "No daily rental observations are available for this month.")}</p>`;
      $("#calendar-month-label").textContent = `${response.month_name} ${year}`;
      $("#calendar-prev").disabled = year <= 2011 && month <= 1;
      $("#calendar-next").disabled = year >= 2012 && month >= 12;
    } catch (error) {
      $("#calendar-grid").innerHTML = `<div class="calendar-loading">${esc(error.message)}</div>`;
      $("#calendar-day-detail").innerHTML = `<div class="detail-date-icon">!</div><span class="detail-eyebrow">CALENDAR UNAVAILABLE</span><h3>Could not load this month</h3><p>${esc(error.message)}</p>`;
    }
  }
  function renderCalendar(response) {
    const max = Math.max(1, ...response.days.map(item => item.rentals));
    const empty = Array.from({ length: response.weekday_offset }, () => '<span class="calendar-blank" aria-hidden="true"></span>');
    const cells = response.days.map(day => {
      const proportion = day.rentals / max;
      const intensity = proportion >= .72 ? "high" : proportion >= .4 ? "mid" : "low";
      return `<button class="calendar-day ${intensity}" data-day="${day.day}" aria-label="${response.month_name} ${day.day}, ${fmt(day.rentals)} recorded rentals; busiest hour ${hourLabel(day.peak_hour)}" title="${fmt(day.rentals)} rentals · busiest ${hourLabel(day.peak_hour)}"><span class="calendar-day-number">${day.day}</span><b>${fmt(day.rentals)}</b><small>rides</small></button>`;
    });
    $("#calendar-grid").innerHTML = [...empty, ...cells].join("");
    $("#calendar-grid").dataset.daysInMonth = String(response.days_in_month);
  }
  function selectCalendarDay(dayNumber) {
    const day = state.calendar.days.find(item => item.day === dayNumber);
    if (!day) return;
    state.calendar.selectedDay = dayNumber;
    $$(".calendar-day").forEach(button => button.classList.toggle("selected", Number(button.dataset.day) === dayNumber));
    const { year, month } = state.calendar;
    const date = new Date(year, month - 1, dayNumber);
    $("#calendar-day-detail").innerHTML = `<div class="detail-date-icon">${date.getDate()}</div><span class="detail-eyebrow">RECORDED RIDES</span><h3>${esc(date.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }))}</h3><div class="calendar-total">${fmt(day.rentals)}<small>rentals</small></div><div class="calendar-detail-row"><span>Recorded hours</span><b>${day.hours_recorded} / 24</b></div><div class="calendar-detail-row"><span>Busiest hour</span><b>${hourLabel(day.peak_hour)}</b></div><div class="calendar-detail-row"><span>Rentals at peak</span><b>${fmt(day.peak_hour_rentals)}</b></div><p class="calendar-day-note">Completed historical rides in the UCI data. Not reservations, riders, or future bookings.</p>`;
  }
  function renderInsights(data) {
    state.insights = data;
    if (data.data_period) $("#dashboard-date").textContent = `Source data: ${data.data_period.start} – ${data.data_period.end}`;
    if (!data.available) {
      $("#insights-empty").classList.remove("hidden"); $("#insights-content").classList.add("hidden");
      const reason = data.message || "Historical data is unavailable.";
      const dashboardCanvas = $("#dashboard-chart");
      if (dashboardCanvas) showChartFallback(dashboardCanvas, reason);
      if ($("#demand-signals")) $("#demand-signals").innerHTML = `<div class="empty-mini">${esc(reason)}</div>`;
      return;
    }
    $("#insights-empty").classList.add("hidden"); $("#insights-content").classList.remove("hidden");
    $("#insight-rows").textContent = fmt(data.row_count); $("#insight-missing").textContent = fmt(data.missing_values); $("#insight-peak").textContent = hourLabel(data.summaries.peak_hour);
    const startInput = $("#range-start"), endInput = $("#range-end");
    if (data.data_period) {
      startInput.min = data.data_period.start; startInput.max = data.data_period.end;
      endInput.min = data.data_period.start; endInput.max = data.data_period.end;
      if (!startInput.value || startInput.value < data.data_period.start || startInput.value > data.data_period.end) {
        const periodEnd = new Date(`${data.data_period.end}T12:00:00`);
        const periodStart = new Date(periodEnd); periodStart.setDate(periodStart.getDate() - 29);
        startInput.value = localDateValue(periodStart) < data.data_period.start ? data.data_period.start : localDateValue(periodStart);
      }
      if (!endInput.value || endInput.value < data.data_period.start || endInput.value > data.data_period.end) endInput.value = data.data_period.end;
      loadDateRange();
    }
    createChart("insights-chart", data.hourly_average.map(item => hourLabel(item.hour)), data.hourly_average.map(item => item.rentals));
    const summaries = data.summaries || {};
    const groups = [
      ["Weekday vs weekend", summaries.weekday_weekend_average, { weekdays: "Weekdays", weekends: "Weekends" }],
      ["Seasonal average", summaries.season_average, { "1": "Spring", "2": "Summer", "3": "Fall", "4": "Winter" }],
      ["Weather category average", summaries.weather_average, { "1": "Clear / partly cloudy", "2": "Mist / cloudy", "3": "Light precipitation", "4": "Heavy precipitation" }],
      ["Year-over-year profile", summaries.yearly_average, {}],
      ["Temperature quartiles", summaries.temperature_band_average, {}]
    ].filter(([, values]) => values && Object.keys(values).length);
    if (Array.isArray(data.feature_importance) && data.feature_importance.length) {
      const featureLabels = { yr: "Dataset year", mnth: "Month", hr: "Hour", weathersit: "Weather", temp: "Temperature", atemp: "Feels-like temperature", hum: "Humidity", windspeed: "Wind speed", workingday: "Working day", weekday: "Weekday", holiday: "Holiday", season: "Season" };
      groups.push(["Model feature importance · not causal", Object.fromEntries(data.feature_importance.map(item => [item.feature, item.importance])), featureLabels]);
    }
    $("#insight-breakdowns").innerHTML = groups.map(([title, values, labels]) => {
      const importance = title.startsWith("Model feature importance");
      return `<div class="breakdown"><h3>${esc(title)}</h3>${Object.entries(values).map(([key, value]) => `<div class="breakdown-row"><span>${esc(labels[key] || `Category ${key}`)}</span><b>${value == null ? "Unavailable" : importance ? `${(Number(value) * 100).toFixed(1)}% relative importance` : `${fmt(value)} rentals/hour`}</b></div>`).join("")}</div>`;
    }).join("") || '<div class="empty-mini">No calendar or weather summaries are available for this dataset.</div>';
    $("#metric-rentals").textContent = fmt(data.total_rentals);
    $("#metric-rentals-foot").textContent = `${fmt(data.row_count)} historical hourly observations`;
    $("#metric-peak").textContent = hourLabel(data.summaries.peak_hour);
    $("#metric-peak-foot").textContent = `${fmt(data.summaries.peak_hour_average)} average rentals/hour`;
    if (data.hourly_by_regime?.length) {
      const regimeLabels = data.hourly_by_regime.map(item => hourLabel(item.hour));
      const regimeSets = [
        { label: "Working day", data: data.hourly_by_regime.map(item => item.workingday), borderColor: "#43d6c3", backgroundColor: "#43d6c3" },
        { label: "Weekend / non-working", data: data.hourly_by_regime.map(item => item.weekend_or_nonworking), borderColor: "#b89af7", backgroundColor: "#b89af7" }
      ];
      createComparisonChart("dashboard-chart", regimeLabels, regimeSets);
      createComparisonChart("regime-chart", regimeLabels, regimeSets);
    } else createChart("dashboard-chart", data.hourly_average.map(item => hourLabel(item.hour)), data.hourly_average.map(item => item.rentals));
    const signals = [
      [`${hourLabel(data.summaries.peak_hour)} is the historical peak`, `This hour had the highest average, at ${fmt(data.summaries.peak_hour_average)} rentals per recorded hour.`],
      [`${fmt(data.summaries.mean_hourly_rentals)} mean rentals per hour`, `${fmt(data.row_count)} hourly records analyzed with ${fmt(data.missing_values)} missing values across loaded columns.`],
      ["Descriptive—not causal", "Observed patterns are historical associations, not guarantees or causal findings."]
    ];
    if ($("#demand-signals")) $("#demand-signals").innerHTML = signals.map(([title, body]) => `<div class="signal"><span class="signal-icon">◷</span><div><b>${esc(title)}</b><p>${esc(body)}</p></div></div>`).join("");
    loadCalendarMonth(state.calendar.year, state.calendar.month);
    renderDriversAndOps(data);
  }
  async function loadDateRange() {
    const start = $("#range-start").value, end = $("#range-end").value;
    if (!start || !end) return;
    if (start > end) { toast("Start date must be on or before end date.", true); return; }
    try {
      const result = await api(`/api/insights/range?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`);
      state.rangeSummary = result;
      if (!result.available) {
        $("#range-total").textContent = "—"; $("#range-average").textContent = "—"; $("#range-peak").textContent = "—"; $("#range-days-count").textContent = "0";
        showChartFallback($("#range-chart"), result.message || "No daily observations in this date range.");
        return;
      }
      $("#range-total").textContent = fmt(result.total_rentals);
      $("#range-average").textContent = fmt(result.average_daily_rentals);
      $("#range-peak").textContent = `${new Date(`${result.peak_day.date}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })} · ${fmt(result.peak_day.rentals)}`;
      $("#range-days-count").textContent = fmt(result.days_with_data);
      createChart("range-chart", result.daily.map(item => new Date(`${item.date}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })), result.daily.map(item => item.rentals), "Completed rentals per day", "#4d9fe3");
      $("#ai-summary-result").classList.add("hidden");
    } catch (error) {
      showChartFallback($("#range-chart"), error.message);
      toast(`Could not analyze date range: ${error.message}`, true);
    }
  }
  async function loadAiStatus() {
    try {
      const status = await api("/api/insights/ai/status");
      state.aiAvailable = status.available;
      $("#ai-status-note").textContent = status.available ? `Connected · ${status.model}` : "Optional · configure server-side Groq key to enable";
      $("#ai-summary-button").disabled = !status.available;
      $("#ai-summary-button").title = status.available ? "Generate an AI explanation of selected-range aggregates" : "AI is not configured; date-range analytics still work";
      $("#ai-summary-button").textContent = status.available ? "Explain this range" : "AI not connected";
    } catch {
      state.aiAvailable = false;
      $("#ai-status-note").textContent = "AI status unavailable · historical analytics still work";
      $("#ai-summary-button").disabled = true;
    }
  }
  async function explainDateRange() {
    const button = $("#ai-summary-button");
    if (!state.rangeSummary?.available) { toast("Select a date range with source data first.", true); return; }
    busy(button, true, "Asking AI…");
    const output = $("#ai-summary-result"); output.textContent = "Generating a cautious operations brief from the selected historical aggregates…"; output.classList.remove("hidden");
    try {
      const response = await api("/api/insights/ai-summary", { method: "POST", body: JSON.stringify({ start_date: state.rangeSummary.start_date, end_date: state.rangeSummary.end_date }), timeoutMs: 25000 });
      output.textContent = response.explanation;
      $("#ai-status-note").textContent = `${response.provider} · ${response.model} · based on selected range`;
      toast("AI operations brief is ready.");
    } catch (error) {
      output.textContent = error.message;
      toast(error.message, true);
    } finally { busy(button, false); }
  }
  function renderDriversAndOps(data) {
    const names = { hr: "Hour of day", atemp: "Feels-like temperature", temp: "Temperature", yr: "Dataset year", workingday: "Working-day status", hum: "Humidity", weathersit: "Weather category", weekday: "Day of week", mnth: "Month", season: "Season", windspeed: "Wind speed", holiday: "Holiday" };
    const drivers = (data.feature_importance || []).slice(0, 3);
    if (drivers[0]) $("#dashboard-driver").textContent = `Top driver: ${names[drivers[0].feature] || drivers[0].feature}`;
    $("#top-drivers").innerHTML = drivers.length ? drivers.map((driver, index) => `<div class="driver"><div class="driver-head"><b>${index + 1}. ${esc(names[driver.feature] || driver.feature)}</b><span>${(driver.importance * 100).toFixed(1)}%</span></div><div class="driver-track"><i style="width:${Math.max(3, Math.min(100, driver.importance * 100))}%"></i></div></div>`).join("") : '<div class="empty-mini">Train a supported model to calculate feature importance.</div>';
    const guidance = data.ops_guidance || [];
    $("#ops-guidance").innerHTML = guidance.length ? guidance.map((item, index) => `<div class="ops-guidance-item"><span>${index + 1}</span><div><b>${esc(item.title)}</b><p>${esc(item.evidence)}</p><small>${esc(item.action)}</small></div></div>`).join("") : '<div class="empty-mini">Operational guidance is unavailable until the data contains the required calendar/weather fields.</div>';
    renderOpsPrintBrief(data);
  }
  function renderScenarioComparison(first, second, firstWeather, secondWeather) {
    const firstExact = Number(first.predicted_rentals_unrounded ?? first.predicted_rentals);
    const secondExact = Number(second.predicted_rentals_unrounded ?? second.predicted_rentals);
    const exactDelta = secondExact - firstExact;
    const displayedDelta = second.predicted_rentals - first.predicted_rentals;
    const percentDelta = firstExact ? exactDelta / firstExact * 100 : 0;
    $("#scenario-wrap").classList.remove("hidden");
    $("#scenario-values").innerHTML = `<div class="scenario-chip"><span>${esc(firstWeather)}</span><b>${fmt(first.predicted_rentals)}</b><small>${firstExact.toFixed(2)} unrounded</small></div><div class="scenario-chip"><span>${esc(secondWeather)}</span><b>${fmt(second.predicted_rentals)}</b><small>${secondExact.toFixed(2)} unrounded</small></div>`;
    const sameDisplayed = displayedDelta === 0;
    const deltaLabel = exactDelta === 0
      ? "This model gives the same estimate for both weather inputs in this scenario."
      : sameDisplayed
        ? `Both round to ${fmt(first.predicted_rentals)} rentals. Before rounding, the second scenario differs by ${Math.abs(exactDelta).toFixed(2)} rentals/hour (${Math.abs(percentDelta).toFixed(2)}%).`
        : `The second scenario is ${Math.abs(displayedDelta)} rentals/hour ${displayedDelta > 0 ? "higher" : "lower"} (${Math.abs(percentDelta).toFixed(1)}% before rounding).`;
    $("#scenario-delta").classList.toggle("no-change", sameDisplayed);
    $("#scenario-delta").innerHTML = `<b>${sameDisplayed ? "No displayed difference" : `${displayedDelta > 0 ? "+" : "-"}${fmt(Math.abs(displayedDelta))} rentals/hour`}</b><span>${esc(deltaLabel)}</span>`;
    const weatherImportance = state.insights?.feature_importance?.find(item => item.feature === "weathersit")?.importance;
    $("#scenario-context").textContent = weatherImportance == null
      ? "Both predictions use the same trained model and all the same inputs except weather."
      : `Same trained model and same other inputs. Weather accounts for ${(weatherImportance * 100).toFixed(1)}% relative model importance overall; individual scenarios may still round to the same rental count.`;
    if (window.Chart) {
      hideChartFallback($("#scenario-chart"));
      state.charts.scenario?.destroy();
      const lightTheme = document.body.dataset.theme === "light";
      state.charts.scenario = new Chart($("#scenario-chart"), {
        type: "bar",
        data: { labels: [firstWeather, secondWeather], datasets: [{ label: "Estimated citywide rentals", data: [first.predicted_rentals, second.predicted_rentals], backgroundColor: ["#168b79", "#4389c4"], borderRadius: 5, maxBarThickness: 58 }] },
        options: { maintainAspectRatio: false, responsive: true, plugins: { legend: { display: false }, tooltip: { callbacks: { afterLabel: context => `Unrounded estimate: ${[firstExact, secondExact][context.dataIndex].toFixed(2)}` } } }, scales: { x: { grid: { display: false }, ticks: { color: lightTheme ? "#526970" : "#8196a1", font: { size: 9 } } }, y: { beginAtZero: true, grid: { color: lightTheme ? "#243f4b16" : "#ffffff0b" }, ticks: { color: lightTheme ? "#526970" : "#8196a1", font: { size: 9 } }, title: { display: true, text: "Rentals per hour", color: lightTheme ? "#526970" : "#8196a1", font: { size: 9 } } } } }
      });
    } else showChartFallback($("#scenario-chart"), "Chart library unavailable; both actual model estimates and their difference are shown above.");
  }
  function renderOpsPrintBrief(data) {
    const period = data.data_period ? `${data.data_period.start} to ${data.data_period.end}` : "Historical observation dates unavailable";
    $("#brief-period").textContent = `${fmt(data.row_count)} source hourly records · observed ${period}`;
    const evaluation = state.metrics?.evaluated
      ? `${state.metrics.selected_model}: holdout MAE ${fmt(state.metrics.mae)} rentals/hour, RMSE ${fmt(state.metrics.rmse)}, R² ${Number(state.metrics.r2).toFixed(3)}. Test ${state.metrics.test_period?.start || ""} to ${state.metrics.test_period?.end || ""}.`
      : "Holdout evaluation is unavailable.";
    $("#brief-model").textContent = evaluation;
    const names = { hr: "Hour of day", atemp: "Feels-like temperature", temp: "Temperature", yr: "Dataset year", workingday: "Working-day status", hum: "Humidity", weathersit: "Weather category", weekday: "Day of week", mnth: "Month", season: "Season", windspeed: "Wind speed", holiday: "Holiday" };
    const drivers = (data.feature_importance || []).slice(0, 3);
    $("#brief-drivers").innerHTML = drivers.map(item => `<li><b>${esc(names[item.feature] || item.feature)}</b> — ${(item.importance * 100).toFixed(1)}% relative model importance.</li>`).join("") || "<li>Feature importance unavailable.</li>";
    $("#brief-actions").innerHTML = (data.ops_guidance || []).map(item => `<li><b>${esc(item.title)}.</b> ${esc(item.evidence)} ${esc(item.action)}</li>`).join("") || "<li>Operational evidence unavailable.</li>";
  }
  function renderMetrics(data, info) {
    state.metrics = data;
    if (state.insights?.available) renderOpsPrintBrief(state.insights);
    if (!data.evaluated) { $("#quality-empty").classList.remove("hidden"); $("#quality-content").classList.add("hidden"); $("#monitor-errors").textContent = "Unavailable"; return; }
    $("#quality-empty").classList.add("hidden"); $("#quality-content").classList.remove("hidden");
    $("#quality-model").textContent = data.selected_model; $("#quality-version").textContent = `Version ${info?.metadata?.model_version || "unavailable"}`;
    $("#quality-mae").textContent = fmt(data.mae); $("#quality-rmse").textContent = fmt(data.rmse);
    $("#quality-r2").textContent = Number.isFinite(data.r2) ? Number(data.r2).toFixed(3) : "Unavailable";
    const seasonalBaseline = (data.baselines || []).find(item => item.model_name === "Same hour last week");
    $("#dashboard-mae").textContent = `MAE ${fmt(data.mae)} rentals/hour`;
    $("#dashboard-baseline").textContent = seasonalBaseline ? `Weekly baseline MAE ${fmt(seasonalBaseline.mae)}` : "Naive baseline unavailable";
    const verdict = $("#baseline-verdict");
    if (seasonalBaseline) {
      const beatsSeasonal = data.mae <= seasonalBaseline.mae;
      verdict.className = `notice ${beatsSeasonal ? "notice-info" : "notice-warn"}`;
      verdict.innerHTML = `<span>${beatsSeasonal ? "✓" : "!"}</span><div><b>${beatsSeasonal ? "Model beats" : "Model does not beat"} the same-hour-last-week naive baseline</b><p>Selected model MAE ${fmt(data.mae)} vs baseline MAE ${fmt(seasonalBaseline.mae)} rentals/hour on the same chronological holdout. ${data.selected_beats_mean_baseline ? `It improves on the training-mean baseline by ${fmt(data.mae_improvement_vs_mean_baseline_pct)}%.` : "It does not beat the training-mean baseline; prefer the benchmark until improved."}</p></div>`;
    }
    $("#test-period").textContent = data.test_period ? `Chronological test: ${data.test_period.start} – ${data.test_period.end} · ${fmt(data.test_period.rows)} rows` : "Test period unavailable";
    $("#quality-table").innerHTML = (data.comparison || []).map(row => `<tr><td>${esc(row.model_name)}</td><td>${fmt(row.mae)}</td><td>${fmt(row.rmse)}</td><td>${row.model_name === data.selected_model ? '<span class="selected-badge">SELECTED MODEL</span>' : row.baseline ? '<span class="priority-badge medium">NAIVE BASELINE</span>' : 'Compared model'}</td></tr>`).join("");
    if (Array.isArray(data.test_series) && data.test_series.length) {
      const labels = data.test_series.map(row => row.timestamp.slice(0, 16).replace("T", " "));
      createComparisonChart("quality-actual-chart", labels, [
        { label: "Actual", data: data.test_series.map(row => row.actual), borderColor: "#43d6c3", backgroundColor: "#43d6c3" },
        { label: "Predicted", data: data.test_series.map(row => row.predicted), borderColor: "#b89af7", backgroundColor: "#b89af7" }
      ]);
      createComparisonChart("quality-residual-chart", labels, [
        { label: "Residual", data: data.test_series.map(row => row.residual), borderColor: "#f0b96b", backgroundColor: "#f0b96b" },
        { label: "Zero error", data: data.test_series.map(() => 0), borderColor: "#617783", backgroundColor: "#617783", borderDash: [4, 4] }
      ]);
    }
    $("#monitor-errors").textContent = `${fmt(data.mae)} / ${fmt(data.rmse)}`;
  }
  function renderMonitoring(health, info, insights, metrics) {
    state.health = health;
    $("#monitor-api").textContent = health ? "Available" : "Unavailable"; $("#monitor-api-foot").textContent = health ? `API v${health.application_version}` : "Backend could not be reached";
    $("#monitor-model").textContent = info?.available ? "Available" : "Unavailable"; $("#monitor-model-foot").textContent = info?.metadata?.model_name || info?.message || "No artifact metadata";
    $("#monitor-trained").textContent = info?.metadata?.trained_at ? new Date(info.metadata.trained_at).toLocaleDateString() : "Unavailable";
    const dataset = insights?.available ? `${fmt(insights.row_count)} rows · ${fmt(insights.missing_values)} missing` : insights?.message || "Unavailable";
    const model = info?.available ? `${esc(info.metadata.model_name)} · v${esc(info.metadata.model_version)}` : "Unavailable";
    $("#monitor-details").innerHTML = `<div class="detail-row"><span>Dataset</span><b>${esc(dataset)}</b></div><div class="detail-row"><span>Model artifact</span><b>${model}</b></div><div class="detail-row"><span>Last forecast request</span><b id="last-forecast-status">${esc(state.lastForecast)}</b></div><div class="detail-row"><span>Evaluation</span><b>${metrics?.evaluated ? "Available" : "Not evaluated"}</b></div>`;
    $("#metric-model").textContent = info?.available ? "Available" : "Unavailable"; $("#metric-version").textContent = info?.available ? `${info.metadata.model_name} · v${info.metadata.model_version}` : "Train model to enable estimates";
  }
  async function refreshAll() {
    pill("pending", "Checking API");
    const [health, info, insights, metrics] = await Promise.allSettled([api("/api/health"), api("/api/model/info"), api("/api/insights"), api("/api/metrics")]);
    const healthy = health.status === "fulfilled";
    pill(healthy ? "online" : "offline", healthy ? "API connected" : "API offline");
    const h = healthy ? health.value : null, i = info.status === "fulfilled" ? info.value : null, d = insights.status === "fulfilled" ? insights.value : null, m = metrics.status === "fulfilled" ? metrics.value : null;
    renderInsights(d || { available: false, message: insights.status === "rejected" ? insights.reason.message : "Historical insights are unavailable." });
    renderMetrics(m || { evaluated: false }, i);
    renderMonitoring(h, i, d, m);
    const setupRequired = healthy && (!h.dataset_available || !h.model_available);
    $("#setup-banner").classList.toggle("hidden", !setupRequired);
    if (setupRequired && config.AUTO_SETUP_ON_MISSING && !state.setupAttempted) {
      state.setupAttempted = true;
      initializeProject(true);
    }
    if (i?.available && !state.autoForecastAttempted) {
      state.autoForecastAttempted = true;
      await loadTodayForecast();
    }
    if (!healthy) { $("#dashboard-notice").innerHTML = `<span>!</span><div><b>Backend unavailable</b><p>Start FastAPI to load data, forecasts, and action recommendations. No demo values are substituted.</p></div>`; }
  }
  async function loadTodayForecast() {
    try {
      const result = await api("/api/forecast/today");
      renderTodayForecast(result);
      toast(`Today’s outlook is ready · peak scenario ${hourLabel(result.peak_hour)}.`, false);
    } catch (error) {
      $("#metric-forecast-foot").textContent = "Today scenario unavailable";
      $("#today-suggestions").innerHTML = `<div class="empty-mini">${esc(error.message)}</div>`;
      toast(`Could not prepare today's scenario: ${error.message}`, true);
    }
  }
  async function initializeProject(showToast = false) {
    const button = $("#initialize-button");
    if (button) busy(button, true, "Downloading & training…");
    $("#setup-title").textContent = "Preparing CityCycle with source data";
    $("#setup-message").textContent = "Fetching the original UCI Bike Sharing archive, validating hour.csv, then training and evaluating models. This may take a minute.";
    try {
      const result = await api("/api/setup/initialize", { method: "POST", timeoutMs: 90000 });
      $("#setup-title").textContent = "CityCycle data and model are ready";
      $("#setup-message").textContent = result.message;
      $("#setup-banner").classList.add("hidden");
      if (showToast) toast("Original data installed and model training completed.");
      await refreshAll();
    } catch (error) {
      $("#setup-title").textContent = "Automatic setup needs attention";
      $("#setup-message").textContent = error.message;
      if (button) busy(button, false, "Retry setup");
      toast(error.message, true);
    }
  }
  function formPayload(form) {
    const values = new FormData(form);
    const selectedDate = new Date(`${values.get("forecast_date")}T12:00:00`);
    const month = selectedDate.getMonth() + 1;
    const weekday = selectedDate.getDay();
    return { forecast_date: values.get("forecast_date"), year: 1, season: Math.floor((month - 1) / 3) + 1, month, hour: Number(values.get("hour")), holiday: values.has("holiday") ? 1 : 0, weekday, workingday: weekday !== 0 && weekday !== 6 ? 1 : 0, weather: Number(values.get("weather")), temperature: Number(values.get("temperature")), feels_like: Number(values.get("feels_like")), humidity: Number(values.get("humidity")), windspeed: Number(values.get("windspeed")) };
  }
  $("#forecast-form [name=forecast_date]").addEventListener("change", event => deriveCalendarInputs(event.target.value));
  function deriveCalendarInputs(value) {
    if (!value) return;
    const date = new Date(`${value}T12:00:00`);
    const month = date.getMonth() + 1;
    const day = date.getDay();
  }
  function applyScenarioPreset(preset) {
    const form = $("#forecast-form");
    const now = new Date();
    const date = new Date(now);
    if (preset === "commute" || preset === "rain") {
      date.setDate(date.getDate() + ((8 - date.getDay() + 7) % 7 || 7));
      $("[name=hour]", form).value = "8";
      $("[name=weather]", form).value = preset === "rain" ? "3" : "1";
      $("[name=holiday]", form).checked = false;
    } else if (preset === "weekend") {
      date.setDate(date.getDate() + ((6 - date.getDay() + 7) % 7 || 7));
      $("[name=hour]", form).value = "13";
      $("[name=weather]", form).value = "1";
      $("[name=holiday]", form).checked = false;
    } else {
      $("[name=hour]", form).value = String(now.getHours());
      $("[name=weather]", form).value = String(state.todayForecast?.weather_context?.weather || 1);
      $("[name=holiday]", form).checked = false;
    }
    $("[name=forecast_date]", form).value = localDateValue(date);
    deriveCalendarInputs($("[name=forecast_date]", form).value);
    const typical = state.todayForecast?.weather_context;
    if (typical && preset !== "rain") {
      for (const name of ["temperature", "feels_like", "humidity", "windspeed"]) {
        $(`[name="${name}"]`, form).value = typical[name];
        $(`output[data-for="${name}"]`, form).textContent = Number(typical[name]).toFixed(2);
      }
    }
    $$(".preset-card").forEach(button => button.classList.toggle("active", button.dataset.preset === preset));
    form.requestSubmit();
  }
  $$(".preset-card").forEach(button => button.addEventListener("click", () => applyScenarioPreset(button.dataset.preset)));
  $("#reset-scenario").addEventListener("click", () => applyScenarioPreset("today"));
  $$("#forecast-form input[type=range]").forEach(input => input.addEventListener("input", event => {
    const output = $(`output[data-for="${event.target.name}"]`);
    if (output) output.textContent = Number(event.target.value).toFixed(2);
  }));
  function busy(button, busy, text) { button.disabled = busy; button.dataset.original ??= button.textContent; button.textContent = busy ? (text || "Working…") : (text || button.dataset.original); }
  $("#forecast-form").addEventListener("submit", async event => {
    event.preventDefault(); state.autoForecastAttempted = true; const form = event.currentTarget; deriveCalendarInputs($("[name=forecast_date]", form).value); const payload = formPayload(form); const button = $("button[type=submit]", form); const error = $("#forecast-error"); error.classList.add("hidden"); busy(button, true);
    try {
      const result = await api("/api/forecast", { method: "POST", body: JSON.stringify(payload) });
      $("#forecast-result").classList.add("hidden"); $("#forecast-output").classList.remove("hidden"); $("#forecast-number").textContent = fmt(result.predicted_rentals); $("#forecast-meta").textContent = `${result.model_name} · v${result.model_version} · citywide hourly estimate`;
      $("#forecast-output .result-label").textContent = `ESTIMATED RENTALS · ${hourLabel(payload.hour)}`;
      state.lastForecast = `Success · ${new Date().toLocaleTimeString()}`; $("#last-forecast-status").textContent = state.lastForecast;
      $("#optimizer-form [name=forecast_demand]").value = result.predicted_rentals;
      $("#optimizer-form [name=period]").value = scenarioPeriod(payload);
      $("#optimizer-form").requestSubmit();
      if (event.isTrusted) toast(`Scenario ready · ${fmt(result.predicted_rentals)} predicted rentals at ${hourLabel(payload.hour)}.`);
    } catch (err) { error.textContent = err.message; error.classList.remove("hidden"); state.lastForecast = `Failed · ${err.message}`; toast(err.message, true); }
    finally { busy(button, false); }
  });
  function scenarioPeriod(payload) {
    const selectedDate = new Date(`${payload.forecast_date}T12:00:00`);
    return `${selectedDate.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" })} · ${hourLabel(payload.hour)}`;
  }
  $("#compare-button").addEventListener("click", async event => {
    const button = event.currentTarget; busy(button, true);
    try {
      const weatherNames = { 1: "Clear / partly cloudy", 2: "Cloudy / mist", 3: "Light precipitation", 4: "Heavy precipitation" };
      const form = $("#forecast-form"); deriveCalendarInputs($("[name=forecast_date]", form).value); const baseline = formPayload(form);
      const firstWeather = baseline.weather === 3 ? 3 : 1;
      const secondWeather = baseline.weather === 3 ? 1 : 3;
      const firstScenario = { ...baseline, weather: firstWeather };
      const secondScenario = { ...baseline, weather: secondWeather };
      const compareResult = await api("/api/forecast/compare", { method: "POST", body: JSON.stringify({ scenario_a: firstScenario, scenario_b: secondScenario }) });
      const firstLabel = weatherNames[firstWeather] || "Selected weather";
      const secondLabel = weatherNames[secondWeather];
      renderScenarioComparison(compareResult.scenario_a, compareResult.scenario_b, firstLabel, secondLabel);
      if (event.isTrusted) toast("Both weather scenarios were evaluated with the same trained model and matched calendar/temperature inputs.");
    } catch (err) { toast(err.message, true); }
    finally { busy(button, false); }
  });
  $("#optimizer-form").addEventListener("submit", async event => {
    event.preventDefault(); const data = new FormData(event.currentTarget); const capacity = data.get("capacity"); const budget = data.get("budget");
    const request = { forecast_demand: Number(data.get("forecast_demand")), threshold: Number(data.get("threshold")), capacity: capacity === "" ? null : Number(capacity), budget: budget === "" ? null : Number(budget), priority: data.get("priority"), period: data.get("period") };
    try {
      const result = await api("/api/actions/recommend", { method: "POST", body: JSON.stringify(request) });
      const recommendations = result.recommendations;
      $("#recommendations").innerHTML = recommendations.length ? recommendations.map(item => `<article class="recommendation"><h3>${esc(item.title)}</h3><p>${esc(item.explanation)}</p><div class="recommendation-foot"><span>${esc(item.period)} · ${fmt(item.estimated_demand)} rentals</span><span class="priority-badge ${item.priority.toLowerCase()}">${esc(item.priority)}</span></div><button class="button button-secondary save-recommendation" data-title="${esc(item.title)}" data-description="${esc(item.explanation)}" data-period="${esc(item.period)}" data-demand="${item.estimated_demand}" data-priority="${esc(item.priority)}">Add to action center</button></article>`).join("") : '<div class="empty-mini">Demand is at or below the configured threshold. No intervention is recommended.</div>';
      if (event.isTrusted) toast(recommendations.length ? `${recommendations.length} ops suggestion${recommendations.length === 1 ? "" : "s"} ready for review.` : "No elevated demand under this threshold.");
    } catch (err) { $("#recommendations").innerHTML = `<div class="inline-error">${esc(err.message)}</div>`; }
  });
  $("#recommendations").addEventListener("click", async event => {
    const button = event.target.closest(".save-recommendation"); if (!button) return;
    try { await api("/api/actions", { method: "POST", body: JSON.stringify({ title: button.dataset.title, description: button.dataset.description, period: button.dataset.period, estimated_demand: Number(button.dataset.demand), priority: button.dataset.priority, status: "PENDING_APPROVAL" }) }); toast("Recommendation added to Action Center."); await loadActions(); }
    catch (err) { toast(err.message, true); }
  });
  async function loadActions() {
    try {
      const result = await api("/api/actions"); state.actions = result.actions || []; $("#action-count").textContent = state.actions.filter(action => action.status === "PENDING_APPROVAL").length; renderActions();
    } catch (err) { $("#actions-table").innerHTML = `<tr><td colspan="5" class="table-empty">${esc(err.message)}</td></tr>`; }
  }
  function renderActions() {
    const status = $("#status-filter").value, priority = $("#priority-filter").value;
    const rows = state.actions.filter(item => (status === "ALL" || item.status === status) && (priority === "ALL" || item.priority === priority));
    $("#actions-table").innerHTML = rows.length ? rows.map(item => {
      const canDecide = item.status === "PENDING_APPROVAL" || item.status === "EDITED";
      const reviewControls = canDecide
        ? `<button class="approve-action" data-action="approve" data-id="${esc(item.id)}" title="Approve this recommendation; this does not dispatch staff or bikes">Approve</button><button class="reject-action" data-action="reject" data-id="${esc(item.id)}" title="Record that this recommendation was declined">Reject</button><button data-action="edit" data-id="${esc(item.id)}" title="Edit the recommendation note before deciding">Edit note</button>`
        : '<span class="decision-locked">Decision recorded</span>';
      return `<tr><td><span class="action-title">${esc(item.title)}</span><span class="action-desc">${esc(item.description)}</span></td><td>${esc(item.period)}${item.estimated_demand == null ? "" : `<br><small>${fmt(item.estimated_demand)} estimated rentals</small>`}</td><td><span class="priority-badge ${item.priority.toLowerCase()}">${esc(item.priority)}</span></td><td><span class="status-badge ${item.status.toLowerCase()}">${esc(item.status.replaceAll("_", " "))}</span></td><td><div class="row-actions">${reviewControls}</div></td></tr>`;
    }).join("") : '<tr><td colspan="5" class="table-empty">No actions match these filters. Forecast demand above your threshold to create review suggestions.</td></tr>';
  }
  function confirmDialog(title, message, confirmText = "Continue") {
    return new Promise(resolve => {
      const backdrop = document.createElement("div"); backdrop.className = "action-confirm";
      backdrop.innerHTML = `<div class="confirm-box"><h2>${esc(title)}</h2><p>${esc(message)}</p><div class="confirm-actions"><button class="button button-secondary" data-answer="no">Cancel</button><button class="button button-primary" data-answer="yes">${esc(confirmText)}</button></div></div>`;
      backdrop.addEventListener("click", event => { const answer = event.target.closest("[data-answer]"); if (answer) { backdrop.remove(); resolve(answer.dataset.answer === "yes"); } }); document.body.append(backdrop);
    });
  }
  function editActionDialog(action) {
    return new Promise(resolve => {
      const backdrop = document.createElement("div"); backdrop.className = "action-confirm";
      backdrop.innerHTML = `<section class="confirm-box edit-action-dialog" role="dialog" aria-modal="true" aria-labelledby="edit-action-title"><h2 id="edit-action-title">Edit recommendation note</h2><p>${esc(action.title)}</p><label for="edit-action-description">Updated note</label><textarea id="edit-action-description" maxlength="1000">${esc(action.description)}</textarea><div class="confirm-actions"><button class="button button-secondary" data-answer="no">Cancel</button><button class="button button-primary" data-answer="yes">Save as edited</button></div></section>`;
      backdrop.addEventListener("click", event => {
        const answer = event.target.closest("[data-answer]");
        if (!answer) return;
        const description = $("#edit-action-description", backdrop).value.trim();
        backdrop.remove();
        resolve(answer.dataset.answer === "yes" ? description : null);
      });
      document.body.append(backdrop);
      $("#edit-action-description", backdrop).focus();
    });
  }
  $("#actions-table").addEventListener("click", async event => {
    const button = event.target.closest("button[data-action]"); if (!button) return;
    const action = state.actions.find(item => item.id === button.dataset.id); if (!action) return;
    try {
      let patch;
      if (button.dataset.action === "approve") { if (!await confirmDialog("Approve this recommendation?", "Approval records a human decision only; it does not execute an operational change.", "Approve")) return; patch = { status: "APPROVED" }; }
      else if (button.dataset.action === "reject") { if (!await confirmDialog("Reject this recommendation?", "This updates the action status. The action can no longer be considered pending.", "Reject")) return; patch = { status: "REJECTED" }; }
      else { const description = await editActionDialog(action); if (description === null) return; if (!description) { toast("Description cannot be blank.", true); return; } patch = { description, status: "EDITED" }; }
      await api(`/api/actions/${encodeURIComponent(action.id)}`, { method: "PATCH", body: JSON.stringify(patch) }); toast("Action updated successfully."); await loadActions();
    } catch (err) { toast(err.message, true); }
  });
  $("#export-actions").addEventListener("click", () => {
    const status = $("#status-filter").value, priority = $("#priority-filter").value;
    const rows = state.actions.filter(item => (status === "ALL" || item.status === status) && (priority === "ALL" || item.priority === priority));
    const fields = ["id", "title", "description", "priority", "period", "estimated_demand", "status", "created_at"];
    const csv = [fields.join(","), ...rows.map(row => fields.map(field => `"${String(row[field] ?? "").replace(/"/g, '""')}"`).join(","))].join("\r\n");
    const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); link.download = "citycycle-actions.csv"; link.click(); URL.revokeObjectURL(link.href); toast(`Exported ${rows.length} visible action(s).`);
  });
  $("#status-filter").addEventListener("change", renderActions); $("#priority-filter").addEventListener("change", renderActions); $("#load-actions").addEventListener("click", loadActions);
  $("#quality-refresh").addEventListener("click", refreshAll); $("#monitor-refresh").addEventListener("click", refreshAll);
  $("#refresh-button").addEventListener("click", async () => { await refreshAll(); await loadTodayForecast(); });
  $("#initialize-button").addEventListener("click", () => { state.setupAttempted = true; initializeProject(true); });
  $("#calendar-prev").addEventListener("click", () => {
    const { year, month } = state.calendar;
    if (year === 2011 && month === 1) return;
    const previous = new Date(year, month - 2, 1);
    loadCalendarMonth(previous.getFullYear(), previous.getMonth() + 1);
  });
  $("#calendar-next").addEventListener("click", () => {
    const { year, month } = state.calendar;
    if (year === 2012 && month === 12) return;
    const next = new Date(year, month, 1);
    loadCalendarMonth(next.getFullYear(), next.getMonth() + 1);
  });
  $("#calendar-grid").addEventListener("click", event => {
    const dayButton = event.target.closest(".calendar-day");
    if (dayButton) selectCalendarDay(Number(dayButton.dataset.day));
  });
  $("#range-form").addEventListener("submit", event => { event.preventDefault(); $$("[data-range-days]").forEach(button => button.classList.remove("active")); loadDateRange(); });
  $$("[data-range-days]").forEach(button => button.addEventListener("click", () => {
    const days = Number(button.dataset.rangeDays);
    const end = new Date(`${$("#range-end").value}T12:00:00`);
    end.setDate(end.getDate());
    const start = new Date(end); start.setDate(start.getDate() - days + 1);
    const lowerBound = $("#range-start").min;
    $("#range-start").value = localDateValue(start) < lowerBound ? lowerBound : localDateValue(start);
    $("#range-end").value = localDateValue(end);
    $$("[data-range-days]").forEach(preset => preset.classList.toggle("active", preset === button));
    loadDateRange();
  }));
  $("#ai-summary-button").addEventListener("click", explainDateRange);
  $("#ai-summary-button").setAttribute("aria-label", "Generate a Groq AI explanation for the selected date range");
  $("#theme-toggle").addEventListener("click", () => {
    const next = document.body.dataset.theme === "light" ? "dark" : "light";
    applyTheme(next);
    try { localStorage.setItem("citycycle-theme", next); } catch { /* Theme still applies for this page session. */ }
    if (state.insights?.available) renderInsights(state.insights);
    if (state.rangeSummary?.available) loadDateRange();
    if (state.todayForecast) renderTodayForecast(state.todayForecast);
    if (state.metrics?.evaluated) renderMetrics(state.metrics, null);
  });
  $("#print-ops").addEventListener("click", () => window.print());
  $$(".nav-item").forEach(item => item.addEventListener("click", () => showPage(item.dataset.page)));
  $$('[data-goto]').forEach(item => item.addEventListener("click", () => showPage(item.dataset.goto)));
  $("#menu-toggle").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
  document.addEventListener("click", event => { if (window.innerWidth <= 820 && $("#sidebar").classList.contains("open") && !$("#sidebar").contains(event.target) && !$("#menu-toggle").contains(event.target)) $("#sidebar").classList.remove("open"); });
  $("#dashboard-date").textContent = "Source observation period loads from the dataset";
  const initialDate = new Date();
  const localDate = localDateValue(initialDate);
  $("#forecast-form [name=forecast_date]").value = localDate;
  $("#forecast-form [name=hour]").value = String(initialDate.getHours());
  deriveCalendarInputs(localDate);
  for (const [name, value] of Object.entries({ temperature: 0.5, feels_like: 0.5, humidity: 0.5, windspeed: 0.2 })) {
    $(`#forecast-form [name="${name}"]`).value = String(value);
    $(`#forecast-form output[data-for="${name}"]`).textContent = value.toFixed(2);
  }
  initializeTheme();
  loadAiStatus();
  refreshAll();
})();
