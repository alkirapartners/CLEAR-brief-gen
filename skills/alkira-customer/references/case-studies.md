# Alkira Case Studies Reference

## Story Matching Table

Pick the customer story for an angle from this table. Match on **situation** first, then on **industry**. Name the customer only when Public is `yes`; otherwise use the Customer label as written. Cite a story by its ID. The Result column is the only proof you may attach to a story.

Situations: `multi_cloud` (multi-cloud or hybrid cloud connectivity), `china_global` (China-to-global connectivity), `firewall_consolidation` (firewall or security-services consolidation), `m_and_a` (acquisition, divestiture, carve-out), `network_modernization` (MPLS exit, backbone replacement, data-center exit, SD-WAN or SASE), `site_rollout` (stores or sites opening or closing at scale), `partner_connectivity` (business-partner or third-party connectivity).

| ID | Customer | Public | Situations | Industry | Result |
|---|---|---|---|---|---|
| koch | Koch Industries | yes | multi_cloud, m_and_a, china_global | Manufacturing | Replaced 10 transport hubs with 2 Alkira Cloud Exchange Points, connects newly acquired companies to its infrastructure through Alkira, and expanded its network to mainland China. |
| tekion | Tekion | yes | multi_cloud | Automotive technology | One standard network for all cloud and multi-cloud connectivity, with greatly reduced IT time-to-service and international network expansion, run by a small IT team. |
| sp-global | S&P Global | yes | partner_connectivity, m_and_a, multi_cloud | Financial services | Combined networks after its merger with IHS Markit in 2 months, against its own estimate of 2.5 years, and runs extranet as a service on Alkira across multiple clouds. |
| chart | Chart Industries | yes | m_and_a, multi_cloud | Manufacturing | Grew from 40 to over 130 global sites by acquiring Howden, and joined the acquired company to its cloud backbone across Azure, AWS and Google Cloud while connecting different SD-WAN technologies without swapping hardware right away. |
| warner | Warner Hotels | yes | network_modernization, multi_cloud | Hospitality | Network changes that took days or weeks are now made in minutes, across 18 UK properties and its AWS and Azure environments. |
| canada-professional-services | A leading Canadian professional services organization | no | multi_cloud | Professional services | 3 public clouds (AWS, Azure and Google Cloud) unified on 1 networking platform, with 0 networking hires needed to support rapid growth. |
| fortune50-healthcare | A Fortune 50 healthcare company | no | multi_cloud, m_and_a, partner_connectivity | Healthcare | Runs primarily in Azure with cross-cloud communication among Azure, Google Cloud and Oracle Cloud, no longer depends on colocation facilities or legacy ExpressRoute circuits, integrates acquisitions that have overlapping networks, and connects business partners over IPsec, SD-WAN or private circuits. |
| software-firewalls | A large software company | no | firewall_consolidation | Software | Firewalls in the cloud reduced from 24 to 2. |
| finserv-egress | A global financial services company | no | multi_cloud | Financial services | Saved over $800,000 annually in cloud egress fees. |
| retail-colocation | A retail customer | no | multi_cloud | Retail | Avoided $3M in upfront costs per colocation hub while expanding its cloud presence. |
| airline-hub | A large airline | no | multi_cloud, network_modernization | Airline | A communications hub to the cloud that took 5 weeks and 4 people sent on site can now be brought up in 1 hour, remotely. |
| railroad-multicloud | A large railroad | no | multi_cloud, firewall_consolidation | Rail | After struggling for over a year in one cloud, a trial with Alkira brought up 2 regions, 3 clouds, highly available firewalls and SD-WAN in 2 days. |
| retailer-latam | A large retailer | no | multi_cloud, network_modernization | Retail | A regional hub in Brazil was brought up in 1 hour, connecting its 200 retail stores in Latin America to its cloud in the US. |
| clearing-house | A financial clearing house | no | partner_connectivity | Financial services | Partner connectivity for thousands of banks is automated through a self-service portal: a partner asks, the clearing house approves, and the partner connects itself. |
| food-distributor | A large food distributor | no | multi_cloud | Food distribution | With three cloud providers, can eliminate 4 of its 6 connections to the cloud. |
| michaels | Michaels | yes | site_rollout, network_modernization, multi_cloud | Retail | About 1,400 stores in the U.S. and Canada connected to Google Cloud in three weeks, ahead of peak season, with no new network infrastructure. |
| software-datacenter | A very large software company (Nemertes study) | no | multi_cloud, network_modernization | Software | 90% less network engineer time needed across its data centers and cloud regions, and a new data center stood up in a month. |
| nemertes-healthcare-provider | A large healthcare provider (Nemertes study) | no | multi_cloud, firewall_consolidation | Healthcare | 300% more cloud environments after expanding to a second cloud region, with fewer firewalls and firewall as a service in place of over-provisioning. |
| nemertes-investment-institution | A global investment institution (Nemertes study) | no | partner_connectivity, network_modernization | Financial services | 88% fewer VPN tunnels per partner, with core traffic moved off MPLS and the public internet onto the hyperscalers' backbones. |
| nemertes-medical-manufacturer | A large medical manufacturer (Nemertes study) | no | m_and_a, multi_cloud | Medical manufacturing | 99.8% decrease in time to merge in an acquired company's network, on one network service across its clouds and on-premises sites. |
| nemertes-financial-extranet | A financial services firm (Nemertes study) | no | partner_connectivity, m_and_a, multi_cloud | Financial services | 88% less staff time to add an extranet partner, with cloud networks and SD-WAN unified and acquired companies assimilated faster. |
| nemertes-software-services | A large software and services company (Nemertes study) | no | multi_cloud | Software | About 600 VPCs and VNets across AWS, Azure and Google Cloud, each with uncontrolled internet access, brought under consistent, controlled and monitored access. |
| nemertes-financial-telecoms | A financial telecoms company (Nemertes study) | no | m_and_a, firewall_consolidation | Financial telecoms | Connecting an acquired company's network went from 80 to 120 days to 3 days, with far fewer firewalls needed. |
| nemertes-manufacturer | A large manufacturer (Nemertes study) | no | m_and_a, multi_cloud | Manufacturing | After a massive acquisition, linked the new infrastructure to the old through Alkira in Azure and was in business in 2 weeks, not 2 years. |
| nemertes-financial-multicloud | A very large financial services company (Nemertes study) | no | multi_cloud, firewall_consolidation, m_and_a | Financial services | 200% more cloud environments across AWS, Azure and Google Cloud, with the firewalls it had in every cloud consolidated into Alkira and acquired companies' networks assimilated. |
| nemertes-software-acquirer | A large software company (Nemertes study) | no | firewall_consolidation, m_and_a | Software | 60% fewer firewalls for cloud, and one consistent way to bring in the several companies it acquires each year. |
| nemertes-telecom | A large telecommunications company (Nemertes study) | no | multi_cloud | Telecommunications | 200% more cloud regions connected, with more control over routing than the cloud's native networking gave. |
| nemertes-biotech | A small biotech company (Nemertes study) | no | network_modernization, multi_cloud | Biotech | 98% reduction in the number of WAN outages. Replaced colocation-based regional hubs with a cloud model across Azure and AWS. |
| healthcare-firewalls | One large healthcare enterprise | no | firewall_consolidation | Healthcare | Firewalls consolidated from 76 to 14. |

When no story's Situations include the angle's use case, use the ID `none` rather than stretching a story.

---

## Named Case Studies

### Michaels
- **Industry:** Retail. One of North America's largest arts and crafts retailers, with about 1,400 stores across the U.S. and Canada
- **Use case:** Store rollout at national scale, store-to-cloud connectivity into Google Cloud, moving off datacenter-centric networking
- **Situation:** Michaels was moving more workloads to Google Cloud while every store still backhauled through private datacenters. Earlier outages tied to proprietary datacenter equipment had disrupted operations and cost sales. The team needed all stores connected to Google Cloud ahead of peak holiday demand
- **What they did:** Deployed Alkira Cloud Exchange Points to connect Google Cloud with the stores. They validated the approach in a small number of stores, then rolled it out to the whole estate
- **Outcome:** About 1,400 stores connected in three weeks, with no new capital investment and no new network infrastructure. An individual store went from zero to full connectivity within hours. The rollout began as peak-season preparation
- **Who said so:** Wei Dong, Vice President and Chief Information Security Officer, and Sreenu Sampati, Director of Security Engineering, both at Michaels
- **Why Alkira:** Removing redundant backhaul to private datacenters was a primary objective, and the network had to be highly available through peak season
- **Source:** Futuriom Networking Leadership Brief, "Michaels' Three-Week Shift to Network Infrastructure as a Service", sponsored by Alkira. The customer is public and may be named

### Chart Industries
- **Industry:** Manufacturing. A global maker of highly engineered equipment for the clean energy and industrial gas markets
- **Use case:** M&A integration across Azure, AWS and Google Cloud
- **Situation:** Acquired UK-based Howden in March 2023 and grew from 40 to over 130 global sites. The 90 added sites came with different cloud architectures across Azure, AWS and Google Cloud and with different SD-WAN vendors. Chart has about 50 IT professionals globally
- **Outcome:** Joined the acquired company to its cloud backbone and connected the different SD-WAN technologies without swapping hardware right away. Separately, 60 VPN endpoints installed in 3 days against a traditional 3-6 months, for remote monitoring of cryogenic equipment
- **Who said so:** Susan Tlacil, Senior Network Architect, Chart Industries

### Warner Hotels
- **Industry:** Hospitality. A UK company operating 18 properties across the United Kingdom
- **Use case:** A cloud-based backbone and network modernization across AWS and Azure
- **Situation:** Aging on-premises systems, workloads moving to AWS and Azure, and network and security changes that took days or weeks through legacy suppliers
- **Outcome:** Network changes that previously took days or weeks can now be implemented in minutes. Direct cloud-to-cloud connectivity, and the network extended to third parties such as payment providers
- **Who said so:** Madoc Batters, Head of Cloud & IT Security, Warner Leisure Hotels

### Tekion
- **Industry:** Automotive technology
- **Use case:** Fast network provisioning for cloud and multi-cloud connectivity
- **Situation:** Unreliable connectivity to cloud, a small IT team struggling to support a growing network, limited cloud networking expertise, and a delayed international expansion
- **What they did:** A global multi-cloud network delivered as a service, with any on-premises router supported for IPsec cloud connectivity and firewalls integrated into the network
- **Outcome:** One standard network for all cloud and multi-cloud connectivity, greatly reduced IT time-to-service, international network expansion, a stronger security posture, and operational agility with limited staff

### Koch Industries
- **Industry:** One of America's largest privately held companies, with businesses from manufacturing to software. Growth by acquisition left it with seven global networks spanning 700 sites across 70 countries
- **Use case:** Multi-cloud networking, M&A integration, expansion to mainland China
- **Situation:** A separate transport hub for each business network, region and cloud provider, and M&A network integration that took months to years
- **Outcome:** Replaced ten transport hubs with two Alkira Cloud Exchange Points. Deployed Azure in a single day against 3-6 months with the legacy hubs. Connects new acquisitions to Koch infrastructure quickly. Alkira's customer one-pager adds an 83% reduction in time to deploy cloud environments (6 months to 1) and an 80% reduction in cloud networking infrastructure. Its one-page case study lists network expansion to mainland China and operational agility without a headcount increase
- **Who said so:** Troy Schneider, Global Infrastructure Platform Lead, and Matt Hoag, Chief Technology Officer
- **Notable:** Koch Disruptive Technologies is also an Alkira investor

### S&P Global
- **Industry:** Financial services
- **Use case:** Extranet as a service for partner connectivity, M&A integration, multi-cloud networking with segmentation
- **Situation:** Integrating mergers and acquisitions took a long time, point solutions had multiplied network complexity, and on-premises and cloud ran on different architectures
- **What they did:** A global multi-cloud network delivered as a service, firewalls and SD-WAN integrated into it, and network segmentation with selective resource sharing across segments
- **Outcome:** After its merger with IHS Markit, S&P Global estimated two and a half years to bring the networks together and did it with Alkira in two months. 80% reduction in deployment time for new cloud regions, and savings of $10M+ from circuits and hardware. Consistent security policy and enforcement points
- **Who said so:** Guruprasad Ramamoorthy, VP, Head of Global Network Services

---

## Other Anonymous Stories

Use an anonymous story's Customer label exactly as the table gives it. Never add a rank, a place or a partner's name to it, and never guess or hint at who the customer is.

- **`canada-professional-services`:** thousands of employees, cloud-first, with a lean networking team. One security and segmentation policy across every environment.
- **`railroad-multicloud`:** remote access for 30,000 users is planned on the same platform.

---

## Nemertes Case Studies

Twelve anonymous case studies from the Nemertes "Alkira Real Economic Value Report" (October 2024), for which Nemertes interviewed thirteen Alkira customers. Every figure here belongs to the one customer it is listed under. The study's averages across customers are under Key Stats.

- **`software-datacenter`, very large software company:** needed a new data center to exit a country when shipped hardware had a lead time of a year or two. Built it in colocation with Alkira carrying routing, DNS, DHCP and firewall. 90% fewer FTEs to manage cloud networks, 92% faster to onboard a new partner, 94% faster to connect new data centers.
- **`nemertes-healthcare-provider`, large healthcare provider:** scores of apps across hundreds of cloud environments in one cloud region. 50% fewer firewalls, four new hires avoided, and defined-trust extranet connections with partners for the first time.
- **`nemertes-investment-institution`, global investment institution:** a cloud-first shift. Closed some data centers and reduced telco spend.
- **`nemertes-medical-manufacturer`, large medical manufacturer:** replaced a multicloud networking product that was complex and expensive. Places apps in nearby cloud regions for latency and data sovereignty.
- **`nemertes-financial-extranet`, financial services firm:** 67% less calendar time to add an extranet partner. Three planned hires avoided. A partner or an acquired company connects without the networks being merged until its security is understood.
- **`nemertes-software-services`, large software and services company:** cleaning up after ten years of uncontrolled moves to cloud. 6 new hires avoided.
- **`nemertes-financial-telecoms`, financial telecoms company:** 94% fewer firewalls. Went from 0 cloud environments to 100 across seven regions. Eight planned hires avoided.
- **`nemertes-manufacturer`, large manufacturer:** 1650% more cloud apps. Private connectivity to a new customer in about one-fiftieth of the time.
- **`nemertes-financial-multicloud`, very large financial services company:** cloud platforms up 100%, regions up 50%. Staff time and calendar time to connect one cloud to another down 50%.
- **`nemertes-software-acquirer`, large software company:** 65% fewer routers for cloud.
- **`nemertes-telecom`, large telecommunications company:** a voice and text services company. Time to hook up a new environment cut in half.
- **`nemertes-biotech`, small biotech company:** wanted direct access to its clouds from every site and a simpler extranet, without adding network engineers.

`healthcare-firewalls` (76 firewalls to 14) is one large healthcare enterprise. It is not part of the Nemertes study and is not the study's healthcare provider.

---

## Customers by Use Case

How customers map to Alkira's five entry points:

**Hybrid / Multi-Cloud Networking:** The most common entry point: enterprises migrating to cloud or connecting multiple clouds.

**Security & Services Consolidation:** Healthcare and financial services enterprises consolidating firewalls. One large healthcare enterprise went from 76 firewalls to 14.

**Backbone-as-a-Service:** Companies replacing expensive MPLS circuits. Alkira's partner TCO guide puts the typical cut in WAN connectivity costs at 40-60%.

**Extranet / Business Partner Connectivity:** Companies with M&A activity or large partner ecosystems.

**ZTNA:** Distributed workforce companies implementing zero trust. Pay-per-use model with auto-scaling.

---

## Key Stats Quick Reference

What the Nemertes study measured across the customers it interviewed. An average is never one customer's result:

- 96% less calendar time to add a cloud environment (study average)
- 73% fewer firewalls for cloud (study average, among the customers that cut firewalls)
- 44% fewer network and security devices for cloud connectivity (study average)
- 47% less staff time to manage cloud networks (study average)
- 98% less staff time and 91% less calendar time to add an extranet partner (study averages)

Alkira's own figures, not from the study:

- 40-60% lower TCO
- 80% less provisioning time
