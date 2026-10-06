"""Find the technology terms in a line of the technical snapshot.

The PDF sets them in mono, as the brief page does, so an engineer's eye
lands on the products, vendors and protocols. A reading aid only: the list
is a best guess kept here (the page keeps the same one in tech-terms.ts),
and a term it misses is simply left as plain text.
"""

import re

Token = tuple[str, bool]

# Products, vendors and protocols, as they are normally written.
KNOWN_TERMS: tuple[str, ...] = (
    # Clouds
    "Amazon Web Services", "AWS", "Microsoft Azure", "Azure", "Google Cloud Platform", "Google Cloud", "GCP",
    "Oracle Cloud", "OCI", "Alibaba Cloud", "IBM Cloud",
    # Cloud networking
    "AWS Direct Connect", "Direct Connect", "ExpressRoute", "Azure Virtual WAN", "Virtual WAN", "vWAN",
    "Transit Gateway", "Cloud Interconnect", "PrivateLink", "Private Link", "Cloud WAN", "VNet", "VPC",
    # Network and security designs
    "SD-WAN", "MPLS", "BGP", "OSPF", "VPN", "IPsec", "SASE", "SSE", "ZTNA", "Zero Trust", "NGFW", "WAF",
    "SCADA", "5G",
    # Vendors and products
    "Palo Alto Networks", "Palo Alto", "Prisma Access", "Panorama", "Fortinet", "FortiGate", "Check Point",
    "Cisco", "Meraki", "Viptela", "Juniper", "Aruba", "Arista", "Zscaler", "Netskope", "Cloudflare", "Akamai",
    "Infoblox", "VeloCloud", "Silver Peak", "Aviatrix", "Equinix", "Megaport", "Honeywell Experion", "Foxboro",
    "Siemens", "Rockwell",
    # Automation and platforms
    "Terraform", "Ansible", "Python", "CloudFormation", "Kubernetes", "Databricks", "Azure Functions",
    "Azure DevOps", "Snowflake",
)
# Capitals that are not technology: places, titles, filings.
EVERYDAY_CAPITALS: frozenset[str] = frozenset({
    "US", "USA", "UK", "EU", "UAE", "IT", "HQ", "HR", "FY", "CEO", "CIO", "CTO", "CFO", "COO", "CISO", "VP",
    "SVP", "EVP", "LLC", "INC", "NYSE", "SEC", "IRS", "Q1", "Q2", "Q3", "Q4", "H1", "H2",
})

_ACRONYM = "[A-Z][A-Z0-9]{1,5}"
# Longest first, so "Azure Virtual WAN" is one term and not "Azure" followed by "WAN".
_KNOWN = "|".join(re.escape(term) for term in sorted(KNOWN_TERMS, key=len, reverse=True))
# A term starts at the beginning or after a character that is not part of a
# word, and ends before one. Acronyms joined by slashes are tried first, so
# they stay together: "SSE/SASE".
_TERM = re.compile(rf"(^|[^A-Za-z0-9])({_ACRONYM}(?:/{_ACRONYM})+|{_KNOWN}|{_ACRONYM})(?![A-Za-z0-9])")


def _is_everyday(candidate: str) -> bool:
    return all(part in EVERYDAY_CAPITALS for part in candidate.split("/"))


def tokenize(text: str) -> list[Token]:
    """The text as a run of plain words and technology terms, in order, nothing dropped."""
    tokens: list[Token] = []
    end = 0
    for match in _TERM.finditer(text):
        candidate = match.group(2)
        if _is_everyday(candidate):
            continue
        start = match.start(2)
        if start > end:
            tokens.append((text[end:start], False))
        tokens.append((candidate, True))
        end = match.end(2)
    if end < len(text):
        tokens.append((text[end:], False))
    return tokens
