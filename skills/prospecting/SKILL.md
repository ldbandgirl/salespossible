---
name: prospecting
description: Research a company or person to build a prospect profile and identify buying signals
triggers:
  - research
  - prospect
  - company info
  - tell me about
  - find out about
  - background on
  - who is
  - buying signals
tools:
  - web_search
  - crm_lookup
  - http_request
version: 1
auto_improve: true
---

# Prospecting Skill

## Purpose
Build a complete prospect profile before outreach or a call. Surface buying signals,
pain points, recent news, and decision-maker information.

## Execution Steps

1. **Web search** for the company name + recent news (funding, layoffs, product launches, leadership changes)
2. **Web search** for the specific contact (LinkedIn profile, role, background, recent activity)
3. **CRM lookup** to check if they're already in the system and what interactions exist
4. **Synthesise** findings into a structured profile

## Output Format

Return a prospect brief in this structure:

```
## Prospect Brief: [Name] at [Company]

### Company
- **Industry**: ...
- **Size**: ...
- **Recent news**: ...
- **Tech stack** (if known): ...
- **Funding status**: ...

### Contact
- **Role**: ...
- **Background**: ...
- **LinkedIn**: ...
- **Likely priorities**: ...

### Buying Signals
- ...

### Potential Pain Points
- ...

### Recommended Approach
One paragraph on how to open the conversation.

### Recommended Next Action
[Specific, time-boxed action]
```

## Notes
- If the CRM already has notes, reference them and focus on what's new
- Prioritise recent news (last 90 days) over older information
- If research is thin, flag it rather than speculating
