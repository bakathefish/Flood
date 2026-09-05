"""Single authority for every physical constant, threshold and travel time.

Rules of this module:

* Every value carries its ``source``: the document, page or file it was read from, or the
  computation that produced it. Nothing here is a remembered number.
* Nothing else in the package may re-declare a value that lives here; import it by name.
* Values quoted from the Punjab Water Resources Department (WRD) *Flood Preparedness
  Guidebook 2026* were read from the text layer of the PDF and then checked against the
  rendered page (see ``data/reference/wrd/VERIFICATION.md``). Printed inconsistencies in
  the guidebook are kept as printed and flagged in ``note``, never silently corrected.

Abbreviations: FRL full reservoir level, MWL maximum water level, BCM 10^9 m3,
MCM 10^6 m3, cusec ft3/s, cumec m3/s.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------------------
# exact unit conversions
# --------------------------------------------------------------------------------------
FOOT_M = 0.3048  # exact by definition (international foot)
CUSEC_M3_PER_S = FOOT_M**3  # 0.028316846592 m3/s per ft3/s, exact
SECONDS_PER_DAY = 86_400
CUSEC_DAY_M3 = CUSEC_M3_PER_S * SECONDS_PER_DAY  # 2446.5755... m3 per cusec-day
CUSEC_DAY_BCM = CUSEC_DAY_M3 * 1e-9  # BCM per cusec-day
LAKH = 100_000
MCM_TO_BCM = 1e-3


def cusecs_to_m3s(cusecs: float) -> float:
    return cusecs * CUSEC_M3_PER_S


def m3s_to_cusecs(m3s: float) -> float:
    return m3s / CUSEC_M3_PER_S


def cusec_days_to_bcm(cusec_days: float) -> float:
    return cusec_days * CUSEC_DAY_BCM


def bcm_to_cusec_days(bcm: float) -> float:
    return bcm / CUSEC_DAY_BCM


def feet_to_m(ft: float) -> float:
    return ft * FOOT_M


def m_to_feet(m: float) -> float:
    return m / FOOT_M


# --------------------------------------------------------------------------------------
# sources, named once
# --------------------------------------------------------------------------------------
SRC_WRD_GUIDEBOOK = (
    "Punjab WRD, Flood Preparedness Guidebook 2026 (PDF captured 2026-08-10, sha1 6bf23d33)"
)
SRC_BBMB_BULLETIN = (
    "BBMB reservoir bulletin res_data.pdf header, captured 2026-08-09 to 2026-09-04 "
    "(data/reference/bbmb/bulletins_2026.jsonl)"
)
SRC_PONG_EAP = (
    "BBMB, Emergency Action Plan / Disaster Management Plan, Pong Dam (amended), "
    "bbmb.gov.in GeneralDocument/492_1_Pong_Dam_EAP_Amended.pdf, Annexure II salient "
    "features, pp. 56-60 (fetched 2026-09-05, sha256 186f374a4a8339f2...)"
)
SRC_BBMB_GLANCE = (
    "BBMB at a Glance, bbmb.gov.in Images/pdf/BBMB_glance.pdf (fetched 2026-09-05, "
    "sha256 60d2a319c48c3498...)"
)
SRC_BHAKRA_ESDD = (
    "BBMB, Environment and Social Due Diligence Report, Bhakra Dam (DRIP-II), "
    "bbmb.gov.in Images/pdf/ESDD_Report_Bhakra_Dam.pdf, salient features pp. 3-4 "
    "(fetched 2026-09-05, sha256 0d71d9dfcc38c9ea...)"
)
SRC_BHAKRA_DRIP_PST = (
    "BBMB, Project Screening Template for Nangal Dam under DRIP, February 2020, "
    "bbmb.gov.in images/drip/bbmb_pst_nangal_dam_18022020.pdf (fetched 2026-09-05, "
    "sha256 dd07654e589ca6a1...)"
)
SRC_BBMB_CBIP_DSS = (
    "BBMB presentation 'Real Time Decision Support System of BBMB' hosted by CBIP, "
    "cbip.org/DCSM/Data/Mr. Anil.pdf (fetched 2026-09-05, sha256 3c9c8555de3a069f...)"
)
SRC_CWC_FEED = (
    "CWC daily reservoir feed on data.gov.in, resource 1fc2148c-fc41-46f5-a364-bdc03f77053f, "
    "fields Full_reservoir_level and Live_capacity_FRL"
)
SRC_WIKIPEDIA_INFOBOX = "Wikipedia infobox (secondary source; used only where no primary was found)"
SRC_PUNJAB_WRD_DAMS = (
    "Punjab Department of Water Resources, Dams Administration page, "
    "wrd.punjab.gov.in/en/page/damsadministration, Ranjit Sagar salient features "
    "(fetched 2026-09-05)"
)
SRC_PSPCL_MHP = (
    "PSPCL, Mukerian Hydel Project Stage-I page, pspcl.in/Otherlinks/mukerian-hydel-project-"
    "stage-i.aspx (page dated 04-09-2026, fetched 2026-09-05)"
)
SRC_HYDROBASINS = (
    "HydroBASINS v1c Asia level 8 (Lehner & Grill 2013), hybas_as_lev08_v1c.zip, "
    "sha256 878c56bb4253a7c8...; upstream set of the sub-basin containing the dam"
)


# --------------------------------------------------------------------------------------
# dams
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Sourced:
    value: float
    source: str
    note: str = ""


@dataclass(frozen=True)
class Dam:
    name: str
    river: str
    lat: float
    lon: float
    coord_source: str
    cwc_name: str
    frl_ft: Sourced
    frl_m: Sourced
    mwl_ft: Sourced | None
    min_level_ft: Sourced | None
    live_capacity_bcm: Sourced
    gross_capacity_bcm: Sourced | None
    catchment_km2_published: Sourced | None
    hydrobasins_outlet: int
    spillway_capacity_cusecs: Sourced | None
    turbine_capacity_cusecs: Sourced | None
    max_observed_inflow_cusecs: Sourced | None = None
    extra: dict = field(default_factory=dict)


# Bhakra's non-spill passing capacity is not printed anywhere we found. The DRIP screening
# template gives the total that spillway, river outlets and both power houses can pass
# (about 3,25,000 cusecs) and the ESDD gives the spillway-plus-outlets design discharge
# (8,212 cumec). Their difference is the power-house passage, computed here, never typed.
_BHAKRA_TOTAL_PASSAGE_CUSECS = 325_000.0
_BHAKRA_SPILLWAY_PLUS_OUTLETS_CUMEC = 8_212.0
_BHAKRA_TURBINE_CUSECS = _BHAKRA_TOTAL_PASSAGE_CUSECS - m3s_to_cusecs(
    _BHAKRA_SPILLWAY_PLUS_OUTLETS_CUMEC
)

BHAKRA = Dam(
    name="Bhakra",
    river="Sutlej",
    lat=31.41111,
    lon=76.43611,
    coord_source=SRC_BHAKRA_ESDD + "; Lat/Long 31° 24' 40'' / 76° 26' 10''",
    cwc_name="Gobind Sagar-Bhakra Reservoir",
    frl_ft=Sourced(1680.0, SRC_BBMB_BULLETIN + "; also " + SRC_WRD_GUIDEBOOK + " Annexure Z"),
    frl_m=Sourced(512.06, SRC_CWC_FEED, "1680 ft x 0.3048 = 512.064 m"),
    mwl_ft=Sourced(
        1690.0,
        SRC_BBMB_BULLETIN,
        "top of dam 1700 ft in the same header; the ESDD prints MWL 515.24 m (1690.4 ft)",
    ),
    min_level_ft=Sourced(1462.0, SRC_WRD_GUIDEBOOK + " Annexure Z (Bhakra minimum level)"),
    live_capacity_bcm=Sourced(
        6.229,
        SRC_CWC_FEED,
        "live capacity at the FRL of 1680 ft as carried by CWC; BBMB prints the design live "
        "storage as 7,197 MCM (ESDD) and 7,191 MCM (BBMB at a Glance)",
    ),
    gross_capacity_bcm=Sourced(9.621, SRC_BHAKRA_ESDD + "; " + SRC_BBMB_GLANCE, "9621 MCM"),
    catchment_km2_published=Sourced(
        56_875.0,
        SRC_BHAKRA_ESDD,
        "'Catchment Area at Dam site 56,875 sq km'; the BBMB RTDSS presentation and Wikipedia "
        "print 56,980 km2, of which 20,000 km2 lies in India",
    ),
    hydrobasins_outlet=4080726490,
    spillway_capacity_cusecs=Sourced(
        m3s_to_cusecs(5_589.0),
        SRC_BHAKRA_ESDD,
        "4 radial-gated bays 15.24 x 14.50 m, total discharging capacity at MWL 5589 cumec; "
        "BBMB's presentation rounds this to 197,300 cusecs",
    ),
    turbine_capacity_cusecs=Sourced(
        _BHAKRA_TURBINE_CUSECS,
        SRC_BHAKRA_DRIP_PST
        + " (total about 3,25,000 cusecs) minus "
        + SRC_BHAKRA_ESDD
        + " (spillway and river outlets 8212 cumec)",
        "derived; ten penstocks feed 5 + 5 units of 1,379 MW installed (ESDD)",
    ),
    max_observed_inflow_cusecs=Sourced(
        m3s_to_cusecs(17_234.0), SRC_BHAKRA_ESDD, "17234 cumec on 06/08/1971"
    ),
    extra={
        "river_outlets_cusecs": Sourced(
            m3s_to_cusecs(8 * 187.97 + 8 * 160.10),
            SRC_BHAKRA_ESDD,
            "16 sluices at 402.33 m and 432.80 m, 187.97 and 160.10 cumec each at FRL",
        ),
        "original_design_flood_cusecs": Sourced(
            m3s_to_cusecs(11_331.44), SRC_BHAKRA_ESDD, "11331.44 cumec"
        ),
        "revised_design_flood_cusecs": Sourced(
            m3s_to_cusecs(22_487.0), SRC_BHAKRA_ESDD, "22487 cumec PMF, CWC report 2000/2014"
        ),
        "nangal_hydel_channel_cusecs": Sourced(
            12_500.0, SRC_BHAKRA_DRIP_PST + "; " + SRC_BBMB_GLANCE, "353.96 cumec full supply"
        ),
        "anandpur_sahib_hydel_channel_cusecs": Sourced(
            10_150.0, SRC_BHAKRA_DRIP_PST, "287.42 cumec full supply, off-takes above Nangal dam"
        ),
        "beas_sutlej_link_pandoh_baggi_cusecs": Sourced(
            9_000.0,
            SRC_BBMB_GLANCE,
            "Pandoh-Baggi tunnel capacity (9005 cusecs in the RTDSS presentation); Beas water "
            "diverted into the Sutlej above Bhakra",
        ),
        "sundernagar_sutlej_tunnel_cusecs": Sourced(14_250.0, SRC_BBMB_GLANCE),
        # The filling schedule BBMB operates to (rule curve). Two points, 2019 vintage, read
        # off the chart on page 44 of the RTDSS presentation: the labels are in the PDF text
        # layer, the values are where the labelled lines sit on the level gridlines. A press
        # figure of 1,662 ft for 19 August 2025 shows the schedule has been revised since;
        # no operator scenario is built on these until the current schedule is sourced.
        "rule_curve_max_level_ft_31_jul": Sourced(
            1650.0,
            SRC_BBMB_CBIP_DSS + ", page 44",
            "'MAXIMUM PERMISSIBLE RESERVOIR LEVEL UPTO 31 JULY AS PER RULE CURVE'; 2019 season "
            "chart; line on the 1,650 ft gridline",
        ),
        "rule_curve_max_level_ft_15_aug": Sourced(
            1670.0,
            SRC_BBMB_CBIP_DSS + ", page 44",
            "'MAXIMUM PERMISSIBLE RESERVOIR LEVEL UPTO 15AUGUST AS PER RULE CURVE'; 2019 season "
            "chart; line on the 1,670 ft gridline",
        ),
    },
)

PONG = Dam(
    name="Pong",
    river="Beas",
    lat=31.97139,
    lon=75.94667,
    coord_source=SRC_WIKIPEDIA_INFOBOX + "; 31.97139 N 75.94667 E",
    cwc_name="Pong Reservoir",
    frl_ft=Sourced(
        1390.0,
        SRC_BBMB_BULLETIN,
        "reduced FRL; design FRL 1400 ft (426.72 m) per " + SRC_PONG_EAP,
    ),
    frl_m=Sourced(423.67, SRC_CWC_FEED, "1390 ft x 0.3048 = 423.672 m"),
    mwl_ft=Sourced(
        1410.0, SRC_BBMB_BULLETIN, "reduced MWL; design MWL 1421 ft (433.12 m) per the EAP"
    ),
    min_level_ft=Sourced(1260.0, SRC_PONG_EAP + " (dead storage level 384.05 m)"),
    live_capacity_bcm=Sourced(
        6.157,
        SRC_CWC_FEED,
        "at the reduced FRL of 1390 ft; design live storage 7,290 MCM at 1400 ft per the EAP",
    ),
    gross_capacity_bcm=Sourced(8.570, SRC_PONG_EAP, "8570 x 10^6 m3 at design FRL"),
    catchment_km2_published=Sourced(
        12_560.0, SRC_PONG_EAP, "4850 sq. miles; 780 km2 under permanent snow"
    ),
    hydrobasins_outlet=4080700890,
    spillway_capacity_cusecs=Sourced(437_000.0, SRC_PONG_EAP, "12375 m3/s at MWL 433.12 m"),
    turbine_capacity_cusecs=Sourced(
        45_600.0,
        SRC_PONG_EAP,
        "6 penstock branches x 215 m3/s (7600 cusecs) each; the non-spill passing capacity",
    ),
    max_observed_inflow_cusecs=Sourced(734_000.0, SRC_PONG_EAP, "20784.56 m3/s on 14 August 2023"),
    extra={
        "design_flood_cusecs": Sourced(
            1_185_000.0, SRC_PONG_EAP, "33555 m3/s, 1 in over 10,000 years"
        ),
        "outlet_capacity_cusecs": Sourced(
            35_700.0, SRC_PONG_EAP, "4 outlets x 253 m3/s (8925 cusecs)"
        ),
        "avg_annual_runoff_bcm": Sourced(15.3, SRC_PONG_EAP, "15300 x 10^6 m3"),
        # the Beas is diverted below Pong at the Shah Nehar barrage into the Mukerian Hydel
        # Channel; what the channel can take is the most that can leave the river before
        # Naushera Mirthal and Dhilwan
        "mukerian_hydel_channel_cusecs": Sourced(
            11_500.0,
            SRC_PSPCL_MHP,
            "37 km lined channel from the Shah Nehar barrage, maximum carrying capacity 11500 "
            "cusecs (Stage-II channel, 3.5 km, also 11500 cusecs, takes off from it)",
        ),
        "eap_blue_alert": (
            "RWL about 1380 ft with inflows 75,000 cusecs on 31 August (EAP alert table)"
        ),
        "eap_orange_alert": (
            "RWL reaching 1390 ft by 20 August with inflows of the order of lakhs of cusecs (EAP)"
        ),
    },
)

RANJIT_SAGAR = Dam(
    name="Ranjit Sagar",
    river="Ravi",
    lat=32.4425,
    lon=75.7286,
    coord_source=SRC_WIKIPEDIA_INFOBOX + "; 32°26′33″N 75°43′43″E",
    cwc_name="Thein\\Ranjit Sagar",
    frl_ft=Sourced(
        m_to_feet(527.91), SRC_WRD_GUIDEBOOK + " Annexure Z (527.91 m)", "derived from metres"
    ),
    frl_m=Sourced(527.91, SRC_CWC_FEED + "; " + SRC_WRD_GUIDEBOOK + " Annexure Z"),
    mwl_ft=None,
    min_level_ft=Sourced(
        m_to_feet(487.0), SRC_WRD_GUIDEBOOK + " Annexure Z (487 m)", "derived from metres"
    ),
    live_capacity_bcm=Sourced(
        2.344,
        SRC_CWC_FEED,
        "Punjab WRD and the Wikipedia infobox agree: live storage 2344 million cubic metres",
    ),
    gross_capacity_bcm=Sourced(
        3.280, SRC_PUNJAB_WRD_DAMS, "Gross storage Capacity 3280 million cum"
    ),
    catchment_km2_published=Sourced(6_086.0, SRC_PUNJAB_WRD_DAMS, "Catchment area 6086 sq.km"),
    hydrobasins_outlet=4080698070,
    spillway_capacity_cusecs=Sourced(
        m3s_to_cusecs(24_637.0),
        SRC_PUNJAB_WRD_DAMS,
        "Maximum outflow 24637 cumecs; spillway design flood 20678 cumecs",
    ),
    # no turbine discharge is printed; estimated from the installed 4 x 150 MW at the
    # published maximum net head of 121.9 m with an assumed 0.9 overall efficiency
    turbine_capacity_cusecs=Sourced(
        m3s_to_cusecs(4 * 150e6 / (1000.0 * 9.80665 * 121.9 * 0.9)),
        SRC_PUNJAB_WRD_DAMS
        + " (4 x 150 MW, max net head 121.9 m) with an assumed efficiency of 0.9",
        "estimate, not a published figure; about 20,000 cusecs",
    ),
    extra={
        "installed_mw": Sourced(600.0, SRC_PUNJAB_WRD_DAMS, "4 x 150 MW"),
        "spillway_design_flood_cusecs": Sourced(
            m3s_to_cusecs(20_678.0), SRC_PUNJAB_WRD_DAMS, "20678 cumecs"
        ),
        "reservoir_area_km2": Sourced(87.0, SRC_PUNJAB_WRD_DAMS),
    },
)

DAMS: dict[str, Dam] = {d.name: d for d in (BHAKRA, PONG, RANJIT_SAGAR)}


# --------------------------------------------------------------------------------------
# Ghaggar (rain-fed pathway): HydroBASINS outlets for the two index points
# --------------------------------------------------------------------------------------
GHAGGAR_BASINS = {
    # sub-basin containing the point; upstream set = catchment above the index point
    "Bhankarpur": {"hydrobasins_outlet": 4080762860, "lat": 30.66, "lon": 76.85},
    "Khanauri": {"hydrobasins_outlet": 4080768840, "lat": 30.00, "lon": 76.20},
}


# --------------------------------------------------------------------------------------
# WRD control points and flood-intensity thresholds (guidebook section 3.2, page 11)
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ControlPoint:
    station: str
    river: str
    low_min: float
    low_max: float
    med_min: float
    med_max: float
    high_min: float
    note: str = ""
    source: str = SRC_WRD_GUIDEBOOK + " section 3.2, p. 11"

    def classify(self, cusecs: float) -> str | None:
        """'high', 'medium', 'low' or None (below the low band). Bands are half-open on the
        upper side so a value on a boundary belongs to the higher class, matching the
        guidebook's 'X and above' wording for High."""
        if cusecs is None or cusecs != cusecs:
            return None
        if cusecs >= self.high_min:
            return "high"
        if cusecs >= self.med_min:
            return "medium"
        if cusecs >= self.low_min:
            return "low"
        return None


CONTROL_POINTS: dict[str, ControlPoint] = {
    cp.station: cp
    for cp in (
        ControlPoint("Ropar Head Works", "Sutlej", 80_000, 140_000, 140_000, 200_000, 200_000),
        ControlPoint(
            "Railway Bridge Phillaur", "Sutlej", 100_000, 150_000, 150_000, 200_000, 200_000
        ),
        ControlPoint(
            "Harike Head Works", "Sutlej+Beas", 50_000, 200_000, 200_000, 300_000, 300_000
        ),
        ControlPoint("Ferozepur Head Works", "Sutlej", 50_000, 150_000, 150_000, 225_000, 225_000),
        ControlPoint("Naushera Mirthal", "Beas", 50_000, 150_000, 150_000, 225_000, 225_000),
        ControlPoint(
            "Dhilwan",
            "Beas",
            80_000,
            150_000,
            200_000,
            300_000,
            300_000,
            note="printed as Low 80,000-1,50,000 and Med 2,00,000-3,00,000; the 1.5 to 2.0 lakh "
            "gap is the guidebook's own; values in the gap classify as low",
        ),
        ControlPoint("Madhopur Head Works", "Ravi", 30_000, 60_000, 60_000, 100_000, 100_000),
        ControlPoint("Bhankarpur", "Ghaggar", 21_000, 31_500, 31_500, 42_000, 42_000),
        ControlPoint("BML Crossing", "Ghaggar", 10_000, 14_999, 15_000, 19_999, 20_000),
        ControlPoint(
            "Crossing with Narwana Branch", "Ghaggar", 21_000, 31_500, 31_500, 42_000, 42_000
        ),
    )
}


# --------------------------------------------------------------------------------------
# travel times (guidebook Annexure Z, page 118)
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Reach:
    river: str
    frm: str
    to: str
    km: float
    hours: float
    source: str = SRC_WRD_GUIDEBOOK + " Annexure Z, p. 118"


REACHES: tuple[Reach, ...] = (
    Reach("Sutlej", "Bhakra Dam", "Ropar Head Works", 75, 18),
    Reach("Sutlej", "Ropar Head Works", "Railway Bridge Phillaur", 70, 14),
    Reach("Sutlej", "Railway Bridge Phillaur", "Harike Head Works", 74, 20),
    Reach("Sutlej", "Harike Head Works", "Hussainiwala Head Works", 40, 12),
    Reach("Beas", "Pong Dam", "Shah Nehar Barrage", 5, 1.5),
    Reach("Beas", "Shah Nehar Barrage", "Naushera Mirthal", 34.3, 7.5),
    Reach("Beas", "Naushera Mirthal", "Nashahra Pattan", 14.7, 5),
    Reach("Beas", "Nashahra Pattan", "Tanda Bridge", 35.0, 12),
    Reach("Beas", "Tanda Bridge", "Harike Head Works", 126.3, 46),
    Reach("Ghaggar", "Bhankarpur", "Crossing with Narwana Branch", 52, 9),
    Reach("Ghaggar", "Crossing with Narwana Branch", "Khanauri", 90, 24),
    Reach("Ghaggar", "Khanauri", "Sardulgarh", 94, 39),
)

# totals as printed in Annexure Z, used by the tests to prove the reach table adds up
ANNEXURE_Z_TOTALS = {
    "Sutlej": Sourced(52.0, SRC_WRD_GUIDEBOOK + " Annexure Z", "Bhakra Dam to Harike, 219 km"),
    "Beas": Sourced(72.0, SRC_WRD_GUIDEBOOK + " Annexure Z", "Pong Dam to Harike, 215 km"),
    "Ghaggar": Sourced(72.0, SRC_WRD_GUIDEBOOK + " Annexure Z", "Bhankarpur to Sardulgarh, 236 km"),
}
ANNEXURE_Z_TOTAL_KM = {"Sutlej": 219.0, "Beas": 215.0, "Ghaggar": 236.0}

# Dhilwan is not an Annexure Z node. It lies between Tanda Bridge and Harike on the Beas;
# the WRD peak table dates put its 2023 and 2025 peaks two days after the Pong releases.
# We place it on the Tanda-Harike reach by distance (Dhilwan railway bridge is about 40 km
# below Tanda by river), which the routing module treats as an interpolated lag. Flagged as
# an assumption, not a guidebook value.
DHILWAN_FRACTION_OF_TANDA_HARIKE = 0.32


def travel_hours(river: str, frm: str, to: str) -> float:
    """Sum of reach times from ``frm`` to ``to`` along ``river`` (both nodes inclusive)."""
    chain = [r for r in REACHES if r.river == river]
    names = [chain[0].frm] + [r.to for r in chain]
    if frm not in names or to not in names:
        raise KeyError(f"{frm!r} or {to!r} not on the {river} reach table")
    i, j = names.index(frm), names.index(to)
    if j < i:
        raise ValueError(f"{to!r} is upstream of {frm!r}")
    return float(sum(r.hours for r in chain[i:j]))


# --------------------------------------------------------------------------------------
# season
# --------------------------------------------------------------------------------------
SEASON_START_MD = "06-01"  # WRD flood season and CWC monsoon window
SEASON_END_MD = "09-30"
