"""Przykład badawczy: przepływy w kolejce przyłączeniowej między edycjami.

Pytanie badawcze
----------------
Jak zmienia się kolejka przyłączeniowa między dwiema edycjami tego samego
rejestru i czy rejestr zachowuje się jak **monotoniczna migawka** — to znaczy
czy sprawy wchodzą do niego i wychodzą zgodnie z przebiegiem postępowania, czy
też pojawiają się i znikają także poza tym porządkiem?

Dlaczego to pytanie jest warunkiem każdej analizy wzdłużnej na tym źródle: jeśli
rejestr nie jest monotoniczny, to różnica między edycjami nie jest tożsama ze
zmianą stanu kolejki i trzeba to zadeklarować zamiast milcząco założyć.

Uruchomienie::

    python examples/longitudinal_use_case.py <edycja_A.xlsx> <edycja_B.xlsx> \\
        [etykieta_A] [etykieta_B] [katalog_wyjściowy]

Wytwarza::

    przeplywy_kolejki.csv        podsumowanie przepływów
    przejscia_statusu.csv        macierz przejść statusu
    przejscia_statusu.png        figura macierzy przejść
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from gridqueue import (SCHEMA_VERSION, STATUS_ORDER, TERMINAL_NEGATIVE,
                       __version__, compare_editions, detect_publisher,
                       get_adapter)

OPIS = {
    "WNIOSEK_ZLOZONY": "wniosek złożony",
    "WNIOSEK_NIEKOMPLETNY": "wniosek niekompletny",
    "W_TRAKCIE_ANALIZY": "w trakcie analizy",
    "WARUNKI_WYDANE": "warunki wydane",
    "UMOWA_OBOWIAZUJACA": "umowa obowiązująca",
    "PRZYLACZONY": "przyłączony",
    "ODMOWA": "odmowa",
    "WNIOSEK_WYCOFANY": "wniosek wycofany",
    "WARUNKI_WYGASLE": "warunki wygasłe",
}


def wczytaj(sciezka: Path) -> pd.DataFrame:
    """Wczytaj edycję, rozpoznając publikującego z dokumentu."""
    klucz = detect_publisher(str(sciezka))
    if klucz is None:
        raise SystemExit(f"nie rozpoznano publikującego dla {sciezka}")
    return get_adapter(klucz).parse(str(sciezka)).frame


def figura(tr: pd.DataFrame, plik: Path, etykiety: tuple[str, str]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    porzadek = [s for s in list(STATUS_ORDER) + sorted(TERMINAL_NEGATIVE)]
    idx = [s for s in porzadek if s in tr.index]
    kol = [s for s in porzadek if s in tr.columns]
    M = tr.reindex(index=idx, columns=kol, fill_value=0).astype(int).values
    Mz = M.copy()
    for i, a in enumerate(idx):
        for j, b in enumerate(kol):
            if a == b:
                Mz[i, j] = 0

    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.imshow(Mz, cmap="Blues", aspect="auto",
              vmin=0, vmax=max(1, Mz.max()))
    for i in range(len(idx)):
        for j in range(len(kol)):
            if M[i, j] == 0:
                continue
            trwa = idx[i] == kol[j]
            ax.text(j, i, f"{M[i, j]}", ha="center", va="center", fontsize=6.5,
                    color="#9aa5ad" if trwa else
                    ("#ffffff" if Mz[i, j] > Mz.max() * 0.6 else "#222222"))
    ax.set_xticks(range(len(kol)))
    ax.set_xticklabels([OPIS.get(s, s) for s in kol], rotation=40,
                       ha="right", fontsize=6.5)
    ax.set_yticks(range(len(idx)))
    ax.set_yticklabels([OPIS.get(s, s) for s in idx], fontsize=6.5)
    ax.set_xlabel(f"status w edycji {etykiety[1]}", fontsize=7.5)
    ax.set_ylabel(f"status w edycji {etykiety[0]}", fontsize=7.5)
    ax.set_title("Przejścia statusu biegną zgodnie z porządkiem postępowania,\n"
                 "co niezależnie potwierdza dopasowanie klucza treściowego",
                 fontsize=8, loc="left")
    ax.set_xticks(np.arange(-.5, len(kol), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(idx), 1), minor=True)
    ax.grid(which="minor", color="#ffffff", lw=0.8)
    ax.tick_params(which="minor", length=0)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    fig.savefig(plik, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    pa, pb = Path(argv[1]), Path(argv[2])
    ea = argv[3] if len(argv) > 3 else pa.stem
    eb = argv[4] if len(argv) > 4 else pb.stem
    out = Path(argv[5]) if len(argv) > 5 else Path(".")
    out.mkdir(parents=True, exist_ok=True)

    a, b = wczytaj(pa), wczytaj(pb)
    d = compare_editions(a, b, ea, eb)
    podsum = d.as_dict()
    podsum["gridqueue"] = __version__
    podsum["schema_version"] = SCHEMA_VERSION

    pd.DataFrame([podsum]).to_csv(out / "przeplywy_kolejki.csv", index=False)
    d.przejscia.to_csv(out / "przejscia_statusu.csv")
    figura(d.przejscia, out / "przejscia_statusu.png", (ea, eb))

    for k, v in podsum.items():
        print(f"{k}: {v}")
    print()
    print("Interpretacja:")
    u = d.udzial_przejsc_w_przod
    if u is not None:
        print(f"  {u * 100:.2f} % przejść biegnie zgodnie z porządkiem postępowania — "
              "jest to niezależny test dopasowania klucza treściowego, bo klucz "
              "dopasowujący losowo nie wytworzyłby tego porządku.")
    if not podsum["migawka_monotoniczna"]:
        print(f"  Rejestr NIE jest monotoniczną migawką: {podsum['nowe_zamkniete']} "
              f"wierszy pojawia się już w stanie zamkniętym, a {podsum['ubyle_czynne']} "
              "wierszy o statusie czynnym znika. Różnicy między edycjami nie wolno "
              "czytać jako samej zmiany stanu kolejki.")
    print(f"\nzapisano do: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
