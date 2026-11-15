"""Investiga o volume acumulado da linha 3 de 2024. Grava em resultados_simulador, na raiz do projeto."""

import numpy as np
import pandas as pd
from comum import ROOT, RESULTADOS, saida_local
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ANO, LINHA = "2024", 3
LIMITE_S = 20 * 60


def carregar(arquivo, valor, dispositivo):
    df = pd.read_csv(
        ROOT / f"data/raw/{ANO}/{arquivo}{ANO}.csv",
        usecols=["line", "ts_generation", dispositivo, valor],
    )
    df = df.loc[df.line.eq(LINHA)].copy()
    if df[dispositivo].nunique() != 1:
        raise ValueError(f"Esperado um dispositivo na linha {LINHA}: {arquivo}")
    df[valor] = pd.to_numeric(df[valor], errors="coerce")
    df = df.dropna(subset=["ts_generation", valor])
    validos = df[valor].isin([0, 1]) if valor == "valve_state" else df[valor].ge(0)
    df = df.loc[validos]
    if df.groupby("ts_generation")[valor].nunique().gt(1).any():
        raise ValueError(f"Leituras conflitantes no mesmo horário: {arquivo}")
    df = df.drop_duplicates("ts_generation").sort_values("ts_generation")
    df["timestamp"] = pd.to_datetime(df.ts_generation, unit="ms", utc=True)
    return df.reset_index(drop=True)


def associar(medidor, valvula):
    intervalos = medidor.copy()
    intervalos["inicio"] = medidor.timestamp.shift()
    intervalos["delta_volume"] = medidor.current_volume.diff()
    intervalos["duracao_s"] = medidor.ts_generation.diff() / 1000
    intervalos["utilizavel"] = intervalos.duracao_s.between(
        0, LIMITE_S, inclusive="right"
    ) & intervalos.delta_volume.ge(0)
    inicios = valvula.ts_generation.to_numpy() / 1000
    fins = np.minimum(np.r_[inicios[1:], np.inf], inicios + LIMITE_S)
    estados = valvula.valve_state.to_numpy()
    classes = []
    for row in intervalos.itertuples():
        if pd.isna(row.inicio):
            classes.append("sem_intervalo")
            continue
        a, b = row.inicio.timestamp(), row.timestamp.timestamp()
        lo = np.searchsorted(fins, a, side="right")
        hi = np.searchsorted(inicios, b, side="left")
        sobreposicao = np.maximum(
            0, np.minimum(fins[lo:hi], b) - np.maximum(inicios[lo:hi], a)
        )
        aberta = sobreposicao[estados[lo:hi] == 1].sum()
        fechada = sobreposicao[estados[lo:hi] == 0].sum()
        if row.duracao_s - aberta - fechada > 0.001:
            classe = "cobertura_incompleta"
        elif aberta > 0 and fechada > 0:
            classe = "misto"
        else:
            classe = "aberta" if aberta > 0 else "fechada"
        classes.append(classe)
    intervalos["classe_valvula"] = classes
    return intervalos


def graficos(intervalos, valvula, out):
    fig, ax = plt.subplots(figsize=(10, 4), layout="constrained")
    ax.plot(intervalos.timestamp, intervalos.current_volume, color="#245b8a")
    ax.set(
        title="Linha 3 · 2024 — o contador acumula o volume ao longo do tempo",
        xlabel="Data (UTC)",
        ylabel="Contador (m³)",
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    fig.savefig(out / "01_volume_acumulado.png", dpi=160)
    plt.close(fig)

    candidatos = intervalos.loc[
        intervalos.utilizavel
        & intervalos.delta_volume.gt(0)
        & intervalos.classe_valvula.ne("cobertura_incompleta")
    ]
    if candidatos.empty:
        return
    pico = candidatos.loc[candidatos.delta_volume.idxmax()]
    inicio = pico.inicio.to_pydatetime() - pd.Timedelta(hours=1).to_pytimedelta()
    fim = pico.timestamp.to_pydatetime() + pd.Timedelta(hours=1).to_pytimedelta()
    janela = intervalos.loc[intervalos.timestamp.between(inicio, fim)]
    estados = valvula.loc[valvula.timestamp.between(inicio, fim)]
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True, layout="constrained")
    for row in janela.itertuples():
        if pd.notna(row.inicio) and row.delta_volume >= 0:
            axes[0].hlines(
                row.delta_volume,
                row.inicio,
                row.timestamp,
                color="#245b8a",
                linewidth=3,
            )
    axes[0].set(
        title="Linha 3 · 2024 — volume e válvula perto do maior incremento observado",
        ylabel="Aumento do contador (m³)",
    )
    axes[1].scatter(estados.timestamp, estados.valve_state, color="#e69826", s=25)
    axes[1].set(
        yticks=[0, 1],
        yticklabels=["Fechada", "Aberta"],
        ylim=(-0.2, 1.2),
        xlabel="Horário UTC — pontos representam leituras da válvula",
    )
    for ax in axes:
        ax.grid(alpha=0.2)
        ax.set_xlim(inicio, fim)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
    fig.savefig(out / "03_janela_linha_3.png", dpi=160)
    plt.close(fig)


def main():
    medidor = carregar("water_meter", "current_volume", "device_identifier")
    valvula = carregar("valve_controller", "valve_state", "generated_by")
    intervalos = associar(medidor, valvula)
    utilizaveis = intervalos.loc[intervalos.utilizavel].copy()
    utilizaveis["incremento_positivo"] = utilizaveis.delta_volume.gt(0)
    resumo = utilizaveis.groupby(["line", "classe_valvula"]).agg(
        intervalos=("delta_volume", "size"),
        incrementos_positivos=("incremento_positivo", "sum"),
        soma_deltas=("delta_volume", "sum"),
        duracao_s=("duracao_s", "sum"),
    )
    out = saida_local(RESULTADOS / "volume_agua")
    # resumo.to_csv(out / "resumo_por_estado.csv")
    graficos(intervalos, valvula, out)
    comportamento = (
        "O contador só aumenta ou permanece parado: ele se comporta como um total acumulado."
        if intervalos.delta_volume.dropna().ge(0).all()
        else "Há quedas no contador; esses trechos precisam ser investigados antes de calcular consumo."
    )
    texto = f"""# Volume de água — linha 3, 2024

{comportamento} Para saber quanto passou entre duas leituras, subtraia a anterior da seguinte. Somar as leituras do contador contaria a mesma água várias vezes.

No gráfico do período inteiro, procure os degraus: são os momentos em que o contador aumentou. O outro gráfico aproxima o maior incremento com cobertura da válvula, para comparar o aumento de volume com as leituras de abertura e fechamento. É um exemplo escolhido pelo volume, não um evento típico.

Neste recorte, quase todo o aumento do contador está nos intervalos com válvula aberta ou nos mistos. Nos mistos, houve mudança de estado durante o intervalo, então não dá para atribuir todo aquele volume a um único estado. A pequena parcela de aumento com válvula fechada merece conferência, mas sozinha não prova vazamento. Onde falta cobertura, não se presume que a válvula estava fechada.

A análise descarta intervalos do medidor acima de 20 minutos e só prolonga cada estado observado da válvula por até 20 minutos. São hipóteses de leitura dos dados; não revelam o instante exato de acionamento. O volume está em m³, conforme data/raw/2024/README.md.
"""
    (out / "interpretacao.md").write_text(texto, encoding="utf-8")
    print("Resultados da linha 3 de 2024:", out)


if __name__ == "__main__":
    main()
