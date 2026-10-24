"""Adapter: E-REDES (PT), national distribution network reception capacity.

The source is the third release mode in the panel: not a document for printing and not a
file on a page, but **a dataset on an open data portal with a REST interface**.
Publication is quarterly, just like the Polish duty, and the row unit is
a substation or a high-voltage network cutting point.

What this adapter contributes to the panel
------------------------------------------
The first foreign source populating the **NODE** entity. Until now, available capacity
at the node was disclosed only by one Polish publisher, so the criterion "available
connection capacity" could be computed in a single jurisdiction. The Portuguese source
additionally provides the **composition of the substation group**, which is exactly the
information that, in the Polish panel, allows applications to be assigned to a node.

Resolving units, read this before you start comparing
-----------------------------------------------------
The publisher provides reception capacity and connected capacities in **MVA**, that is,
in apparent power. The schema's canonical unit is **kW of active power**. These are
different physical quantities and converting one into the other requires an assumption
about the power factor, which the publisher does not provide.

For this reason the `moc_dostepna` field remains **empty**, and the MVA values go into
extension fields together with the explicitly recorded source unit. This is the same
principle that was applied to the publisher reporting the number of free connection
slots instead of capacity: entering a number in a field with a different unit would be
fabrication, not harmonization.

The core of the NODE entity is nonetheless satisfied, because it is realized by the
second branch of the alternative, `ograniczenie_flaga`, set based on zero reception
capacity. Zero reception capacity is a disclosed value and means a constraint, not a
missing datum.

Input format
------------
CSV export from the portal (semicolon separator, technical headers, not labels).
The adapter deliberately reads a FILE, rather than querying the interface during parsing:
this makes the result reproducible from a manifest with a checksum, just as with the
other publishers.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .base import Adapter, ParseResult

PUBLISHER = "E-REDES S.A."
JURISDICTION = "PT"
#: The unit in which the publisher provides capacities. This is NOT the schema's
#: canonical unit (kW of active power) and it is not converted to it.
SOURCE_POWER_UNIT = "MVA"

#: Reception capacity columns broken down by voltage level, from the highest.
#: They serve solely to determine the voltage level at which the capacity occurs;
#: their values do not go into the capacity field because of the unit difference.
_VOLTAGE_COLUMNS = [
    ("capacidade_de_recepcao_at_mva_ultimo_trimestre", "AT"),
    ("capacidade_de_recepcao_mt_30kv_mva_ultimo_trimestre", "30 kV"),
    ("capacidade_de_recepcao_mt_15kv_mva_ultimo_trimestre", "15 kV"),
    ("capacidade_de_recepcao_mt_10kv_mva_ultimo_trimestre", "10 kV"),
]

_INSTALLATION_TYPE = {
    "SE AT": "substation_HV",
    "PC AT": "cutting_point_HV",
}


def _count(v) -> float | None:
    """Number from the portal notation; decimal comma allowed."""
    if v is None:
        return None
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if s == "" or s.lower() in {"none", "nan"}:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _quarter_to_date(v) -> str | None:
    """'2T2026' -> '2026-06-30'. Quarterly publication, last day of the quarter."""
    s = str(v or "").strip().upper()
    if len(s) == 6 and s[1] == "T" and s[0].isdigit() and s[2:].isdigit():
        kw, year = int(s[0]), int(s[2:])
        end = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}.get(kw)
        if end:
            return f"{year}-{end}"
    return None


class EredesAdapter(Adapter):
    publisher = PUBLISHER
    jurisdiction = JURISDICTION
    declared_fields = (
        "id_wezla", "nazwa_wezla", "lokalizacja_tekst", "poziom_napiecia",
        "ograniczenie_flaga", "data_publikacji",
    )
    declared_extensions = {
        "_jednostka_mocy_zrodlowa": "unit in which the publisher provides capacities (MVA)",
        "_moc_dostepna_mva": "reception capacity MV+HV in MVA, as in the source",
        "_moc_przylaczona_mva": "connected capacity in MVA",
        "_moc_zakontraktowana_mva": "contracted capacity in MVA",
        "_moc_w_potwierdzaniu_mva": "capacity in the process of confirmation in MVA",
        "_typ_instalacji": "substation or high-voltage network cutting point",
        "_dystrykt": "administrative district",
        "_gmina": "municipality",
        "_nuts3": "NUTS 3 statistical unit",
        "_wezel_rnt": "transmission network node to which the substation is connected",
    }
    detect_patterns = (r"capacidade.?rececao", r"e.?redes", r"\brnd\b")

    def parse(self, source) -> ParseResult:
        path = Path(str(source))
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f, delimiter=";"))

        records, without_code, zero_valued = [], 0, 0
        for w in rows:
            code = (w.get("codigo") or "").strip()
            if not code:
                without_code += 1
            capability = _count(w.get("capacidade_de_recepcao_mt_at_mva_ultimo_trimestre"))
            limit = None
            if capability is not None:
                limit = capability == 0.0
                zero_valued += int(limit)

            voltages = [label for col, label in _VOLTAGE_COLUMNS
                        if (_count(w.get(col)) or 0.0) > 0.0]

            records.append({
                "id_wezla": code or None,
                "nazwa_wezla": (w.get("instalacao") or "").strip() or None,
                # Composition of the substation group, the equivalent of the station list in the
                # node row of the Polish publisher, so it goes into the same field.
                "lokalizacja_tekst": (w.get("grupo_de_subestacoes_rari") or "").strip() or None,
                "poziom_napiecia": ", ".join(voltages) or None,
                "moc_dostepna": None,       # source unit is MVA, see module header
                "moc_zarezerwowana": None,  # as above.
                "ograniczenie_flaga": limit,
                "data_publikacji": _quarter_to_date(w.get("data_ultimo_trimestre")),
                "_encja": "WEZEL",
                "_jednostka_mocy_zrodlowa": SOURCE_POWER_UNIT,
                "_moc_dostepna_mva": capability,
                "_moc_przylaczona_mva": _count(w.get("potencia_de_ligacao_ligado_mva_ultimo_trimestre")),
                "_moc_zakontraktowana_mva": _count(w.get("potencia_de_ligacao_comprometido_mva_ultimo_trimestre")),
                "_moc_w_potwierdzaniu_mva": _count(w.get("potencia_de_ligacao_em_confirmacao_mva_ultimo_trimestre")),
                "_typ_instalacji": _INSTALLATION_TYPE.get(
                    (w.get("tipo_de_instalacao") or "").strip(),
                    (w.get("tipo_de_instalacao") or "").strip() or None),
                "_dystrykt": (w.get("distrito") or "").strip() or None,
                "_gmina": (w.get("concelho") or "").strip() or None,
                "_nuts3": (w.get("nut3") or "").strip() or None,
                "_wezel_rnt": (w.get("ligacao_rnt_barramento_60kv_ultimo_trimestre") or "").strip() or None,
            })

        import pandas as pd

        df = self.finalize(pd.DataFrame(records), document=path.name)
        notes = {
            "publisher": PUBLISHER,
            "jurisdiction": JURISDICTION,
            "release_mode": "open data portal, CSV export from REST interface",
            "rows": int(len(df)),
            "rows_without_installation_code": without_code,
            "nodes_with_zero_acceptance_capacity": zero_valued,
            "source_capacity_unit": SOURCE_POWER_UNIT,
            "available_capacity_empty_due_to_unit": True,
            "note_units": (
                "The publisher provides capacities in MVA (apparent power); the schema's canonical unit "
                "is kW of active power. Conversion would require an undisclosed power "
                "factor, so the moc_dostepna field remains empty, and the source values are "
                "in extension fields with an explicit unit."
            ),
        }
        return ParseResult(frame=df, report=notes)
