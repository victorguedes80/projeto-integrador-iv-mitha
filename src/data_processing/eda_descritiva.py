"""
eda_descritiva.py  (v3 — consolidado com os 3 anos)

Análise estatística descritiva do dataset do M2 (MITHA).

Faz duas análises:
  1) POR SAFRA: 2023, 2024, 2025 separadamente
  2) CONSOLIDADO: os 3 anos juntos, apenas nas colunas comuns

Nenhum filtro de ruído/outlier é aplicado.

Uso:
    python eda_descritiva.py
    python eda_descritiva.py --root . --out ./eda
"""

import argparse
import os
import time
import pandas as pd
import numpy as np


SAFRAS = ["2023", "2024", "2025"]
ID_COLS = {"timestamp_10min", "timestamp_ms", "line"}

LABELS = {
    "env_temperature":         "Temperatura do ar (°C)",
    "env_humidity":            "Umidade do ar (%)",
    "env_co2":                 "CO2 (ppm)",
    "env_pressure":            "Pressão barométrica (hPa)",
    "soil_temperature":        "Temperatura do solo (°C)",
    "soil_humidity":           "Umidade do solo (%)",
    "soil_ec":                 "Condutividade elétrica do solo (µS/cm)",
    "valve_state":             "Estado da válvula (0=fechada, 1=aberta)",
    "water_volume":            "Volume acumulado (m³)",
    "gdd":                     "Graus-dia acumulados (GDD)",
    "daily_mean_temperature":  "Temperatura média diária (°C)",
    "sdd":                     "Standard Day Degree (°C)",
    "ontario_units":           "Ontario Units (°C)",
    "daily_max":               "Temperatura máxima diária (°C)",
    "daily_max_above_tbase":   "Máx acima da base (°C)",
    "daily_max_reduction":     "Máx com cutoff (°C)",
}


# ---------- carregamento ----------

def load_datasets(root):
    datasets = {}
    for s in SAFRAS:
        path = os.path.join(root, f"dataset_m2_{s}.csv")
        if not os.path.exists(path):
            print(f"[aviso] não encontrado: {path}")
            continue
        df = pd.read_csv(path, low_memory=False)
        datasets[s] = df
        print(f"[ok] {path}: shape={df.shape}")
    return datasets


# ---------- utilidades ----------

def numeric_feature_cols(df, drop_ids=True):
    cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if drop_ids:
        cols = [c for c in cols if c not in ID_COLS]
    return cols


def describe_df(df, cols):
    rows = []
    for c in cols:
        s = df[c]
        rows.append({
            "variavel": c,
            "descricao": LABELS.get(c, ""),
            "count": int(s.notna().sum()),
            "missing": int(s.isna().sum()),
            "missing_%": round(100 * s.isna().mean(), 2),
            "mean": s.mean(),
            "median": s.median(),
            "std": s.std(),
            "min": s.min(),
            "q25": s.quantile(0.25),
            "q75": s.quantile(0.75),
            "max": s.max(),
            "n_unique": int(s.nunique()),
        })
    return pd.DataFrame(rows).set_index("variavel").round(4)


def common_numeric_cols(datasets):
    sets = [set(numeric_feature_cols(df)) for df in datasets.values()]
    return sorted(set.intersection(*sets)) if sets else []


def print_stats(title, stats):
    print("\n" + "=" * 110)
    print(title)
    print("=" * 110)
    if stats.empty:
        print("(vazio)")
        return
    cols_order = ["descricao", "count", "missing", "missing_%",
                  "mean", "median", "std", "min", "q25", "q75", "max", "n_unique"]
    stats = stats[[c for c in cols_order if c in stats.columns]]
    with pd.option_context(
        "display.max_rows", None,
        "display.max_columns", None,
        "display.width", 240,
        "display.float_format", lambda v: f"{v:,.3f}",
    ):
        print(stats.to_string())


# ---------- main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Pasta com os dataset_m2_*.csv")
    parser.add_argument("--out", default="./eda", help="Pasta de saída")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()

    print("Carregando datasets...")
    datasets = load_datasets(args.root)
    if not datasets:
        print("[erro] nenhum dataset_m2_*.csv encontrado.")
        return

    # ---------- 1) estatísticas por safra ----------
    for s in SAFRAS:
        if s not in datasets:
            continue
        df = datasets[s]
        cols = numeric_feature_cols(df)
        stats = describe_df(df, cols)
        print_stats(f"ESTATÍSTICAS DESCRITIVAS — SAFRA {s}  (n = {len(df):,} linhas)", stats)
        out = os.path.join(args.out, f"descritiva_{s}.csv")
        stats.to_csv(out)
        print(f"[ok] {out}")

    # ---------- 2) colunas comuns às 3 safras ----------
    common = common_numeric_cols(datasets)

    print("\n" + "=" * 110)
    print(f"COLUNAS COMUNS ÀS 3 SAFRAS ({len(common)} variáveis):")
    print("=" * 110)
    for c in common:
        print(f"  - {c:28s}  {LABELS.get(c, '')}")

    # ---------- 3) estatísticas consolidadas (3 anos) ----------
    frames = []
    for s in SAFRAS:
        if s not in datasets:
            continue
        sub = datasets[s][common].copy()
        sub["_safra"] = s
        frames.append(sub)
    df_all = pd.concat(frames, ignore_index=True)

    print(f"\nDataset consolidado (3 safras): {len(df_all):,} linhas  ×  {len(common)} variáveis")

    stats_all = describe_df(df_all, common)
    print_stats("ESTATÍSTICAS DESCRITIVAS — CONSOLIDADO (2023 + 2024 + 2025)", stats_all)
    out = os.path.join(args.out, "descritiva_consolidado.csv")
    stats_all.to_csv(out)
    print(f"[ok] {out}")

    # ---------- 4) comparação de médias por safra ----------
    means = {s: datasets[s][common].mean() for s in SAFRAS if s in datasets}
    means_df = pd.DataFrame(means).round(4)
    means_df["consolidado"] = df_all[common].mean().round(4)
    means_df["descricao"] = [LABELS.get(c, "") for c in means_df.index]
    means_df = means_df[["descricao"] + [s for s in SAFRAS if s in datasets] + ["consolidado"]]

    print("\n" + "=" * 110)
    print("COMPARAÇÃO DE MÉDIAS POR SAFRA")
    print("=" * 110)
    with pd.option_context("display.max_rows", None, "display.width", 240,
                           "display.float_format", lambda v: f"{v:,.3f}"):
        print(means_df.to_string())
    means_df.to_csv(os.path.join(args.out, "media_por_safra.csv"))
    print(f"[ok] {os.path.join(args.out, 'media_por_safra.csv')}")

    # ---------- 5) comparação de medianas por safra ----------
    medians = {s: datasets[s][common].median() for s in SAFRAS if s in datasets}
    medians_df = pd.DataFrame(medians).round(4)
    medians_df["consolidado"] = df_all[common].median().round(4)
    medians_df["descricao"] = [LABELS.get(c, "") for c in medians_df.index]
    medians_df = medians_df[["descricao"] + [s for s in SAFRAS if s in datasets] + ["consolidado"]]

    print("\n" + "=" * 110)
    print("COMPARAÇÃO DE MEDIANAS POR SAFRA")
    print("=" * 110)
    with pd.option_context("display.max_rows", None, "display.width", 240,
                           "display.float_format", lambda v: f"{v:,.3f}"):
        print(medians_df.to_string())
    medians_df.to_csv(os.path.join(args.out, "mediana_por_safra.csv"))
    print(f"[ok] {os.path.join(args.out, 'mediana_por_safra.csv')}")

    # ---------- 6) proporção de irrigação ----------
    print("\n" + "=" * 110)
    print("PROPORÇÃO DE IRRIGAÇÃO (valve_state = 1)")
    print("=" * 110)
    for s in SAFRAS:
        if s not in datasets:
            continue
        df = datasets[s]
        if "valve_state" in df.columns:
            pct = df["valve_state"].mean() * 100
            print(f"  {s}: {pct:.2f}% do tempo com válvula aberta  "
                  f"({int(df['valve_state'].sum()):,} de {len(df):,} janelas)")

    print(f"\n[tempo total] {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()