---
name: crm_lookup
description: Look up contacts, companies, or deals in the CRM and summarise their status
triggers:
  - look up
  - find contact
  - check CRM
  - pull up
  - what's the status
  - deal status
  - pipeline
  - open deals
  - stalled
tools:
  - crm_lookup
  - crm_update_deal
version: 1
auto_improve: true
---

# CRM Lookup Skill

## Purpose
Retrieve and summarise CRM records. Surface action items, overdue follow-ups,
and missing data.

## Execution Steps

1. **Call crm_lookup** with the search query and record_type
2. **Parse results** — extract key fields (contact info, deal stage, last activity, notes)
3. **Identify gaps** — missing email, no follow-up date, overdue close date
4. **Summarise** in a scannable format with recommended actions

## Output Format

For a single contact:
```
### [Name] — [Company]
- **Role**: ...
- **Email**: ...
- **Deal stage**: ...
- **Last activity**: ...
- **Notes**: ...

⚠️ Action needed: [specific issue]
✅ Recommended next step: [action]
```

For pipeline overview:
```
### Pipeline Summary
| Deal | Company | Stage | Amount | Close Date | Days in Stage |
|------|---------|-------|--------|------------|---------------|
| ...  | ...     | ...   | ...    | ...        | ...           |

**Stalled deals (>14 days):** ...
**Missing close dates:** ...
**Overdue follow-ups:** ...
```

## Notes
- Flag deals that have been in the same stage for more than 14 days
- Highlight contacts with no email address
- Surface deals without a scheduled next step
