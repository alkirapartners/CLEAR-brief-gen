---
name: alkira-customer
description: "Alkira knowledge base for Channel Account Managers working with VAR partners. Use this skill whenever the user mentions Alkira in any context — deal strategy, partner enablement, use case identification, competitive positioning, pricing, objection handling, case studies, or partner communications. Also trigger when the user shares a call transcript, meeting notes, or describes a partner's customer opportunity and needs help mapping it to Alkira use cases. Trigger on cloud networking, network-as-a-service, multicloud, MPLS replacement, firewall consolidation, extranet, or backbone-as-a-service discussions. If the user is creating partner-facing deliverables (cheat sheets, one-pagers, quick reference docs), drafting emails to partners, or analyzing a deal opportunity, use this skill."
---

# Alkira Knowledge Base — Channel Account Manager Edition

This skill is built for Blake's role as a Channel Account Manager. It's your Alkira reference layer for enabling partners, strategizing on deals, creating partner-facing deliverables, and identifying use cases from real conversations.

## How to Use This Skill

**You are not selling directly to end customers.** You're enabling VAR partners to sell Alkira effectively. That means the skill should help you:

1. **Identify use cases from context** — When Blake shares a call transcript, meeting notes, or describes a partner's customer opportunity (e.g., "Western Midstream is looking at..."), map the situation to Alkira's five solution categories, pull relevant proof points, and suggest how the partner should position Alkira.

2. **Deal strategy** — Help think through how to position Alkira for a specific partner's customer opportunity. What's the entry point? Which use cases apply? What proof points will resonate? What objections should the partner expect?

3. **Partner communications** — Draft emails to partners (not end customers). These might be about deal-specific guidance, Alkira updates, competitive intel, or enablement materials. Tone should be collaborative and peer-to-peer — you're coaching them, not selling to them.

4. **Partner-facing deliverables** — Create cheat sheets, quick reference docs, use case summaries, competitive one-pagers, or other materials that partners can use with their customers.

5. **Competitive & objection support** — When a partner encounters pushback or competitive pressure, provide the right positioning and responses they can use.

When matching tone: you're talking *to partners* about *their customers*. Be direct, practical, and specific. Partners don't need marketing fluff — they need "here's exactly what to say and why."

---

## Company Overview

Alkira was founded in 2018 by Amir Khan and Atif Khan (deep networking pedigree), launched in 2020, and has raised $176M from Sequoia Capital, Kleiner Perkins, Google Ventures, Koch Disruptive Technologies, and Tiger Global. Named "Leader" and "Fast Mover" in the GigaOm Radar Report and CRN SaaS/Cloud Startup of the Year.

**Category:** Network infrastructure-as-a-service (NaaS is the broad category; Alkira differentiates as network *infrastructure*-as-a-service)

**Tagline:** Network Infrastructure On-Demand

**Elevator Pitch (for partners to use with their customers):** Alkira is to networking what cloud hyperscalers are to compute and storage. It's the only platform that provides global network infrastructure-as-a-service to connect geographically dispersed users and applications across cloud, data center, and WAN environments — without deploying any physical infrastructure, agents, complex overlays, or configurations. You draw your entire network on an intuitive digital design canvas and deploy it in a single click. No hardware to buy, no software to download, no cloud to learn.

---

## Target Buyers (Who Partners Should Be Selling To)

**Technical buyers:** Network Architects, Cloud Architects, Security Architects, IT Managers/Directors, CloudOps

**Business decision-makers:** CIOs, CTOs, CISOs, VPs of Infrastructure

**Sweet spot:** Mid-to-large enterprises dealing with cloud migration, multicloud complexity, M&A integration, or network modernization.

---

## The Problem Alkira Solves

Traditional networking can't keep up with the speed, scale, and agility demands of AI workloads, cloud applications, and distributed work. Enterprises end up stitching together point solutions — one for branches, another for remote users, another for cloud, another for security. This creates layers of complexity: disaggregated WANs, multi-cloud networks, distributed security, no consolidated visibility, and lots of hardware. The result is high OpEx, capital-intensive infrastructure, human inefficiency, unnecessary risk, and troubleshooting delays.

Compute and storage are agile. Development is agile. **The network is not.** Alkira changes that.

---

## Fit Rules

These rules decide whether a company is an Alkira fit. They set the fit score and decide which angles a brief may present.

**One clear use case is enough.** A company does not have to check every box. Any single one of these, with evidence, is a fit:

| Use case | ID | What counts |
|---|---|---|
| Multi-cloud or hybrid cloud connectivity | `multi_cloud` | Two or more clouds, or cloud plus data centers, that must reach each other. A cloud network built by hand counts: ExpressRoute, Direct Connect, Virtual WAN, Transit Gateway hub-and-spoke. Hand-built cloud-native networking is a positive signal, never a negative one. One cloud is enough when the network around it is complex. |
| China-to-global connectivity | `china_global` | Workloads, plants or users in mainland China that must reach systems outside it, or the reverse. |
| Firewall or security-services consolidation | `firewall_consolidation` | Firewalls or security services deployed per cloud, per region or per VPC or VNet, or a stated plan to consolidate them in the cloud. |
| M&A | `m_and_a` | An acquisition, merger, divestiture, carve-out or separation that happened in the last three months, or that is announced and not yet completed. See "M&A: recent or pending" below. |
| Network modernization | `network_modernization` | An MPLS exit, backbone replacement, data-center exit, an SD-WAN or SASE programme, or any stated network or infrastructure modernization. |
| Sites opening or closing at scale | `site_rollout` | Stores, plants, branches or clinics being opened, closed or moved in numbers. |
| Business-partner connectivity | `partner_connectivity` | Suppliers, customers, joint ventures or other third parties that need controlled network access. |

**Supporting only.** These strengthen a use case and are never an angle on their own: a cost programme with network contracts in scope; a new CIO or head of infrastructure; a lean network team.

**Never fit evidence.** Never present these as a reason to pursue: a new CEO or CFO; SAP, Workday or other ERP projects; generic "digital transformation"; headcount or hiring statistics; product recalls; earnings.

**Evidence quality.** First-hand evidence is the company's own careers site and job postings, its filings and annual report, its press releases, and a cloud vendor's case study about it. Trade press is second-hand, and so is a job board's copy of a posting. A data-broker profile is a last resort and must be labelled as one. So is an encyclopedia. Current means the source is dated within about the last two years.

**The word "network".** Fit evidence is about the IT network: the WAN, cloud connectivity, data centers, firewalls, and the people who run them. Many companies also call their business footprint a network: a delivery network, a logistics network, a store network, a distribution network, a branch or dealer network. That is not the IT network. Example: UPS reports "Network Reconfiguration" and "Network of the Future", programmes that close sorting buildings and consolidate package routes. Neither is network modernization. The building closures can support `site_rollout`, because sites are closing at scale, and nothing more. A `network_modernization` angle needs at least one fact that names network technology: MPLS, SD-WAN, SASE, a backbone, a data-center exit, a network engineering programme.

**Plant networks.** In the technical snapshot, plant networks means industrial control systems: OT, SCADA, PLCs, the networks on a plant floor, and how they are kept apart from IT. RFID readers, package scanners, store Wi-Fi and vehicle telematics are not plant networks. Example: the RFID readers UPS puts in its package cars are a tracking product. Leave the line empty for a company with no plants.

**Risk-factor language is not evidence.** The risk factors in a filing list what could go wrong, in wording most filers share: technology infrastructure may be aging, an integration may be harder than expected, the company depends on transition services. None of it shows that anything is happening. Evidence is what the company did or announced, with a date.

**M&A: recent or pending.** M&A is the strongest reason to engage, and only while it is live. An M&A event counts when it happened in the last three months, or when the deal is announced and not yet completed. The event is the announcement or the completion of an acquisition, merger, divestiture, carve-out or separation, dated by the company's own press release or filing. Examples: HF Sinclair's separation of its lubricants business, announced on 28 July and still to be completed, qualifies when a brief is written in October. A carve-out completed in January does not qualify in October: the deal is done and more than three months old, and transition services that are still running do not bring it back.

- A qualifying M&A angle goes first in the brief. The lead line and the first question open with it.
- An M&A angle names what has to be connected or separated: the sites, the systems, or the businesses on each side. A deal with a price and a closing date and nothing to connect is news, not an angle.
- A completed deal outside the three months is not an angle, cannot lead and cannot raise the score. It may appear as one line of background inside another angle's evidence when it explains that angle, and nowhere else.
- Give each M&A angle the date of its event and say whether the deal is pending or completed. The date is checked against the page, and the three-month rule is applied to it afterwards. A deal is pending only on the page's own words: a sentence from the company's release or filing that gives the expected completion, a condition still to be met, or says the deal has not closed. Without that sentence the deal is treated as completed on its date.

**A specific first-hand fact.** Every angle rests on at least one specific fact from a first-hand source: a posting on the company's careers site, a filing, a press release on its own site, a cloud vendor's case study about it. Trade press or a data broker alone does not make an angle. The fact does not have to be dated: an older or undated first-hand fact still shows the use case, as Anker's undated AWS case study shows its China-to-global split, and the score then stops at 3. An accounting adjustment after a closed sale is not a specific fact about the network. Never add an angle to reach three. Example: a parts retailer with one strong network-modernization angle gains nothing from a third angle built on a divestiture that closed the year before and a line of risk-factor language.

---

## Five Core Solution Categories (Entry Points)

These are the five reasons customers buy Alkira. When Blake describes a partner's deal or shares a call transcript, map the customer's situation to one or more of these entry points.

### 1. Hybrid / Single / Multi-Cloud Networking
**Trigger signals:** Customer is migrating to cloud, connecting multiple clouds, moving workloads between providers, or running AI workloads across environments.

Connect anything to anything — network to cloud, within clouds, between clouds, branch offices together. AI workloads aren't constrained by data gravity or a single provider's toolset.

**Key metrics:** 96% less calendar time to add a cloud environment (average across the Nemertes study's customers). Alkira's own figures: 80% less provisioning time and 40-60% lower TCO.

### 2. Network & Security Services Consolidation
**Trigger signals:** Customer has firewalls everywhere, running different security policies per cloud/VPC, wants to reduce security infrastructure footprint, or is paying too much for firewall licenses.

Move network services from data centers to the cloud. Centrally deploy security services within a region instead of per-VPC/VNET. Leverage the same firewalls for multiple use cases (N-S, E-W, Internet ingress/egress, multi-segment).

**Key metrics:** 73% fewer firewalls and 44% fewer network and security devices for cloud connectivity (averages across the Nemertes study's customers). Separately, one large healthcare enterprise went from 76 firewalls to 14.

### 3. Backbone-as-a-Service (MPLS Replacement)
**Trigger signals:** Customer is paying for expensive MPLS circuits, needs low-latency connectivity across regions, shutting down data centers, or looking at SD-WAN migration.

Secure, high-availability, low-latency connectivity across geographic regions on hyperscale cloud infrastructure. Alkira's partner TCO guide says customers that replace MPLS typically see 40-60% lower WAN connectivity costs while improving performance. Replaces MPLS, AWS Direct Connect, Azure ExpressRoute, or Google Cloud Dedicated Interconnect.

### 4. Extranet-as-a-Service (Business Partner / M&A Connectivity)
**Trigger signals:** Customer has M&A activity, needs to onboard business partners, is dealing with overlapping IP address spaces, or needs segmented third-party access.

Point-and-click connectivity with business partners — expose only the applications they need, inspect traffic, get full visibility. For M&A: bring in multiple networks as separate segments with resource-share capabilities. Handles overlapping IP address space.

**Key metrics:** 98% less staff time and 91% less calendar time to add an extranet partner (averages across the Nemertes study's customers).

### 5. Zero Trust Network Access (ZTNA)
**Trigger signals:** Customer is implementing zero trust, has distributed remote workforce, or needs per-user access controls.

Secure remote user access based on authentication, authorization, and group-based policies. Per-user segmentation with service autoscaling and pay-per-use pricing.

---

## How the Platform Works (Quick Reference for Partner Enablement)

**Two core components:**

**Alkira Portal** — The interface (UI, APIs, SDKs, Terraform) for building, deploying, managing, and monitoring the entire network from a single pane of glass. Visio-like click-and-provision experience.

**Cloud Exchange Points (CXPs)** — Network infrastructure-as-a-service fabric nodes. Full-stack networking: Active/Active, Full-Mesh, Routed, HA, deployed in multiple AZs, elastic (scale up/down). CXPs do four things:
1. **Global backbone:** Full-mesh connectivity between CXPs across regions
2. **On-prem & cloud connectivity:** Connect via AWS DX, Azure ER, SD-WAN, IPSec, remote access
3. **Network services insertion:** Deploy services from the Alkira marketplace (Alkira-native + third-party)
4. **Visibility & governance:** See and control how traffic flows across the entire network

**What Alkira is NOT:** Not an orchestration layer. Not software you install in your cloud tenant. Not an overlay. It's a true abstraction layer that leverages cloud providers' infrastructure to deliver network infrastructure as-a-service.

---

## Key Differentiators (Partner Talking Points)

These are the points partners should hammer when positioning Alkira:

- **Only** comprehensive, entirely virtual network infrastructure delivered as-a-service
- Full-stack networking and security in one platform
- Horizontally and vertically scalable with auto-detect for node/link failure
- End-to-end segmentation and micro-segmentation
- Third-party marketplace for network and security services
- Single-click provisioning of an entire global network
- Zero CAPEX via SaaS-like PAYG, subscription, or ELA options
- No cloud-specific expertise required

---

## Proof Points (Quick Reference Table)

Each figure says whose it is. A Nemertes figure is an average across the customers Nemertes interviewed for its study of Alkira customers. It is never one customer's result: never attach it to a named customer.

| Metric | Value |
|--------|-------|
| Less calendar time to add a cloud environment (Nemertes study average) | 96% |
| Fewer firewalls for cloud (Nemertes study average) | 73% |
| Fewer network and security devices for cloud connectivity (Nemertes study average) | 44% |
| Less staff time to manage cloud networks (Nemertes study average) | 47% |
| Less staff time to add an extranet partner (Nemertes study average) | 98% |
| Less calendar time to add an extranet partner (Nemertes study average) | 91% |
| Provisioning time reduction (Alkira's own figure) | 80% |
| TCO reduction (Alkira's own figure) | 40-60% |

---

## Competitive Positioning

When partners encounter these alternatives at a customer, here's how to position Alkira:

### DIY Cloud Native (AWS Cloud WAN, Azure Virtual WAN)
Manual, complex, single-provider, requires deep cloud expertise, inherits all cloud-native limitations.

### DIY Co-location (Equinix, etc.)
Long provisioning, high CAPEX/OPEX, no automation, no agility, complexity scales exponentially.

### Gateway-based MCN / Orchestration (Aviatrix, Prosimo, Nefeli/Cloudflare)
Agent-based, overlay on cloud native constructs — all limitations still apply. Customers must deploy, manage, maintain, and upgrade infrastructure including scheduled software upgrades. Not true as-a-service.

### Cloud Security Providers (CASB/SWG)
Pure security play — doesn't solve connectivity. Cloud expertise still needed.

**vs. Cato Networks specifically:** Alkira is *inside* the cloud. Cato is not.

**The Alkira difference:** End-to-end enterprise-grade connectivity between on-prem, cloud, and remote users. As-a-service, on-demand, like a virtual Equinix you can spin up in any region in minutes with automatic routing.

---

## Use Case Identification from Transcripts and Conversations

When Blake shares a call transcript, meeting notes, or describes a partner's customer opportunity:

1. **Identify the customer's situation** — What industry, what infrastructure, what pain points?
2. **Map to entry points** — Which of the five solution categories apply? Often multiple will.
3. **Pull relevant proof points** — Match industry and use case to case studies (see `references/case-studies.md`)
4. **Flag competitive dynamics** — Is there an incumbent? Which competitor category?
5. **Recommend positioning** — How should the partner frame Alkira for this specific opportunity?
6. **Suggest next steps** — What should the partner propose as a next step with the customer?

Be specific. Don't give generic advice. Use the customer's actual situation and map it to Alkira's world.

---

## Reference Files

For deeper detail, read the appropriate reference file:

- **`references/case-studies.md`** — The Story Matching Table (every story tagged by situation and industry), the named case studies and the Nemertes study's case studies. Use when you need specific customer proof points or industry-relevant examples.

- **`references/pricing.md`** — CXP sizing, connector sizing, services, data charges, and business models (ELA, PAYG, Commit Consumption, Subscription). Use when discussing pricing or building proposals.

- **`references/objection-handling.md`** — Responses to 11 common objections (happy with current solution, already in cloud, no budget, not a decision maker, security concerns, etc.). Use when partners encounter pushback and need guidance on how to respond.
