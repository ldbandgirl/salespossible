---
name: meeting_prep
description: Prepare a comprehensive meeting brief for an upcoming sales call or demo
triggers:
  - meeting prep
  - prepare for
  - call prep
  - before my call
  - before my meeting
  - demo prep
  - brief me
  - prep for
tools:
  - web_search
  - crm_lookup
  - execute_python
version: 1
auto_improve: true
---

# Meeting Prep Skill

## Purpose
Give the sales rep everything they need to walk into a call prepared:
company context, contact background, open deal status, likely objections,
and a talk track outline.

## Execution Steps

1. **CRM lookup** — pull all records for this company/contact, including notes and deal history
2. **Web research** — company recent news (last 90 days), contact LinkedIn, industry trends
3. **Synthesise** into a structured brief
4. **Prepare open questions** tailored to the deal stage
5. **Anticipate objections** with prepared responses

## Output Format

```
# Meeting Brief: [Meeting Type] with [Name] at [Company]
**Date/Time**: [if provided]
**Deal stage**: [current stage]
**Deal value**: [if known]

---

## Company Snapshot
- **What they do**: [1-2 sentences]
- **Size**: [employees / revenue]
- **Industry**: [sector]
- **Recent news**: [most relevant items — funding, hires, product, challenges]
- **Likely priorities right now**: [inferred from news/context]

---

## Contact Profile
- **Name**: [name]
- **Title**: [title]
- **Background**: [brief — previous roles, tenure, focus areas]
- **What they care about**: [inferred priorities]
- **Tone to use**: [formal/casual/technical/etc.]

---

## Deal History
- **First contact**: [date]
- **Previous conversations**: [key points, commitments, concerns raised]
- **Blockers identified**: [anything in the way]
- **Where we are**: [honest assessment of deal health]

---

## Agenda (Suggested)
1. [Opening — reference something specific from last conversation or news]
2. [Discovery / deepening understanding of their situation]
3. [Demo or proposal walkthrough — if applicable]
4. [Address likely objections proactively]
5. [Close on next step — specific, time-boxed]

---

## Likely Objections & Responses

| Objection | Response |
|-----------|----------|
| "We don't have budget" | [tailored response] |
| "We're already using [competitor]" | [tailored response] |
| "We need to involve [other stakeholder]" | [tailored response] |

---

## Key Questions to Ask
1. ...
2. ...
3. ...

---

## Success Criteria for This Call
What does a good outcome look like?
- [Specific agreed next step]
- [Any commitment secured]
```

## Notes
- If deal is in early stages, focus more on discovery questions
- If deal is at proposal/negotiation, focus on objection handling and close
- Always end the brief with the ONE most important thing to achieve in this call
