"""Gera gráficos dos sensores e da estação a partir de um arquivo JSONL."""

import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FUSO = "America/Fortaleza"


def carregar_dados(caminho: Path) -> pd.DataFrame:
    """Lê um objeto JSON por linha e converte os timestamps Unix."""
    with caminho.open(encoding="utf-8") as arquivo:
        linhas = [json.loads(linha) for linha in arquivo if linha.strip()]

    dados = pd.json_normalize(linhas)
    for coluna in ("solo.ts", "chuva.ts", "estacao.ts"):
        dados[coluna] = pd.to_datetime(dados[coluna], unit="s", utc=True).dt.tz_convert(FUSO)
    return dados


def marcar_eventos(eixo, dia, eventos):
    """Adiciona linhas verticais nos horários informados."""
    for hora, descricao, cor in eventos:
        instante = pd.Timestamp(f"{dia} {hora}", tz=FUSO)
        eixo.axvline(instante, color=cor, linestyle="--", linewidth=1.4,
                     label=f"{descricao} ({hora[:5]})")


def calcular_limiar(dados, sensor):
    """Ordena por ADC e calcula a média na fronteira DO 1 → 0."""
    serie = dados.sort_values(f"{sensor}.adc", ascending=False).reset_index(drop=True)
    transicao = serie[f"{sensor}.do"].shift().eq(1) & serie[f"{sensor}.do"].eq(0)
    indice = np.flatnonzero(transicao)[0]
    return np.mean(serie[f"{sensor}.adc"].iloc[indice - 1:indice + 1])


def plotar_serie(dados, coluna_tempo, coluna_valor, titulo, eixo_y, cor,
                 caminho_saida, eventos=(), limiar=None):
    """Salva uma série temporal em PNG."""
    serie = dados.sort_values(coluna_tempo)
    fig, eixo = plt.subplots(figsize=(12, 5))
    eixo.plot(serie[coluna_tempo], serie[coluna_valor], color=cor,
              marker="o", markersize=3, linewidth=1.5, label=titulo)

    if eventos:
        dia = serie[coluna_tempo].iloc[0].date()
        marcar_eventos(eixo, dia, eventos)

    if limiar is not None:
        eixo.axhline(limiar, color="black", linestyle="--", linewidth=1.4,
                     label=f"Limiar: {limiar:g} ADC")

    if eventos or limiar is not None:
        eixo.legend(fontsize=8)

    eixo.set(title=titulo, xlabel="Horário em Fortaleza", ylabel=eixo_y)
    eixo.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=FUSO))
    eixo.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(caminho_saida, dpi=150)
    plt.close(fig)


def gerar_graficos(caminho_json: Path, pasta_saida: Path):
    """Gera os quatro gráficos a partir do arquivo indicado."""
    dados = carregar_dados(caminho_json)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    eventos_agua = (
        ("16:10", "Simulação de chuva", "#7451a8"),
        ("17:00", "Pouca água", "#e69f00"),
        ("17:10", "Água em excesso", "#d55e00"),
    )

    limiar_solo = calcular_limiar(dados, "solo")
    print(f"Limiar do solo: {limiar_solo:g} ADC")
    plotar_serie(dados, "solo.ts", "solo.adc", "Umidade do solo (ADC)",
                 "ADC", "#1f77b4", pasta_saida / "umidade_solo.png",
                 eventos_agua, limiar_solo)

    chuva = dados[["chuva.ts", "chuva.adc", "chuva.do"]]
    limiar_chuva = calcular_limiar(chuva, "chuva")
    print(f"Limiar da chuva: {limiar_chuva:g} ADC")
    eventos_chuva = eventos_agua + (("16:52", "Sensor seco", "#555555"),)
    plotar_serie(chuva, "chuva.ts", "chuva.adc", "Sensor de chuva (ADC)",
                 "ADC", "#008c95", pasta_saida / "chuva.png", eventos_chuva,
                 limiar_chuva)

    # A estação repete o mesmo registro nas linhas coletadas entre atualizações.
    estacao = dados.drop_duplicates(subset="estacao.ts")
    plotar_serie(estacao, "estacao.ts", "estacao.temp",
                 "Temperatura do ar em Fortaleza", "Temperatura (°C)",
                 "#e76f51", pasta_saida / "temperatura_fortaleza.png")
    plotar_serie(estacao, "estacao.ts", "estacao.ur",
                 "Umidade relativa do ar em Fortaleza", "Umidade relativa (%)",
                 "#3366cc", pasta_saida / "umidade_ar_fortaleza.png")


def main():
    raiz_projeto = Path(__file__).resolve().parents[2]
    caminho_json = raiz_projeto / "data" / "esp" / "dados.jsonl"
    pasta_saida = raiz_projeto / "imgs" / "esp"
    gerar_graficos(caminho_json, pasta_saida)


if __name__ == "__main__":
    main()
