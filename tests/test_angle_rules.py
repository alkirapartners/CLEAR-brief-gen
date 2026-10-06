"""What an evidence line, an angle or a plant-network line must be to stay in a brief."""

import pytest

import angle_rules


def _line(text, dated="2026-01-03"):
    return {"text": text, "date": dated, "sources": [1]}


def _angle(*lines, use_case="m_and_a"):
    return {
        "title": "Angle", "use_case": use_case, "evidence": list(lines), "alkira": "What Alkira does.",
        "story": {"id": "none", "customer": "", "result": ""},
        "deal_date": "", "deal_status": "none", "deal_pending_quote": "",
    }


FIRST_HAND = frozenset({1})  # every line in these tests cites source 1


def _stands(angle, first_hand=FIRST_HAND):
    return angle_rules.stands(angle, first_hand)


def _why_not(angle, first_hand=FIRST_HAND):
    return angle_rules.why_not(angle, first_hand)


# ── Lines that are never evidence ────────────────────────────────

@pytest.mark.parametrize("text", [
    "The 10-K cites an aging technological infrastructure risk.",
    "The 10-K includes transition services risk language tied to the divestiture.",
    "The FY2025 10-K names integrating the technology and networks of Worldpay as a risk.",
    "Integration is listed among the risk factors.",
    "El informe anual menciona la integración como un riesgo.",
], ids=["aging-infrastructure", "transition-services", "named-as-a-risk", "risk-factors", "spanish"])
def test_what_a_filing_lists_as_a_risk_is_not_evidence(text):
    assert angle_rules.kept_lines([_line(text)]) == []


@pytest.mark.parametrize("text", [
    "The 10-K reports 10,412 continuing employees excluding OxyChem, so the divested business is now outside the headcount.",
    "The company has about 28,274 full-time team members.",
    "Headcount grew 12% over the year.",
    "The careers site lists 340 open positions.",
    "There are 57 job postings in IT.",
    "La empresa tiene 6,304 empleados.",
], ids=["employees", "team-members", "headcount", "open-positions", "postings-count", "spanish"])
def test_headcount_and_hiring_statistics_are_not_evidence(text):
    assert angle_rules.kept_lines([_line(text)]) == []


@pytest.mark.parametrize("text", [
    "A network engineer posting lists ExpressRoute and a Virtual WAN hub-and-spoke.",
    "Advance closed 522 stores and opened 39 in fiscal 2025.",
    "Global Payments completed the Worldpay acquisition on January 9.",
    "The posting asks for a brisk pace and a risky amount of travel.",
    "The network team of 12 engineers runs SD-WAN at 5 refineries.",
    "The Senior Network Engineer posting was published in September.",
])
def test_ordinary_evidence_is_left_alone(text):
    assert angle_rules.kept_lines([_line(text)]) == [_line(text)]


# ── An angle needs a specific, dated fact ────────────────────────

def test_an_angle_with_a_first_hand_fact_stands_whether_or_not_the_fact_is_dated():
    """An undated case study from a cloud vendor is real evidence. The score, not the angle, pays for the missing date."""
    assert _stands(_angle(_line("The deal closed.", "2026-01-09"), _line("An undated note.", ""), use_case="multi_cloud"))
    assert _stands(_angle(_line("Core systems run in AWS China and AWS Oregon.", ""), use_case="china_global"))


def test_an_angle_with_no_first_hand_fact_does_not_stand_however_well_dated():
    """Trade press or a data broker alone does not make an angle."""
    dated = _angle(_line("Trade press reports an SD-WAN rollout.", "2026-09-01"), use_case="multi_cloud")
    assert not _stands(dated, first_hand=frozenset())
    assert _why_not(dated, first_hand=frozenset()) == "no line rests on a first-hand source"


def test_which_sources_can_carry_an_angle_is_one_constant():
    assert angle_rules.SECOND_HAND_ALONE_MAKES_AN_ANGLE is False


# ── An M&A angle names what has to be connected or separated ─────

@pytest.mark.parametrize("text", [
    "HF Sinclair completed its acquisition of Industrial Oils Unlimited, LLC for $38 million.",
    "UPS completed the $1.6B acquisition of Andlauer Healthcare Group.",
    "The company announced an agreement to merge with a competitor.",
    "Management expects cost savings from the integration.",
], ids=["price-only", "closed-only", "announced-only", "savings"])
def test_a_deal_with_a_price_and_a_date_and_nothing_to_connect_is_not_an_angle(text):
    assert not _stands(_angle(_line(text)))


@pytest.mark.parametrize("text", [
    "The separation creates a new independent, publicly traded company operating in the U.S., Canada and the Netherlands.",
    "The acquired business runs blending plants in Tulsa and Houston.",
    "Occidental provides transition services to OxyChem under a Transition Services Agreement.",
    "The deal adds 31 temperature-controlled facilities in Canada.",
    "It acquired the assets of a New York City distribution operation.",
    "Employees and 140 storefronts transferred to the buyer.",
    "The 10-K says the technology and networks of the acquired company are being integrated.",
    "La adquisición suma 12 plantas y sus sistemas.",
], ids=["new-entity", "plants", "tsa", "facilities", "operation", "storefronts", "systems", "spanish"])
def test_a_deal_that_names_sites_systems_or_entities_can_be_an_angle(text):
    assert _stands(_angle(_line(text)))


def test_one_line_that_names_what_is_connected_carries_the_other_lines_of_the_angle():
    angle = _angle(
        _line("It completed the acquisition for $38 million."),
        _line("The acquired business runs two blending plants in Oklahoma.", ""),
    )
    assert _stands(angle)


def test_an_angle_with_no_evidence_left_does_not_stand():
    assert not _stands(_angle(use_case="multi_cloud"))


# ── "Network" has to mean the IT network ─────────────────────────

UPS = [
    "UPS closed 23 leased and owned buildings in Q1 and identified 27 more for closure under Network Reconfiguration and Efficiency Reimagined.",
    "The program expands Network of the Future with automation and sort consolidation, and leads to fewer facilities, vehicles and aircraft.",
    "The proxy says the company strategy centres on network optimization.",
]


def test_a_delivery_network_being_reorganised_is_not_network_modernization():
    angle = _angle(*[_line(text) for text in UPS], use_case="network_modernization")
    assert not _stands(angle)


def test_the_same_facts_can_stand_as_sites_closing_at_scale():
    assert _stands(_angle(*[_line(text) for text in UPS], use_case="site_rollout"))


@pytest.mark.parametrize("text", [
    "The posting covers network strategy across retail and data center, including SD-WAN and cloud connectivity.",
    "The company is exiting MPLS by the end of the year.",
    "A data-center exit is planned for two sites.",
    "The role leads enterprise network security architecture programs.",
    "A Senior Network Engineer posting asks for BGP and Palo Alto firewalls.",
    "La empresa migra su red corporativa a SD-WAN.",
])
def test_a_line_that_names_network_technology_carries_a_network_modernization_angle(text):
    assert _stands(_angle(_line(text), use_case="network_modernization"))


@pytest.mark.parametrize("text", [
    "Management defined a target architecture to consolidate platforms and reduce infrastructure complexity.",
    "The company offers guided migration paths to cloud-based solutions.",
    "The store network grew by 40 locations.",
    "The distribution network is being consolidated into market hubs.",
])
def test_a_line_about_platforms_or_a_business_footprint_does_not(text):
    assert not _stands(_angle(_line(text), use_case="network_modernization"))


# ── Plant networks are industrial control systems ────────────────

@pytest.mark.parametrize("text", [
    "RFID sensing network under Smart Package Smart Facilities, with readers across U.S. package cars.",
    "Handheld scanners and store Wi-Fi at 4,305 stores.",
    "19 DCs and 33 market hubs.",
    "Telematics in delivery vehicles.",
])
def test_scanners_readers_and_shop_wifi_are_not_a_plant_network(text):
    assert not angle_rules.is_plant_network(text)


@pytest.mark.parametrize("text", [
    "Plant networks at five refineries.",
    "OT network segmented from IT at each refinery, Purdue model.",
    "SCADA and PLCs across pipeline operations.",
    "IT/OT separation led by the security team.",
    "Industrial control systems at 12 plants.",
    "Redes de planta con sistemas de control en tres refinerías.",
])
def test_industrial_control_systems_are(text):
    assert angle_rules.is_plant_network(text)


# ── Saying why ───────────────────────────────────────────────────

def test_an_angle_that_does_not_stand_says_why_for_the_log():
    assert _why_not(_angle(use_case="multi_cloud")) == "no evidence line is left"
    assert _why_not(_angle(_line("A posting lists SD-WAN.", ""), use_case="multi_cloud")) == ""
    assert "network technology" in _why_not(_angle(_line("The store network grew."), use_case="network_modernization"))
    assert "connected or separated" in _why_not(_angle(_line("It bought a rival for $38 million.")))
    assert _why_not(_angle(_line("The acquired business runs two plants."))) == ""
