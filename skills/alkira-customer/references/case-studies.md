# Alkira Case Studies Reference

## Story Matching Table

Pick the customer story for an angle from this table. Match on **situation** first, then on **industry**. Name the customer only when Public is `yes`; otherwise use the Customer label as written. Cite a story by its ID. The Result column is the only proof you may attach to a story.

Situations: `multi_cloud` (multi-cloud or hybrid cloud connectivity), `china_global` (China-to-global connectivity), `firewall_consolidation` (firewall or security-services consolidation), `m_and_a` (acquisition, divestiture, carve-out), `network_modernization` (MPLS exit, backbone replacement, data-center exit, SD-WAN or SASE), `site_rollout` (stores or sites opening or closing at scale), `partner_connectivity` (business-partner or third-party connectivity).

| ID | Customer | Public | Situations | Industry | Result |
|---|---|---|---|---|---|
| koch | Koch Industries | yes | multi_cloud, m_and_a, firewall_consolidation | Manufacturing | Significant reduction in network complexity across acquisitions and business units. |
| tekion | Tekion | yes | multi_cloud | Automotive technology | Simplified multi-cloud networking and improved operational efficiency. |
| sp-global | S&P Global | yes | multi_cloud | Financial services | Streamlined network operations across global cloud environments. |
| michaels | Michaels | yes | site_rollout, network_modernization, multi_cloud | Retail | About 1,400 stores in the U.S. and Canada connected to Google Cloud in three weeks, ahead of peak season, with no new network infrastructure. |
| software-datacenter | A software company | no | site_rollout | Software | The equivalent of a new datacenter deployed in far less time than a physical build. |
| nemertes-1 | A software company (Nemertes study) | no | site_rollout | Software | 90% time savings deploying a datacenter equivalent with no physical build-out. |
| nemertes-2 | A software company (Nemertes study) | no | network_modernization | Software | 99%+ availability after replacing an unreliable network. |
| nemertes-3 | A software company (Nemertes study) | no | firewall_consolidation | Software | One security posture across environments and a reduced firewall count. |
| nemertes-4 | A software company (Nemertes study) | no | m_and_a, multi_cloud | Software | An acquired company's cloud networks integrated in days instead of months, with a 1650% increase in cloud app deployments. |
| nemertes-5 | A financial services firm (Nemertes study) | no | multi_cloud | Financial services | 200% more cloud environments supported without adding network staff. |
| nemertes-6 | A financial services firm (Nemertes study) | no | network_modernization | Financial services | 88% less operational time for network changes, from days to hours. |
| nemertes-7 | A financial services firm (Nemertes study) | no | network_modernization | Financial services | One view across all environments and 50% faster provisioning. |
| nemertes-8 | A financial services firm (Nemertes study) | no | firewall_consolidation | Financial services | Consistent policy enforcement and a simpler audit posture across distributed infrastructure. |
| nemertes-9 | A healthcare provider (Nemertes study) | no | network_modernization | Healthcare | 99.9% availability between regions, with cost avoided against an MPLS build. |
| nemertes-10 | A healthcare enterprise (Nemertes study) | no | multi_cloud, firewall_consolidation | Healthcare | Firewalls consolidated from 76 to 14 while scaling multicloud. |
| nemertes-11 | A manufacturer (Nemertes study) | no | multi_cloud | Manufacturing | 99%+ availability and zero unplanned outages for manufacturing operations. |
| nemertes-12 | A manufacturing and biotech company (Nemertes study) | no | network_modernization | Manufacturing | Network hubs reduced by 60-88%. |

When no story's Situations include the angle's use case, use the ID `none` rather than stretching a story.

---

## Named Case Studies

### Michaels
- **Industry:** Retail. One of North America's largest arts and crafts retailers, with about 1,400 stores across the U.S. and Canada
- **Use case:** Store rollout at national scale, store-to-cloud connectivity into Google Cloud, moving off datacenter-centric networking
- **Situation:** Michaels was moving more workloads to Google Cloud while every store still backhauled through private datacenters. Earlier outages tied to proprietary datacenter equipment had disrupted operations and cost sales. The team needed all stores connected to Google Cloud ahead of peak holiday demand
- **What they did:** Deployed Alkira Cloud Exchange Points to connect Google Cloud with the stores. They validated the approach in a small number of stores, then rolled it out to the whole estate
- **Outcome:** About 1,400 stores connected in three weeks, with no new capital investment and no new network infrastructure. An individual store went from zero to full connectivity within hours. The rollout began as peak-season preparation for a 4X increase in traffic
- **Who said so:** Wei Dong, Vice President and Chief Information Security Officer, and Sreenu Sampati, Director of Security Engineering, both at Michaels
- **Why Alkira:** Removing redundant backhaul to private datacenters was a primary objective, and the network had to be highly available through peak season
- **Source:** Futuriom Networking Leadership Brief, "Michaels' Three-Week Shift to Network Infrastructure as a Service", sponsored by Alkira. The customer is public and may be named

### Tekion
- **Industry:** Automotive Technology / SaaS
- **Use case:** Cloud networking and connectivity
- **Outcome:** Simplified multi-cloud networking, improved operational efficiency
- **Why Alkira:** Needed to connect distributed cloud workloads without building complex infrastructure

### Koch Industries
- **Industry:** Manufacturing / Conglomerate (Fortune 100)
- **Use case:** Multi-cloud networking, M&A integration, security consolidation
- **Outcome:** Significant reduction in network complexity across a massive enterprise footprint
- **Why Alkira:** Needed scalable, consistent connectivity across acquisitions and diverse business units
- **Notable:** Koch Disruptive Technologies is also an Alkira investor — they saw the value firsthand as a customer

### S&P Global
- **Industry:** Financial Services / Data & Analytics
- **Use case:** Cloud networking, security integration
- **Outcome:** Streamlined network operations across global cloud environments
- **Why Alkira:** Required enterprise-grade multi-cloud connectivity with integrated security

### Software Company — Needed New Datacenter Fast
- **Industry:** Software / Technology
- **Use case:** Rapid datacenter deployment
- **Outcome:** Deployed equivalent of a new datacenter in dramatically less time than traditional approach
- **Why Alkira:** Urgently needed new datacenter-equivalent capacity without the lead time of physical infrastructure

---

## Nemertes Case Studies

These come from the Nemertes Research 2024 report covering 12 enterprise deployments. Each is anonymized by industry but includes real metrics.

### Software / Technology (4 cases)

**Case 1 — Datacenter Deployment**
- Challenge: Needed rapid datacenter equivalent without physical build-out
- Outcome: 90% time savings on deployment
- Key metric: Dramatic reduction in provisioning timeline

**Case 2 — Network Reliability**
- Challenge: Unreliable network affecting application performance
- Outcome: 99%+ availability achieved
- Key metric: Near-zero downtime post-deployment

**Case 3 — Security Consolidation**
- Challenge: Fragmented security across environments
- Outcome: Unified security posture, reduced firewall count
- Key metric: Significant reduction in security infrastructure

**Case 4 — M&A Cloud Integration**
- Challenge: Integrating acquired company's cloud networks
- Outcome: 1650% increase in cloud app deployments post-integration
- Key metric: What used to take months took days

### Financial Services (4 cases)

**Case 5 — Multicloud Networking**
- Challenge: Managing connectivity across multiple cloud providers
- Outcome: 200% increase in cloud environments supported
- Key metric: Tripled cloud footprint without adding network staff

**Case 6 — Network Simplification**
- Challenge: Overly complex network architecture
- Outcome: 88% reduction in operational time for network changes
- Key metric: Network changes from days to hours

**Case 7 — Network Unification**
- Challenge: Disparate network tools and visibility gaps
- Outcome: Single pane of glass across all environments
- Key metric: 50% faster provisioning

**Case 8 — Compliance & Security**
- Challenge: Meeting regulatory requirements across distributed infrastructure
- Outcome: Consistent policy enforcement, simplified audit posture
- Key metric: Reduced compliance preparation time significantly

### Healthcare (2 cases)

**Case 9 — Inter-Region Connectivity**
- Challenge: Connecting healthcare facilities across regions with high availability requirements
- Outcome: 99.9% availability
- Key metric: Significant cost avoidance vs. traditional MPLS approach

**Case 10 — Agile Multicloud**
- Challenge: Needed to rapidly scale cloud environments for new workloads
- Outcome: Agile multicloud deployment with integrated security
- Key metric: Firewall consolidation from 76 to 14 (one large healthcare account)

### Manufacturing & Biotech (2 cases)

**Case 11 — Cloud Reliability**
- Challenge: Ensuring consistent network performance for manufacturing operations
- Outcome: 99%+ availability
- Key metric: Zero unplanned outages post-deployment

**Case 12 — Hub Consolidation**
- Challenge: Too many network hubs creating management overhead
- Outcome: Consolidated hub architecture, reduced by 60-88%
- Key metric: Dramatic reduction in infrastructure to manage

---

## Customers by Use Case

Summary of how customers map to Alkira's five entry points:

**Hybrid / Multi-Cloud Networking:** Most common entry point. Enterprises migrating to cloud or connecting multiple clouds. Includes Fortune 500 companies across industries.

**Security & Services Consolidation:** Healthcare and financial services enterprises consolidating firewall footprint. Strongest proof point: 76 → 14 firewalls.

**Backbone-as-a-Service:** Companies replacing expensive MPLS circuits. 40% cost savings, 80% faster deployment.

**Extranet / Business Partner Connectivity:** Companies with M&A activity or large partner ecosystems. 98% reduction in partner onboarding time.

**ZTNA:** Distributed workforce companies implementing zero trust. Pay-per-use model with auto-scaling.

---

## Key Stats Quick Reference

Use these when you need a fast proof point:

- 96% decrease in cloud connection time
- 73-82% decrease in firewalls
- 44% reduction in network devices
- 47% reduction in management staff time
- 40-60% TCO reduction
- 80% faster network provisioning
- 98% faster partner onboarding
- 99-99.9% network availability
- 1650% increase in cloud app deployments (M&A case)
- 200% increase in cloud environments (financial services)
- 88% reduction in operational time for network changes
- 67-90% reduction in network engineering time
