# Knowledge base sources

Where each customer story and headline number in `skills/alkira-customer/` comes from. The skill files are inlined into a cached prompt, so they carry no provenance themselves: it is kept here.

One line per story ID: the source document's title, publisher and date, then each figure with the page it is on. A page is the PDF page, counting the cover as 1.

## Rules for a story

- Find the number or the quote on the page before writing it. A figure that cannot be found in its source is left out.
- Exact numbers and units, as written. Figures from different customers are never combined, and an average across customers is never attached to one customer.
- No deal sizes, prices, discounts or contract terms.
- A customer is named only when published material names it. Every other customer is described the way the source's own anonymised version describes it.
- The Result column of the Story Matching Table holds a story's single strongest figure. Its other figures stay in the prose under the table.

## Named customers

- `michaels` — "Michaels' Three-Week Shift to Network Infrastructure as a Service", Futuriom Networking Leadership Brief sponsored by Alkira, undated. About 1,400 stores across the U.S. and Canada in three weeks, pp. 1 and 3; no new capex and no new network infrastructure, pp. 1 and 3; an individual store connected within hours, p. 3; the titles of the two people quoted, p. 3.

## Anonymous stories

Customers that no published source names, labelled as their source labels them.

## Nemertes study

"Alkira Real Economic Value Report" by John Burke, Nemertes, October 2024 (DN11954): interviews with thirteen Alkira customers, written up as twelve anonymous case studies. Alkira published each case study as a one-page PDF of its own.

"Report" below is that report. "One-pager" is Alkira's one-page case study of the same customer, 2025; each is a single page, and three also exist in a 2024 edition with the same figures. A row's result uses the report's figure where the report prints one.

- `software-datacenter` — Report §10.2, Nemertes, October 2024, p. 13: 90% less network engineer time needed; infrastructure stood up in a month; a year or two of lead time on shipped hardware. One-pager "Very Large Software Company: Needed a New Data Center Up Fast", Alkira, 2025: 90% fewer FTEs, 92% faster to onboard a new partner, 94% faster to connect new data centers.
- `nemertes-healthcare-provider` — Report §10.3, Nemertes, October 2024, p. 14: 300% increase in number of cloud environments; expansion to a second region; four new hires avoided; firewall as a service; first defined-trust extranet connections. One-pager "Large Healthcare Provider: Manage Inter-region Connectivity and Simplify Multicloud Deployment", Alkira, 2025: 50% fewer firewalls needed.
- `nemertes-investment-institution` — Report §10.4, Nemertes, October 2024, p. 15: 88% fewer VPN tunnels per partner; core traffic off MPLS and the public internet; data centers closed and telco spend reduced.
- `nemertes-medical-manufacturer` — Report §10.5, Nemertes, October 2024, p. 16: 99.8% decrease in time to merge in an acquired company's network.
- `nemertes-financial-extranet` — Report §10.6, Nemertes, October 2024, p. 17: 88% reduction in time to add a new extranet partner; two-thirds off the calendar time; three new hires avoided. One-pager "Financial Services Firm Unifies Cloud Networks and SD-WAN, Becomes Even More Agile", Alkira, 2025: the 88% is staff time, and calendar time is 67% less.
- `nemertes-software-services` — Report §10.7, Nemertes, October 2024, p. 18: on the order of 600 VPCs and VNets across AWS, Azure and Google; 6 new hires avoided. Controlled and monitored access afterwards, p. 8.
- `nemertes-financial-telecoms` — Report §10.8, Nemertes, October 2024, p. 19: 80 to 120 days down to three days for an acquired company's network; 0 cloud environments before and 100 across seven regions after; eight new hires avoided. One-pager "Financial Telecoms Company Makes the Move to Cloud with Alkira", Alkira, 2025: 94% fewer firewalls needed.
- `nemertes-manufacturer` — Report §10.9, Nemertes, October 2024, p. 20: "in 2 weeks, not 2 years" after a massive acquisition; 1650% more cloud apps; about one-fiftieth of the time to connect a new customer.
- `nemertes-financial-multicloud` — Report §10.10, Nemertes, October 2024, p. 21: cloud platforms up 100%, regions up 50%, cloud environments up 200%; firewalls in every cloud consolidated; staff time and calendar time for cloud-to-cloud connections down 50%.
- `nemertes-software-acquirer` — Report §10.11, Nemertes, October 2024, p. 22: 65% fewer routers for cloud, 60% fewer firewalls for cloud; several acquisitions a year. (The one-pager's summary box prints "5% fewer routers", a misprint: its own figure tile says 65%.)
- `nemertes-telecom` — Report §10.12, Nemertes, October 2024, p. 23: 200% more cloud regions connected; time to hook up a new environment cut in half.
- `nemertes-biotech` — Report §10.13, Nemertes, October 2024, p. 24: 98% reduction in number of WAN outages; colocation-based regional hubs replaced; Azure and AWS. The report calls the company small; the one-pager's title says mid-sized.

### Not a Nemertes case

- `healthcare-firewalls` — 76 firewalls to 14 at one large healthcare enterprise. Its only source is internal Alkira material that was not opened for this list; it is carried at the owner's direction. It is not the study's healthcare provider, whose own figure is 50% fewer firewalls.

### Retired IDs

`nemertes-1` to `nemertes-12` summarised the study wrongly and are retired (`case_studies.RETIRED_IDS`): the table refuses them. A brief stored with one of them keeps the customer label and result it was written with, because a stored brief carries both and nothing looks the ID up again. `software-datacenter` and `nemertes-1` were the same case; it keeps `software-datacenter`.

## Headline numbers

The Proof Points table in `skills/alkira-customer/SKILL.md` and the key stats in `skills/alkira-customer/references/case-studies.md`.

Averages across the customers in the Nemertes study (Report, Nemertes, October 2024):

- 96% less calendar time to add a cloud environment — p. 3 (executive summary) and p. 6: about 26 business days to less than 1.
- 73% fewer firewalls for cloud — p. 3 and p. 7: the average among the 75% of participants whose firewall count fell, from roughly 21 to 6.
- 44% fewer network and security devices for cloud connectivity — p. 3. The body, p. 7, gives 43%: about 23 devices to about 13.
- 47% less staff time to manage cloud networks — p. 3 and p. 6 (47% fewer FTEs on average).
- 98% less staff time to add an extranet partner — p. 3 and p. 9: nearly 260 staff hours to less than five, among the two-thirds who saw a decrease.
- 91% less calendar time to add an extranet partner — p. 3 and p. 9: more than 91 business days to 8.

Alkira's own figures:

- 80% provisioning time reduction — "Network & Security for the Era of Cloud and AI" customer one-pager, Alkira, undated, p. 1.
- 40-60% lower TCO — "Alkira Partners Guide: Lower TCO with Alkira (40-60%)", Alkira, 2025, p. 1: the title, and "40-60% reduction in WAN connectivity costs" where MPLS is replaced. "Alkira Network Infrastructure as-a-Service - Sales Battle Card", Alkira, undated, p. 1, and the customer one-pager say 40%.

### Removed, and why

- Network availability "99-99.9%", "99%+", "99.9% availability" and "zero unplanned outages": no source gives a measured availability. The TCO guide states a 99.9% uptime SLA for the backbone, which is a service commitment, not a result, and is not carried.
- "Up to 82%" fewer firewalls: no source. It appears to be the 76-to-14 example restated as a percentage.
- "Network hubs reduced by 60-88%" and "88% less operational time for network changes": no source.
- "67-90% reduction in network engineering time": no source gives the range. Its two ends match two different customers' figures.
- "Up to 1650%" as a headline: one manufacturer's figure. It now sits with that customer.
- "40-60% TCO, validated by Nemertes": the study did not measure TCO. The figure is Alkira's own.
- "40% lower cost than MPLS, deployed 80% faster": no source says this of MPLS. The TCO guide's own sentence is used instead.
- "Includes Fortune 500 companies across industries": no source reviewed says it.
