"""Auditoria dos dados usados na análise de dinâmica da umidade do solo.

Gera em results/dinamica_irrigacao/<versao>/auditoria/:
  lacunas.csv     início, fim e duração de cada lacuna (por safra e linha), por tipo:
                  - sem_registro: timestamp ausente no dataset processado
                  - umidade_ausente: registro existe mas umidade é NaN
                  - umidade_invalida: umidade = 0 ou > 100 % (sequências)
  hidrometro.csv  semântica do contador (monotonicidade), leituras invalidadas,
                  volume total por linha
  umidade.csv     faixa, zeros, valores > 100, picos isolados corrigidos
  valve_state.csv distribuição de valve_state vs. passos com vazão

Uso: python src/data_processing/auditoria_dinamica.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "utils"))
from resposta_irrigacao import DT, carregar, runs, SAIDA  # noqa: E402

DEST = SAIDA / "auditoria"


def lacunas(ano, linha, g):
    linhas = []
    idx = g.index
    tipos = {
        "sem_registro": ~g["registro_existe"].values,
        "umidade_ausente": g["registro_existe"].values & g["soil_humidity"].isna().values,
        "umidade_invalida": g["umid_invalida"].values,
    }
    for tipo, m in tipos.items():
        for a, b in runs(m):
            linhas.append(dict(ano=ano, linha=linha, tipo=tipo,
                               inicio=idx[a], fim=idx[b],
                               amostras=b - a + 1, duracao_min=(b - a + 1) * DT,
                               interpolavel=(b - a + 1) <= 2 and tipo != "sem_registro"))
    return linhas


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    lac, hid, umi, val = [], [], [], []
    for ano in (2023, 2024, 2025):
        for linha, g in carregar(ano):
            lac += lacunas(ano, linha, g)
            v = g["water_volume"]
            d = v.diff()
            hid.append(dict(
                ano=ano, linha=linha, leituras=int(v.notna().sum()),
                frac_nao_decrescente=float(((d >= 0) | d.isna()).mean()),
                quedas=int((d < 0).sum()),
                invalidadas_pico=int(g["vol_motivo"].eq("pico").sum()),
                resets=int(g["vol_motivo"].eq("reset").sum()),
                invalidadas_zero=int(g["vol_motivo"].eq("zero").sum()),
                volume_bruto_max_menos_min=float(v.max() - v.min()),  # inflado por picos dobrados
                volume_limpo_max_menos_min=float(g["vol_limpo"].max() - g["vol_limpo"].min()),
                volume_limpo_soma_vazao=  # exclui volume que passou durante lacunas longas
                float(g["vazao"].clip(lower=0).sum()),
                passos_com_vazao=int((g["vazao"] > 0).sum()),
            ))
            s = g["soil_humidity"]
            umi.append(dict(
                ano=ano, linha=linha, registros=int(s.notna().sum()),
                minimo=float(s.min()), p01=float(s.quantile(.01)), mediana=float(s.median()),
                p99=float(s.quantile(.99)), maximo=float(s.max()),
                zeros=int((s == 0).sum()), acima_100=int((s > 100).sum()),
                picos_corrigidos=int(g["umid_corrigida"].sum()),
                interpoladas=int(g["umid_interp"].sum()),
            ))
            vs = g["valve_state"]
            fl = g["vazao"] > 0
            val.append(dict(
                ano=ano, linha=linha, frac_valve_1=float(vs.mean()),
                frac_vazao_com_valve_1=float(vs[fl].mean()) if fl.any() else np.nan,
                frac_valve_1_sem_vazao=float(vs[~fl & g["vazao"].notna()].mean()),
            ))
    pd.DataFrame(lac).to_csv(DEST / "lacunas.csv", index=False)
    pd.DataFrame(hid).to_csv(DEST / "hidrometro.csv", index=False)
    pd.DataFrame(umi).to_csv(DEST / "umidade.csv", index=False)
    pd.DataFrame(val).to_csv(DEST / "valve_state.csv", index=False)
    lac = pd.DataFrame(lac)
    print(lac.groupby(["ano", "tipo"]).agg(n=("amostras", "size"), max_min=("duracao_min", "max")))
    print(pd.DataFrame(val).round(3).to_string())


if __name__ == "__main__":
    main()
