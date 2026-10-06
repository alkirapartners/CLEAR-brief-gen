# Alkira Pricing Reference

## Pricing Components

Alkira pricing is built on four metered components:

### 1. Cloud Exchange Points (CXPs)
Priced by **size and quantity**. CXP size determines throughput capacity:

| Size | Throughput |
|------|-----------|
| Small (S) | 100 Mbps |
| Medium (M) | 500 Mbps |
| Large (L) | 1 Gbps |
| 2Large (2L) | 2 Gbps |
| 5Large (5L) | 5 Gbps |
| 10Large (10L) | 10 Gbps |
| 20Large (20L) | 20 Gbps |

### 2. Connectors
On-prem and cloud connector sizing. Connectors link customer environments (branches, data centers, cloud VPCs/VNETs) to the CXP fabric.

### 3. Services
Third-party network and security services deployed from the Alkira marketplace. Two licensing models:
- **BYOL (Bring Your Own License):** Customer uses existing licenses for services like Palo Alto, Fortinet, etc.
- **PAYG (Pay As You Go):** Alkira provides the service license on a consumption basis

### 4. Data Charge
Per-GB charge for data leaving the CXP fabric (egress).

---

## Business Models

Alkira offers multiple consumption and subscription models to match how customers want to buy:

### Enterprise License Agreement (ELA)
Traditional enterprise agreement with committed spend. Good for large enterprises with predictable network needs.

### Consumption Models

**Fixed Infrastructure:** Pre-provisioned CXP capacity at a set monthly rate. Predictable billing.

**PAYG (Pay As You Go):** True cloud consumption model. Pay only for what you use. No upfront commitment. Good for getting started or variable workloads.

**Commit Consumption:** Commit to a minimum spend level in exchange for better rates. Balances flexibility with cost optimization.

### Subscription Models
Subscription-based pricing for predictable monthly/annual costs.

---

## Key Positioning Points for Pricing Conversations

- **Zero CAPEX:** No hardware to buy, no software to download. SaaS-like consumption.
- **40-60% lower TCO** vs. traditional networking approaches. This is Alkira's own figure, from its partner TCO guide: the Nemertes study measured staff time, calendar time and device counts, not TCO
- **Cloud-aligned consumption:** Networking finally matches how enterprises consume compute and storage
- **Flexibility:** Start with PAYG, move to committed consumption as usage stabilizes
- **No hidden costs:** No circuits to procure, no colo cages to rent, no hardware lifecycle management

## Important Notes
- Specific per-unit pricing is not included in this reference. Consult current rate cards or work with Alkira sales operations for deal-specific pricing.
- Support tiers are available but pricing details should come from current Alkira documentation.
