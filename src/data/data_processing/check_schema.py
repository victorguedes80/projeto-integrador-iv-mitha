"""
check_schema.py  (v6 - FINAL)

Lê APENAS o cabeçalho dos CSVs reais e gera matriz de compatibilidade
entre as safras 2023, 2024 e 2025. Não carrega os dados (nrows=0).

Unifica automaticamente:
  water_valve (2023) ≡ valve_controller (2024, 2025)

Layout suportado:
  A) CSVs na mesma pasta (plano)
  B) CSVs em subpastas 2023/, 2024/, 2025/

Uso:
    python check_schema.py
    python check_schema.py --root . --out .
"""

import argparse
import os
import re
import glob
import time
import pandas as pd


# ---------- constantes ----------

PASTAS_SAFRA = {"2023", "2024", "2025"}

NOME_CANONICO = {
    "water_valve": "valve",
    "valve_controller": "valve",
}

IGNORAR = {
    "schema_from_readmes.csv", "schema_readmes_long.csv",
    "schema_meta_por_arquivo.csv",
    "schema_from_csvs.csv", "schema_csvs_long.csv",
}


# ---------- descoberta ----------

def find_csvs(root: str):
    """
    Procura CSVs em:
      - root/*.csv
      - root/2023/*.csv, root/2024/*.csv, root/2025/*.csv
    Ignora arquivos de saída gerados pelos próprios scripts.
    """
    found = set()

    for p in glob.glob(os.path.join(root, "*.csv")):
        if os.path.basename(p) not in IGNORAR:
            found.add(os.path.abspath(p))

    for sub in sorted(os.listdir(root)):
        if sub not in PASTAS_SAFRA:
            continue
        subpath = os.path.join(root, sub)
        if not os.path.isdir(subpath):
            continue
        for p in glob.glob(os.path.join(subpath, "*.csv")):
            if os.path.basename(p) not in IGNORAR:
                found.add(os.path.abspath(p))

    return sorted(found)


# ---------- normalização ----------

def extract_safra(filename: str) -> str:
    m = re.search(r"(20\d{2})", filename)
    return m.group(1) if m else "desconhecida"


def normalize_base(arquivo: str) -> str:
    base = arquivo.replace(".csv", "")
    base = re.sub(r"20\d{2}", "", base).rstrip("_")
    return NOME_CANONICO.get(base, base)


# ---------- main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Pasta raiz (padrão: atual)")
    parser.add_argument("--out", default=".", help="Pasta de saída")
    args = parser.parse_args()

    t0 = time.time()

    csvs = find_csvs(args.root)
    if not csvs:
        print(f"[erro] Nenhum CSV encontrado em: {os.path.abspath(args.root)}")
        return

    print(f"CSVs encontrados: {len(csvs)}")
    for c in csvs:
        rel = os.path.relpath(c, args.root)
        print(f"  - {rel}  (safra={extract_safra(os.path.basename(c))})")

    rows = []
    for csv in csvs:
        arquivo = os.path.basename(csv)
        try:
            df = pd.read_csv(csv, nrows=0)
        except Exception as e:
            print(f"[erro] {arquivo}: {e}")
            continue
        safra = extract_safra(arquivo)
        for col in df.columns:
            rows.append({
                "safra": safra,
                "arquivo": arquivo,
                "arquivo_base": normalize_base(arquivo),
                "coluna": col.strip(),
            })

    if not rows:
        print("[erro] Nenhuma coluna lida.")
        return

    df = pd.DataFrame(rows).drop_duplicates()

    pivot = (
        df.assign(presente=1)
          .pivot_table(index=["arquivo_base", "coluna"],
                       columns="safra",
                       values="presente",
                       aggfunc="max",
                       fill_value=0)
          .reset_index()
    )

    safra_cols = [c for c in pivot.columns if c in ("2023", "2024", "2025")]
    pivot["n_safras"] = pivot[safra_cols].sum(axis=1)

    pivot = pivot.sort_values(
        by=["arquivo_base", "n_safras", "coluna"],
        ascending=[True, False, True],
    ).reset_index(drop=True)

    out1 = os.path.join(args.out, "schema_from_csvs.csv")
    out2 = os.path.join(args.out, "schema_csvs_long.csv")

    pivot.to_csv(out1, index=False)
    df.to_csv(out2, index=False)

    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 220)

    print("\n===== MATRIZ DE COMPATIBILIDADE (CSVs reais) =====\n")
    print(pivot.to_string(index=False))

    print(f"\n[ok] {out1}")
    print(f"[ok] {out2}")
    print(f"[tempo total] {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()