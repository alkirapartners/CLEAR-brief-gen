---
name: alkira-brief-template
description: "Research checklist, fit scoring and content rules for the Alkira Opportunity Brief. Load this skill before researching a company or writing a brief."
---

# Alkira Opportunity Brief: Research, Scoring and Content

The brief answers one question for a partner: is this company an Alkira fit, and what do we attach to? A sales rep reads it and so does an engineer. The fit rules and the use-case IDs are in the Alkira knowledge base, under Fit Rules.

---

## Research Checklist

Work in this order. Drop a line of enquiry when it stops producing dated, specific facts, and follow the lead you just found instead.

1. **Identify the company.** Legal entity, ticker and exchange, headquarters, website. If the name is ambiguous, choose the most likely entity, say which one you chose, and name the look-alikes you excluded.
2. **Work the fit rules.** For each use case look for evidence, best sources first:

| Order | Source | What it gives |
|---|---|---|
| 1 | The company's own careers site and job postings | The real network: clouds, ExpressRoute or Direct Connect, Virtual WAN or Transit Gateway, SD-WAN, firewall vendors, BGP, plant networks, team size |
| 2 | Filings and the annual report | Acquisitions, divestitures, site counts, data-center and IT programmes, China operations |
| 3 | Press releases | Dated triggers: a deal closed, sites opened, a programme announced |
| 4 | Cloud-vendor case studies | Which clouds, since when, and for what |
| 5 | Trade press | Second-hand confirmation and executive interviews |
| 6 | Data brokers and encyclopedias | Last resort only, for a basic nothing else gives. They are labelled as a last resort in the brief |

3. **Technical snapshot.** Clouds, cloud connectivity, WAN, firewalls, data centers, plant networks. Keep the specific terms the source uses.
4. **People.** Who owns the network and the infrastructure. Give a name only when a first-hand source gives it. Otherwise give the role.
5. **Company basics.** Revenue, employees, industry, ownership.

A fact counts only when it is stated on a page that was opened. Search-result summaries merge companies and invent names, so never take a fact from one.

---

## Alkira Fit Score

The score reflects the strength and freshness of the best use case, never the number of boxes checked.

| Score | Meaning |
|---|---|
| 5 | Two different use cases, each resting on a first-hand source of its own, and at least one of those sources dated within the last two years |
| 4 | One use case resting on a first-hand source dated within the last two years |
| 3 | A use case whose evidence is second-hand, undated or older than two years |
| 2 | A plausible use case with no evidence found |
| 1 | No use case |

A dated first-hand source is the trigger: a job posting with its posted date, a filing, a press release. An angle that rests only on trade press or another second-hand source cannot lift the score above 3, however many such angles there are. Two angles that lean on the same single page are one use case told twice. These limits are checked against the sources after the brief is written, and a score they do not support is lowered.

"Could not find out" is different from "weak fit". What the research looked for and did not find belongs under What we couldn't confirm, and stays out of the score reasoning.

---

## What a Brief Contains

- **Company.** The resolved name and identifiers, and a note saying which entity was chosen when the name was ambiguous.
- **Stats.** Headquarters, revenue, employees, industry, ownership, and a cloud-and-network headline such as "Azure, ExpressRoute and Virtual WAN, SD-WAN". Leave a value empty when it was not found.
- **Fit.** The score, a one-sentence verdict, and a lead line: what to open with and whom to call.
- **Why this account, why now.** One to three angles. Each angle has its evidence with date and source, what Alkira does about it, and one customer story with its result. Present an angle only when it has evidence. One strong angle is a complete brief. Never pad to three. A score of 1 or 2 has no angles.
- **Technical snapshot.** One line each for clouds, cloud connectivity, WAN, firewalls, data centers and plant networks. A line is sourced or left empty, and an empty line prints as "not found". Keep the specific terms: ExpressRoute, Virtual WAN, BGP, Palo Alto.
- **Who to talk to.** Names only from first-hand sources, roles otherwise.
- **Questions.** Three or four when the brief has several angles, fewer for a one-angle brief. Each has what to listen for and the Alkira angle. Technical vocabulary is welcome when the evidence uses it.
- **What we couldn't confirm.** Plain statements of what the research looked for and did not find.
- **What would raise the score.** The one or two facts that would move the score up.

### Customer stories

Choose the story from the Story Matching Table in the case studies. Match the angle's situation first, then the industry. Give the story's ID. When nothing matches, use `none`.

### Questions

A good question names a specific fact about the company, fits in one sentence, and sounds like a person asking.

Good:
- "You closed the Northwind acquisition in the spring. Which of its networks still run on their own?" Listen for: overlapping address space, a deadline to merge. Alkira angle: both networks run as separate segments on one fabric until cutover.
- "The senior network engineer posting lists ExpressRoute and a Virtual WAN hub-and-spoke. Who builds a new hub today, and how long does one take?" Listen for: hand-built hubs, weeks of lead time. Alkira angle: a new region is a design change deployed in a day.

Bad:
- "What is your current approach to managing network policy?" It names no fact about the company.
- "Is digital transformation a priority this year?" It rests on evidence that is never fit evidence.

---

## Quality Gate

- [ ] Every angle has evidence from an opened page, with a date where the source gives one
- [ ] No angle rests on supporting-only or never-fit evidence
- [ ] The number of angles matches the evidence and is never padded
- [ ] Every technical snapshot line is sourced or empty
- [ ] Every named person comes from a first-hand source
- [ ] Every customer story is a row in the Story Matching Table
- [ ] The verdict states the use case and how fresh its evidence is
- [ ] No AI writing patterns (see the stop-slop rules)
