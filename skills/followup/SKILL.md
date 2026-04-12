---
name: followup
description: Identify overdue follow-ups in the pipeline and draft re-engagement messages
triggers:
  - follow up
  - follow-up
  - check in
  - overdue
  - haven't heard
  - gone quiet
  - no response
  - bump
  - reminder
tools:
  - crm_lookup
  - crm_update_deal
  - email_draft
version: 1
auto_improve: true
---

# Follow-Up Skill

## Purpose
Never let a deal die from neglect. Identify stalled deals and contacts who need
a follow-up, and draft appropriate re-engagement messages with a real reason to reach out.

## Execution Steps

1. **Pull pipeline** from CRM — look for deals with no activity in 7+ days
2. **Categorise** each stalled deal by last stage + likely reason for silence
3. **Draft a follow-up message** for each — with a genuine hook, not "just checking in"
4. **Suggest timing** for each outreach (avoid Mondays AM, Fridays PM)

## Follow-Up Framework

| Situation | Days Silent | Approach |
|-----------|------------|----------|
| After proposal sent | 5-7 | Reference a specific part of the proposal; ask one clarifying question |
| After discovery call | 3-5 | Send agreed-upon materials; confirm next step |
| Post-demo | 3-4 | Address the top concern raised in the demo |
| Long-stalled deal | 30+ | New angle: something changed (their news, your news, industry trend) |
| After lost deal | 90+ | Gentle re-engagement, no pressure, offer new value |

## Follow-Up Message Rules
- Never say "just checking in" — it signals you have nothing new to offer
- Always have a reason: new data, relevant article, result with similar company, question
- Keep it short: 3–5 sentences max
- One specific CTA
- Reference the last touchpoint by name ("When we spoke last Thursday...")

## Output Format

For each stalled deal, show:
```
### [Contact Name] — [Company] ([Deal Stage])
- **Last activity**: [date]
- **Days silent**: [N]
- **Situation**: [brief context]

**Recommended action**: [specific step]

**Draft message**:
---
[email or message draft]
---
```

Then summarise:
- Total stalled deals found
- Highest priority (by deal value × urgency)
- Suggested outreach order
