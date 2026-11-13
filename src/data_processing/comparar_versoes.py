"""Compara, evento a evento, os resultados v2 e v3.1 da dinâmica da irrigação.

Saídas em results/dinamica_irrigacao/v3_1/:
  comparacao_v2_v3_1.csv          um registro por evento presente nas duas versões
  comparacao_v2_v3_1_resumo.csv   medianas e tabelas de concordância

Uso: python src/data_processing/comparar_versoes.py
"""
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ / "results" / "dinamica_irrigacao"


def main():
    v2 = pd.read_csv(BASE / "v2" / "eventos_todos.csv", parse_dates=["inicio"])
    v31 = pd.read_csv(BASE / "v3_1" / "eventos_todos.csv", parse_dates=["inicio"])
    k = ["ano", "linha", "inicio"]
    c2 = v2[k + ["status", "qualidade", "M1_tau", "M1_theta", "t63", "atraso_5pct",
                 "classe_subida", "classe_recessao"]].add_suffix("_v2")
    c31 = v31[k + ["status", "amostra_principal", "amostra_principal_identificavel",
                   "D1_tau", "D1_theta", "t63", "atraso_5pct", "classe_degrau",
                   "classe_ar1", "classe_iid", "classe_neff", "M1qar_tau",
                   "M2par_theta", "M2par_tau_b", "classe_recessao_ar1"]].add_suffix("_v3_1")
    c2 = c2.rename(columns={f"{c}_v2": c for c in k})
    c31 = c31.rename(columns={f"{c}_v3_1": c for c in k})
    m = c2.merge(c31, on=k, how="outer", indicator=True)
    m["presenca"] = m["_merge"].map({"both": "ambas", "left_only": "so_v2", "right_only": "so_v3_1"})
    m = m.drop(columns="_merge")
    m["d_theta_degrau"] = m["D1_theta_v3_1"] - m["M1_theta_v2"]
    m["d_tau_degrau"] = m["D1_tau_v3_1"] - m["M1_tau_v2"]
    m["d_t63"] = m["t63_v3_1"] - m["t63_v2"]
    m.to_csv(BASE / "v3_1" / "comparacao_v2_v3_1.csv", index=False)

    amb = m[m.presenca.eq("ambas") & m.status_v2.eq("ajustado") & m.status_v3_1.eq("ajustado")]
    linhas = [dict(item="eventos em ambas (ajustados nas duas)", valor=len(amb)),
              dict(item="só v2", valor=int(m.presenca.eq("so_v2").sum())),
              dict(item="só v3.1", valor=int(m.presenca.eq("so_v3_1").sum()))]
    for c in ["M1_theta_v2", "D1_theta_v3_1", "M1_tau_v2", "D1_tau_v3_1", "t63_v2", "t63_v3_1",
              "atraso_5pct_v2", "atraso_5pct_v3_1", "d_theta_degrau", "d_tau_degrau", "d_t63"]:
        linhas.append(dict(item=f"mediana {c}", valor=amb[c].median()))
    for a, b in [("classe_subida_v2", "classe_degrau_v3_1"),
                 ("classe_subida_v2", "classe_ar1_v3_1"),
                 ("classe_recessao_v2", "classe_recessao_ar1_v3_1")]:
        tab = pd.crosstab(amb[a], amb[b])
        for (i, j), v in tab.stack().items():
            linhas.append(dict(item=f"{a} = {i} | {b} = {j}", valor=int(v)))
    r = pd.DataFrame(linhas)
    r.to_csv(BASE / "v3_1" / "comparacao_v2_v3_1_resumo.csv", index=False)
    print(r.to_string(index=False))


if __name__ == "__main__":
    main()
