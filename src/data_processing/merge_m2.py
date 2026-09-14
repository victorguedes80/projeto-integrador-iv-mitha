"""
merge_m2.py

Faz o merge dos 5 arquivos essenciais de cada safra em uma tabela única,
com granularidade (timestamp_10min, line), pronta para o M2.

Arquivos usados por safra:
  - environmental{season}.csv   -> features climáticas (broadcast p/ todas as linhas)
  - soil{season}.csv            -> features de solo (média por linha)
  - indicators{season}.csv      -> GDD e derivados (diário, forward-fill)
  - valve_controller/water_valve{season}.csv -> rótulo valve_state
  - water_meter{season}.csv     -> rótulo water_volume

Gera, para cada safra:
  - dataset_m2_{season}.csv

Uso:
    python merge_m2.py
    python merge_m2.py --root . --out .
"""

import argparse
import os
import re
import gc
import glob
import time
import pandas as pd
import numpy as np


# ---------- constantes ----------

PASTAS_SAFRA = {"2023", "2024", "2025"}

# nomes canônicos para arquivos de válvula
VALVE_FILES = ("valve_controller", "water_valve")

# colunas técnicas a descartar
DROP_COLS = {"Unnamed: 0", "generated_by", "device_identifier", "index"}

# renomeação para evitar colisão entre arquivos
RENAMES = {
    "environmental": {
        "temperature": "env_temperature",
        "humidity": "env_humidity",
        "co2": "env_co2",
        "pressure": "env_pressure",
    },
    "soil": {
        "temperature": "soil_temperature",
        "humidity": "soil_humidity",
        "electrical_conductivity": "soil_ec",
    },
    "indicators": {
        "gdd": "gdd",
        "daily_mean_temperature": "daily_mean_temperature",
        "standard_day_degree_daily": "sdd",
        "ontario_units": "ontario_units",
        "daily_max": "daily_max",
        "daily_max_above_Tbase": "daily_max_above_tbase",
        "daily_max_reduction": "daily_max_reduction",
    },
    "water_meter": {
        "current_volume": "water_volume",
    },
}


# ---------- utilidades ----------

def find_csv(root, season, base):
    """
    Procura o CSV de uma safra por nome base.
    Aceita tanto layout plano (root/*.csv) quanto em pastas (root/2023/*.csv).
    """
    candidates = []
    for folder in (os.path.join(root, season), root):
        for name in [f"{base}{season}.csv"]:
            p = os.path.join(folder, name)
            if os.path.exists(p):
                candidates.append(p)
    return candidates[0] if candidates else None


def find_valve_csv(root, season):
    for base in VALVE_FILES:
        p = find_csv(root, season, base)
        if p:
            return p
    return None


def parse_ts(series):
    """Converte timestamps em ms para datetime UTC."""
    return pd.to_datetime(series, unit="ms", errors="coerce", utc=True)


def to_10min(ts_series):
    """Arredonda timestamps para janelas de 10 minutos."""
    return ts_series.dt.floor("10min")


def encode_valve(series):
    """Converte valve_state para 0/1 (0=close, 1=open)."""
    if series.dtype == object:
        s = series.astype(str).str.strip().str.lower()
        mapping = {
            "open": 1, "on": 1, "true": 1, "1": 1, "aberta": 1,
            "close": 0, "closed": 0, "off": 0, "false": 0, "0": 0, "fechada": 0,
        }
        return s.map(mapping).astype("Int64")
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def clean_df(df, base_name):
    """Remove colunas técnicas e renomeia colunas conhecidas."""
    # 1. remove Unnamed: 0 e outras
    drop = [c for c in df.columns if c in DROP_COLS or c.startswith("Unnamed")]
    df = df.drop(columns=drop, errors="ignore")

    # 2. renomeia conforme o mapa
    if base_name in RENAMES:
        df = df.rename(columns=RENAMES[base_name])

    return df


def load_base(root, season, base):
    """Carrega e pré-processa um CSV base."""
    path = find_csv(root, season, base)
    if not path:
        print(f"  [aviso] {base}{season}.csv não encontrado")
        return None
    df = pd.read_csv(path, low_memory=False)
    df = clean_df(df, base)

    # parse timestamp
    ts_col = "ts_generation"
    if ts_col not in df.columns:
        print(f"  [aviso] {base}{season}.csv sem coluna '{ts_col}'")
        return None
    df["ts"] = parse_ts(df[ts_col])
    df = df.dropna(subset=["ts"])
    df["timestamp_10min"] = to_10min(df["ts"])

    # padroniza 'line' se existir
    if "line" in df.columns:
        df["line"] = pd.to_numeric(df["line"], errors="coerce").astype("Int64")

    return df


# ---------- carregadores por arquivo ----------

def load_environmental(root, season):
    df = load_base(root, season, "environmental")
    if df is None:
        return None
    keep = ["timestamp_10min"]
    for c in ["env_temperature", "env_humidity", "env_co2", "env_pressure"]:
        if c in df.columns:
            keep.append(c)
    df = df[keep].groupby("timestamp_10min", as_index=False).mean(numeric_only=True)
    return df


def load_soil(root, season):
    df = load_base(root, season, "soil")
    if df is None:
        return None
    if "line" not in df.columns:
        print(f"  [aviso] soil{season}.csv sem coluna 'line'")
        return None
    keep = ["timestamp_10min", "line"]
    for c in ["soil_temperature", "soil_humidity", "soil_ec"]:
        if c in df.columns:
            keep.append(c)
    df = df[keep].dropna(subset=["line"])
    # média por (timestamp, line) — 2 sensores por linha em 2024/2025
    df = df.groupby(["timestamp_10min", "line"], as_index=False).mean(numeric_only=True)
    return df


def load_indicators(root, season):
    df = load_base(root, season, "indicators")
    if df is None:
        return None
    keep = ["ts"]
    for c in ["gdd", "daily_mean_temperature", "sdd", "ontario_units",
              "daily_max", "daily_max_above_tbase", "daily_max_reduction"]:
        if c in df.columns:
            keep.append(c)
    df = df[keep].drop_duplicates(subset=["ts"]).sort_values("ts")
    return df


def load_valve(root, season):
    path = find_valve_csv(root, season)
    if not path:
        print(f"  [aviso] arquivo de válvula de {season} não encontrado")
        return None
    df = pd.read_csv(path, low_memory=False)
    base_name = os.path.basename(path).replace(season, "").replace(".csv", "").rstrip("_")
    df = clean_df(df, base_name)

    if "ts_generation" not in df.columns:
        print(f"  [aviso] {os.path.basename(path)} sem ts_generation")
        return None
    df["ts"] = parse_ts(df["ts_generation"])
    df = df.dropna(subset=["ts"])
    df["timestamp_10min"] = to_10min(df["ts"])

    if "line" not in df.columns:
        print(f"  [aviso] {os.path.basename(path)} sem line")
        return None
    df["line"] = pd.to_numeric(df["line"], errors="coerce").astype("Int64")

    if "valve_state" not in df.columns:
        print(f"  [aviso] {os.path.basename(path)} sem valve_state")
        return None
    df["valve_state"] = encode_valve(df["valve_state"])

    df = df[["timestamp_10min", "line", "valve_state"]].dropna(subset=["line"])
    # agrega por janela: se qualquer válvula abriu na janela, considera irrigação
    df = df.groupby(["timestamp_10min", "line"], as_index=False)["valve_state"].max()
    return df


def load_water_meter(root, season):
    df = load_base(root, season, "water_meter")
    if df is None:
        return None
    if "line" not in df.columns or "water_volume" not in df.columns:
        print(f"  [aviso] water_meter{season}.csv incompleto")
        return None
    df = df[["timestamp_10min", "line", "water_volume"]].dropna(subset=["line"])
    # descarta linha #0 (medidor geral) — fica só com linhas de cultivo
    df = df[df["line"] >= 1]
    # soma de volume por (timestamp, line) — várias medições na mesma janela
    df = df.groupby(["timestamp_10min", "line"], as_index=False)["water_volume"].sum()
    return df


# ---------- merge de uma safra ----------

def merge_season(root, season, out_dir):
    print(f"\n=== Safra {season} ===")

    env = load_environmental(root, season)
    soil = load_soil(root, season)
    ind = load_indicators(root, season)
    valve = load_valve(root, season)
    wm = load_water_meter(root, season)

    if env is None or soil is None:
        print(f"  [erro] dados essenciais ausentes em {season}")
        return None

    # grid base: todos os timestamps x todas as linhas
    timestamps = env["timestamp_10min"].unique()
    lines = sorted(int(l) for l in soil["line"].dropna().unique() if int(l) >= 1)
    print(f"  timestamps: {len(timestamps)} | linhas: {lines}")

    grid = pd.MultiIndex.from_product(
        [timestamps, lines], names=["timestamp_10min", "line"]
    ).to_frame(index=False)

    # 1. environmental (broadcast para todas as linhas)
    df = grid.merge(env, on="timestamp_10min", how="left")

    # 2. soil
    df = df.merge(soil, on=["timestamp_10min", "line"], how="left")

    # 3. valve
    if valve is not None:
        df = df.merge(valve, on=["timestamp_10min", "line"], how="left")

    # 4. water_meter
    if wm is not None:
        df = df.merge(wm, on=["timestamp_10min", "line"], how="left")

    # 5. indicators — merge_asof (forward-fill diário)
    if ind is not None:
        df = df.sort_values("timestamp_10min")
        ind = ind.sort_values("ts")
        df = pd.merge_asof(
            df, ind.drop(columns=["ts"]),
            left_on="timestamp_10min", right_index=False,
            left_by=None, right_on=None,
            direction="backward",
            allow_exact_matches=True,
        ) if False else df  # fallback se merge_asof falhar
        # versão robusta:
        df = df.sort_values("timestamp_10min").reset_index(drop=True)
        ind_sorted = ind.sort_values("ts").rename(columns={"ts": "timestamp_10min"})
        df = pd.merge_asof(
            df, ind_sorted,
            on="timestamp_10min",
            direction="backward",
        )

    # ordena e organiza colunas
    df = df.sort_values(["timestamp_10min", "line"]).reset_index(drop=True)

    # converte de volta o timestamp para ms (opcional, mais portável)
    df["timestamp_ms"] = df["timestamp_10min"].astype("int64") // 10**6

    # reordena colunas
    cols_first = ["timestamp_10min", "timestamp_ms", "line"]
    cols_rest = [c for c in df.columns if c not in cols_first]
    df = df[cols_first + cols_rest]

    out = os.path.join(out_dir, f"dataset_m2_{season}.csv")
    df.to_csv(out, index=False)

    # diagnóstico
    print(f"  shape: {df.shape}")
    print(f"  colunas: {list(df.columns)}")
    print(f"  missing % (top 5):")
    miss = df.isna().mean().sort_values(ascending=False).head(5)
    for c, v in miss.items():
        print(f"    - {c}: {v:.2%}")
    print(f"  [ok] {out}")

    # libera memória
    del env, soil, ind, valve, wm, df
    gc.collect()

    return out


# ---------- main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Pasta raiz (padrão: atual)")
    parser.add_argument("--out", default=".", help="Pasta de saída")
    parser.add_argument("--seasons", nargs="*", default=["2023", "2024", "2025"])
    args = parser.parse_args()

    t0 = time.time()
    print(f"Pasta raiz : {os.path.abspath(args.root)}")
    print(f"Safras     : {args.seasons}")

    for season in args.seasons:
        merge_season(args.root, season, args.out)

    print(f"\n[tempo total] {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()