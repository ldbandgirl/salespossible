---
name: pipeline_analysis
description: Analyse the full sales pipeline — health, velocity, forecast, and recommended actions
triggers:
  - pipeline analysis
  - pipeline health
  - forecast
  - revenue forecast
  - analyse pipeline
  - pipeline review
  - win rate
  - deal velocity
tools:
  - crm_lookup
  - execute_python
version: 1
auto_improve: true
---

# Pipeline Analysis Skill

## Purpose
Give a data-driven view of the sales pipeline: what's healthy, what's stuck,
what's at risk, and what to prioritise to hit the number.

## Execution Steps

1. **Pull all open deals** from CRM
2. **Execute Python** to calculate metrics (deal velocity, average stage duration, forecast)
3. **Identify patterns** — which deals are moving, which are stalled, which are at risk
4. **Surface actions** — prioritised list of what to do next

## Metrics to Calculate

```python
# Example calculations for the execute_python tool
deals = [...]  # from CRM

import statistics

# Deal velocity = avg days from open to close (won deals)
# Stage duration = how long each deal has been in current stage
# Weighted forecast = sum(deal_value * stage_probability)
# Win rate = won / (won + lost)

STAGE_PROBABILITIES = {
    "prospecting": 0.10,
    "qualification": 0.25,
    "proposal": 0.50,
    "negotiation": 0.75,
    "closed_won": 1.0,
    "closed_lost": 0.0,
}
```

## Output Format

```
## Pipeline Analysis — [Date]

### Summary
| Metric | Value |
|--------|-------|
| Total open deals | N |
| Total pipeline value | $X |
| Weighted forecast | $Y |
| Average deal size | $Z |
| Average days to close | N days |
| Win rate (last 90 days) | X% |

---

### Deal Health
🟢 **On track** (N deals, $X value)
- [Deal name] — [stage] — [days to expected close] days
  
🟡 **At risk** (N deals, $X value) — stalled >14 days or close date past
- [Deal name] — [reason for risk]

🔴 **Critical** (N deals, $X value) — stalled >30 days or significantly overdue
- [Deal name] — [specific concern] — [recommended action]

---

### Stage Breakdown
| Stage | # Deals | Value | Avg Days in Stage |
|-------|---------|-------|-------------------|
| ...   | ...     | ...   | ...               |

---

### Priority Actions
1. **[Deal name]** — [specific action to take] — [why now]
2. ...

---

### Forecast
- **Commit** (likely to close this period): $X
- **Best case** (if everything goes right): $Y
- **Gap to target**: $Z
```
