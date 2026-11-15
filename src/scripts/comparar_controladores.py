"""Simula baseline/fuzzy no ARX congelado. Execute da raiz: .venv/bin/python -B src/scripts/comparar_controladores.py."""
import json
from comum import ROOT, RESULTADOS, CACHE

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as md
from arx import ARX, janelas
from controladores import baseline, fuzzy
from preparar_dinamica import preparar

SAIDA = RESULTADOS / "comparacao_controladores"
CORES = {"Baseline": "#793b99", "Fuzzy": "#13877f"}
MODELO = RESULTADOS / "arx/modelo_escolhido.json"
MEDIANAS = RESULTADOS / "arx_inicial/medianas_janelas_abertas.csv"


def simular(d, inicio, passos, modelo, controlador, doses):
    """Pulsos completos, sem sobreposição; decisão seguinte ao acabar o pulso.

    Umidades reais só inicializam os lags. Clima histórico igual para ambos.
    A dose de 30 min é distribuída uniformemente pelos três passos de 10 min.
    No fim do horizonte conta somente a parcela de água já aplicada.
    """
    h = d.humidity_soil.iloc[inicio - modelo.p:inicio + 1].tolist()
    u = d.delta_volume.iloc[inicio - modelo.q:inicio].tolist()
    estado = int(d.valve_state.iloc[inicio])
    restante, dose_passo = 0, 0.
    linhas = []
    for k in range(passos):
        row = d.iloc[inicio + k]
        tendencia = (h[-1] - h[-3]) / 20
        decisao = restante == 0
        comando = np.nan
        if decisao:
            comando = (baseline(h[-1], estado) if controlador == "Baseline"
                       else fuzzy(h[-1], tendencia))
            restante = comando
            dose_passo = doses[comando] / (comando / 10) if comando else 0.
        volume = dose_passo if restante else 0.
        abertura = estado == 0 and restante > 0
        estado = int(restante > 0)
        linhas.append(dict(ts_generation=row.ts_generation, umidade=h[-1],
                           dh_20min=tendencia, decisao=decisao,
                           comando_min=comando, restante_min=restante,
                           valvula=estado, acionamento=abertura, volume=volume))
        u.append(volume)
        h.append(modelo.passo(h, u, row.to_dict()))
        restante = max(0, restante - 10)
    linhas.append(dict(ts_generation=d.ts_generation.iloc[inicio + passos],
                       umidade=h[-1], acionamento=False, volume=0.))
    return pd.DataFrame(linhas)


def medidas(trajeto):
    h = trajeto.umidade.to_numpy()
    # Exclui a linha final da soma de ações e volume.
    return dict(volume=trajeto.volume.iloc[:-1].sum(),
                acionamentos_valvula=int(trajeto.acionamento.iloc[:-1].sum()),
                quedas_abaixo_24=int(((h[:-1] >= 24) & (h[1:] < 24)).sum()),
                leituras_abaixo_24=int((h[1:] < 24).sum()),
                inicio_abaixo_24=int(h[0] < 24),
                umidade_minima=h.min())


def salvar(fig, nome):
    fig.savefig(SAIDA / nome, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def grafico(d, exemplos, horizonte):
    fig, axs = plt.subplots(1, 2, figsize=(15, 5), sharey=True, layout="constrained")
    for ax, (inicio, curvas) in zip(axs, exemplos.items()):
        n = horizonte * 6
        datas = pd.to_datetime(d.ts_generation.iloc[inicio:inicio + n + 1], unit="ms", utc=True)
        for nome, curva in curvas.items():
            ax.plot(datas, curva.umidade.iloc[:n + 1], color=CORES[nome], lw=2.6,
                    ls="--" if nome == "Baseline" else "-", label=nome)
        for limite in [24, 27]:
            ax.axhline(limite, color="#89969c", ls=":", lw=1.3,
                       label=f"Limiar de {limite}%RH")
        ax.set(title=datas.iloc[0].strftime("%d/%m/%Y · início %H:%M UTC"),
               xlabel="Horário UTC", ylabel="Umidade do solo (%RH)")
        ax.xaxis.set_major_locator(md.HourLocator(interval=1 if horizonte == 2 else 2))
        ax.xaxis.set_major_formatter(md.DateFormatter("%H:%M"))
        ax.grid(alpha=.18)
    fig.suptitle(f"Baseline × fuzzy · umidade simulada por {horizonte} h",
                 fontsize=20,x=.055,y=1.14,ha="left")
    handles,labels=axs[0].get_legend_handles_labels()
    fig.legend(handles,labels,ncol=4,loc="upper left",bbox_to_anchor=(.055,1.065),
               frameon=False,borderaxespad=0,columnspacing=1.2)
    salvar(fig, f"umidade_{horizonte}h.png")


def tabela(resumo, n):
    fig, ax = plt.subplots(figsize=(18, 4.8))
    ax.axis("off")
    ax.set_title(f"Baseline × fuzzy · totais em {n} janelas sem sobreposição", fontsize=21, loc="left", pad=22)
    linhas = []
    for r in resumo.itertuples():
        economia = "—" if r.controlador == "Baseline" or pd.isna(r.economia_pct) else f"{r.economia_pct:.1f}%".replace(".",",")
        linhas.append([f"{r.horizonte_h} h", r.controlador, f"{r.volume:.1f}".replace(".",","),
                       economia, r.quedas_abaixo_24, r.leituras_abaixo_24, r.acionamentos_valvula])
    tab = ax.table(cellText=linhas, colLabels=["Janela", "Controlador", "Irrigação (m³)",
                   "Economia vs.\nbaseline", "Quedas de umidade\n≥24 → <24%RH", "Leituras <24%RH\napós o início", "Aberturas da válvula\nfechada → aberta"],
                   colWidths=[.07, .12, .14, .14, .18, .17, .18], bbox=[0, .02, 1, .93], cellLoc="center")
    tab.auto_set_font_size(False)
    tab.set_fontsize(14)
    for (i, j), c in tab.get_celld().items():
        c.set_edgecolor("white")
        c.set_facecolor("#193b4d" if i == 0 else "#e8eff2" if i % 2 else "#f5f7f8")
        if i == 0:
            c.set_text_props(color="white", weight="bold")
    salvar(fig, "tabela_comparacao.png")


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 13, "axes.spines.top": False, "axes.spines.right": False})
    dinamica = preparar()
    modelo = ARX.carregar(MODELO)
    med = pd.read_csv(MEDIANAS).set_index("janela_min").mediana
    doses = {0: 0., 10: float(med.loc[10]), 30: float(med.loc[30])}
    d = pd.read_csv(CACHE / "dataset_chuva.csv")
    stamp = lambda s: pd.Timestamp(s, tz="UTC").value // 1_000_000
    d = d[d.ts_generation.between(stamp("2024-08-01"), stamp("2024-09-04") - 1)].reset_index(drop=True)
    elegiveis = janelas(d, 36, stamp("2024-08-19"), stamp("2024-09-04"))
    timestamps_dinamica = set(dinamica.ts_generation)
    elegiveis = [i for i in elegiveis if d.ts_generation.iloc[i] in timestamps_dinamica
                 and np.isfinite(d.valve_state.iloc[i])]
    # Seleciona janelas cronológicas sem sobreposição.
    inicios = []
    for i in elegiveis:
        if not inicios or d.ts_generation.iloc[i] >= d.ts_generation.iloc[inicios[-1] + 36]:
            inicios.append(i)
    registros = []
    for i in inicios:
        for nome in CORES:
            curva = simular(d, i, 36, modelo, nome, doses)
            for horizonte in [2, 6]:
                registros.append(dict(inicio=d.ts_generation.iloc[i], horizonte_h=horizonte,
                                      controlador=nome, **medidas(curva.iloc[:horizonte * 6 + 1])))
    metricas = pd.DataFrame(registros)
    resumo = metricas.groupby(["horizonte_h", "controlador"], as_index=False)[
        ["volume", "acionamentos_valvula", "quedas_abaixo_24", "leituras_abaixo_24", "inicio_abaixo_24"]].sum()
    agua_base = resumo[resumo.controlador.eq("Baseline")].set_index("horizonte_h").volume
    referencia = resumo.horizonte_h.map(agua_base).replace(0, np.nan)
    resumo["economia_pct"] = 100 * (referencia - resumo.volume) / referencia
    # metricas.to_csv(SAIDA / "metricas_por_janela.csv", index=False)
    # resumo.to_csv(SAIDA / "resumo.csv", index=False)
    # pd.concat(trajetorias, ignore_index=True).to_csv(SAIDA / "trajetorias.csv", index=False)
    # Seleciona o início da irrigação nos dias 20 e 28/08.
    eventos = [i for i in elegiveis if d.delta_volume.iloc[i] > 0 and d.delta_volume.iloc[i - 1] == 0]
    exemplos = {}
    for dia in ["2024-08-20", "2024-08-28"]:
        i = next(i for i in eventos if pd.to_datetime(d.ts_generation.iloc[i], unit="ms", utc=True).strftime("%Y-%m-%d") == dia)
        exemplos[i] = {nome: simular(d, i, 36, modelo, nome, doses) for nome in CORES}
    # pd.concat([c.assign(inicio=d.ts_generation.iloc[i], controlador=nome)
    #            for i, curvas in exemplos.items() for nome, c in curvas.items()], ignore_index=True
    #           ).to_csv(SAIDA / "trajetorias_figuras.csv", index=False)
    for horizonte in [2, 6]:
        grafico(d, exemplos, horizonte)
    tabela(resumo, len(inicios))
    (SAIDA / "configuracao.json").write_text(json.dumps(dict(
        modelo=modelo.__dict__, doses=doses, janela_passo_min=10,
        n_janelas=len(inicios), periodo=["2024-08-19", "2024-09-04 (exclusivo)"],
        inicios_ts=[int(d.ts_generation.iloc[i]) for i in inicios],
        fonte_mediana=str(MEDIANAS.relative_to(ROOT)),
        regra_excesso_queda="desligado",
        regra_transicao_estavel="desligado",
        regra_transicao_queda="desligado",
        acionamento="Pulsos completos; centroide fuzzy arredondado para 0/10/30 min"),
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nArtefatos: {SAIDA}")


if __name__ == "__main__":
    main()
