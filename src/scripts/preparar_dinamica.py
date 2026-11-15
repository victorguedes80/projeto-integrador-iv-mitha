"""Prepara df_dinamica em memória com as mesmas transformações do notebook, sem refazer merges."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DESTINO = ROOT / "data/m3/df_dinamica_2024_linha_3.csv"


def preparar():
    d = pd.read_csv(ROOT / "data/m3/dataset_2024_linha_3.csv")
    d["date"] = pd.to_datetime(d.ts_generation, unit="ms", utc=True)
    # Calcula os atrasos antes de remover linhas incompletas.
    regular = d.ts_generation.diff().between(580_000, 620_000)
    for lag in [1, 2]:
        sequencia = regular.rolling(lag, min_periods=lag).sum().eq(lag)
        d[f"humidity_soil_lag_{lag}"] = d.humidity_soil.shift(lag).where(sequencia)
    dinamica = d.dropna().copy()
    for lag in [1, 2]:
        dinamica[f"ts_lag_{lag}"] = d.ts_generation.shift(lag).loc[dinamica.index]
        dinamica[f"valve_state_lag_{lag}"] = d.valve_state.shift(lag).loc[dinamica.index]
    dinamica["intervalo_min"] = (dinamica.ts_generation - dinamica.ts_lag_2) / 60_000
    dinamica = dinamica.loc[dinamica.intervalo_min.between(19, 21)].copy()
    dinamica["erro"] = 27 - dinamica.humidity_soil
    dinamica["dh_20min"] = (dinamica.humidity_soil - dinamica.humidity_soil_lag_2) / 20
    # dinamica.to_csv(DESTINO, index=False)
    return dinamica


if __name__ == "__main__":
    print(f"{len(preparar())} linhas preparadas em memória")
