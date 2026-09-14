"""Visualização e preparação da hipótese H1.

H1: menores níveis de umidade do solo estão associados a uma maior
necessidade de irrigação.
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


_OUTPUT_PATH = (
    Path(__file__).resolve().parents[2]
    / "imgs"
    / "H1"
    / "Menores_niveis_de_umidade_do_solo_associados_a_maior_necessidade_de_irrigacao.png"
)


def extrair_eventos_irrigacao(df: pd.DataFrame) -> pd.DataFrame:
    """Extrai eventos 0→1 e o volume acumulado durante cada irrigação.

    A umidade do evento é a observação imediatamente anterior à abertura.
    O volume é a diferença entre a última leitura válida após o início e a
    última leitura válida antes dele. Eventos sem fechamento, leituras de
    volume ausentes ou com reset do medidor são descartados.
    """
    required = {"timestamp_10min", "valve_state", "soil_humidity", "water_volume"}
    missing = required.difference(df.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"DataFrame sem coluna(s) obrigatória(s): {names}")

    data = df.copy()
    data["timestamp_10min"] = pd.to_datetime(
        data["timestamp_10min"], errors="coerce", utc=True
    )
    for column in ("valve_state", "soil_humidity", "water_volume"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["timestamp_10min"]).sort_values("timestamp_10min")
    data = data.reset_index(drop=True)

    openings = data.index[
        data["valve_state"].eq(1) & data["valve_state"].shift(1).eq(0)
    ].tolist()
    events = []
    for event_number, opening in enumerate(openings, start=1):
        closing_candidates = data.index[
            (data.index > opening) & data["valve_state"].eq(0)
        ]
        if len(closing_candidates) == 0:
            continue
        closing = int(closing_candidates[0])
        before_volume = data.loc[: opening - 1, "water_volume"].dropna()
        during_volume = data.loc[opening:closing, "water_volume"].dropna()
        if before_volume.empty or during_volume.empty:
            continue
        volume = float(during_volume.iloc[-1] - before_volume.iloc[-1])
        if volume < 0:
            continue
        row = data.loc[opening - 1]
        events.append(
            {
                "evento": event_number,
                "timestamp_abertura": data.loc[opening, "timestamp_10min"],
                "timestamp_pre_abertura": row["timestamp_10min"],
                "soil_humidity_pre_abertura": row["soil_humidity"],
                "soil_humidity_abertura": data.loc[opening, "soil_humidity"],
                "water_volume_antes": float(before_volume.iloc[-1]),
                "water_volume_depois": float(during_volume.iloc[-1]),
                "volume_evento": volume,
            }
        )
    return pd.DataFrame(events)


def plot_eventos_irrigacao(eventos: pd.DataFrame) -> Path:
    """Gera o scatter de umidade antes da abertura e volume do evento."""
    required = {"soil_humidity_pre_abertura", "volume_evento"}
    missing = required.difference(eventos.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"DataFrame sem coluna(s) obrigatória(s): {names}")
    data = eventos.dropna(subset=list(required)).copy()
    if data.empty:
        raise ValueError("Não há eventos válidos para plotar")

    root = Path(__file__).resolve().parents[2] / "imgs" / "H1"
    root.mkdir(parents=True, exist_ok=True)
    scatter_path = root / "H1_eventos_umidade_pre_abertura_vs_volume.png"

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        data["soil_humidity_pre_abertura"], data["volume_evento"],
        color="#2171b5", edgecolors="#08306b", linewidths=0.4, alpha=0.8,
    )
    ax.set_xlabel("Umidade do solo antes da abertura (%RH)")
    ax.set_ylabel("Volume de água no evento (m³)")
    ax.grid(color="#c6dbef", alpha=0.45)
    fig.tight_layout()
    fig.savefig(scatter_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return scatter_path


def plot_proporcao_acionamento(df: pd.DataFrame) -> tuple[Path, pd.DataFrame]:
    """Plota a proporção de transições 0→1 por faixa de umidade.

    Cada denominador é uma amostra com válvula fechada e próximo estado
    conhecido; o sucesso ocorre quando o próximo estado é 1.
    """
    required = {"timestamp_10min", "valve_state", "soil_humidity"}
    missing = required.difference(df.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"DataFrame sem coluna(s) obrigatória(s): {names}")
    data = df.copy()
    data["timestamp_10min"] = pd.to_datetime(data["timestamp_10min"], errors="coerce", utc=True)
    data["valve_state"] = pd.to_numeric(data["valve_state"], errors="coerce")
    data["soil_humidity"] = pd.to_numeric(data["soil_humidity"], errors="coerce")
    data = data.dropna(subset=["timestamp_10min"]).sort_values("timestamp_10min").reset_index(drop=True)
    data["proxima_abertura"] = data["valve_state"].shift(-1).eq(1)
    candidatos = data.loc[
        data["valve_state"].eq(0) & data["valve_state"].shift(-1).isin([0, 1])
    ].dropna(subset=["soil_humidity"]).copy()
    candidatos["faixa_umidade"] = pd.qcut(
        candidatos["soil_humidity"], q=3, duplicates="drop"
    )
    tabela = candidatos.groupby("faixa_umidade", observed=True).agg(
        faixa_min=("soil_humidity", "min"),
        faixa_max=("soil_humidity", "max"),
        total=("proxima_abertura", "size"),
        aberturas=("proxima_abertura", "sum"),
        proporcao=("proxima_abertura", "mean"),
    ).reset_index(drop=True)
    tabela.insert(
        0,
        "faixa_umidade",
        tabela.apply(
            lambda row: f"{row['faixa_min']:.2f}–{row['faixa_max']:.2f}", axis=1
        ),
    )
    tabela = tabela.drop(columns=["faixa_min", "faixa_max"])
    root = Path(__file__).resolve().parents[2] / "imgs" / "H1"
    root.mkdir(parents=True, exist_ok=True)
    output = root / "H1_proporcao_acionamento_por_faixa_de_umidade.png"
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.bar(tabela["faixa_umidade"].astype(str), tabela["proporcao"] * 100, color="#6baed6")
    ax.set_xlabel("Faixa de umidade antes do instante (%RH)")
    ax.set_ylabel("Proporção de acionamento da válvula (%)")
    ax.set_ylim(0, max(1, float((tabela["proporcao"].max() * 100) * 1.2)))
    ax.grid(axis="y", color="#c6dbef", alpha=0.45)
    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    tabela["proporcao"] = tabela["proporcao"] * 100
    return output, tabela

def plot_volume_valvula(df: pd.DataFrame) -> Path:
    """Gera scatter do volume bruto, colorido pelo estado da válvula."""
    required = {"timestamp_10min", "water_volume", "valve_state"}
    missing = required.difference(df.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"DataFrame sem coluna(s) obrigatória(s): {names}")

    data = df.copy()
    data["timestamp_10min"] = pd.to_datetime(
        data["timestamp_10min"], errors="coerce", utc=True
    )
    data["water_volume"] = pd.to_numeric(data["water_volume"], errors="coerce")
    data["valve_state"] = pd.to_numeric(data["valve_state"], errors="coerce")
    data = data.dropna(subset=["timestamp_10min", "water_volume"])
    aberta = data["valve_state"].eq(1)

    root = Path(__file__).resolve().parents[2]
    line_label = str(data["line"].dropna().iloc[0]) if "line" in data and data["line"].notna().any() else "todas"
    season_label = str(data["safra"].dropna().iloc[0]) if "safra" in data and data["safra"].notna().any() else "sem_safra"
    output_path = (
        root / "imgs" / "H1"
        / f"Water_volume_linha_{line_label}_{season_label}_por_estado_da_valvula.png"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(16, 6))
    ax.scatter(
        data.loc[~aberta, "timestamp_10min"], data.loc[~aberta, "water_volume"],
        color="#2171b5", s=10, alpha=0.55, label="Válvula fechada",
    )
    ax.scatter(
        data.loc[aberta, "timestamp_10min"], data.loc[aberta, "water_volume"],
        color="#d73027", s=28, alpha=0.9, label="Válvula aberta",
    )
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Volume de água")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#c6dbef", alpha=0.45)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def defasar_umidade(df: pd.DataFrame, janelas: int) -> pd.DataFrame:
    """Adiciona ao DataFrame a umidade observada ``janelas`` períodos antes.

    Os períodos são as janelas de 10 minutos de ``timestamp_10min``. A
    defasagem é calculada separadamente por linha (e por safra, quando a
    coluna existir), evitando que uma observação de outra linha seja usada
    como antecedente.
    """
    required = {"timestamp_10min", "soil_humidity"}
    missing = required.difference(df.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"DataFrame sem coluna(s) obrigatória(s): {names}")
    if not isinstance(janelas, int) or isinstance(janelas, bool) or janelas < 1:
        raise ValueError("janelas deve ser um inteiro positivo")

    data = df.copy()
    data["timestamp_10min"] = pd.to_datetime(
        data["timestamp_10min"], errors="coerce", utc=True
    )
    data["soil_humidity"] = pd.to_numeric(data["soil_humidity"], errors="coerce")

    group_columns = ["line"] if "line" in data.columns else []
    if "safra" in data.columns:
        group_columns.insert(0, "safra")
    data = data.sort_values(group_columns + ["timestamp_10min"]).copy()

    lag_column = f"soil_humidity_lag_{janelas}"
    if group_columns:
        data[lag_column] = data.groupby(group_columns, dropna=False)[
            "soil_humidity"
        ].shift(janelas)
    else:
        data[lag_column] = data["soil_humidity"].shift(janelas)

    return data.sort_values("timestamp_10min").reset_index(drop=True)


def plot_umidade_irrigacao(df: pd.DataFrame) -> Path:
    """Gera a série temporal de umidade e volume de irrigação.

    A função recebe somente um ``DataFrame``. Os registros são ordenados por
    ``timestamp_10min`` e agregados por instante: umidade média das linhas e
    volume total irrigado no intervalo. ``water_volume`` é um medidor
    acumulado; por isso, o gráfico usa sua diferença entre leituras
    consecutivas por linha (mantendo a última leitura válida nos timestamps
    ausentes), em vez de somar a leitura acumulada.

    Retorna o caminho da figura PNG salva em ``imgs/H1``.
    """
    required = {"timestamp_10min", "soil_humidity", "water_volume"}
    missing = required.difference(df.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"DataFrame sem coluna(s) obrigatória(s): {names}")

    data = df.copy()
    data["timestamp_10min"] = pd.to_datetime(
        data["timestamp_10min"], errors="coerce", utc=True
    )
    data["soil_humidity"] = pd.to_numeric(data["soil_humidity"], errors="coerce")
    data["water_volume"] = pd.to_numeric(data["water_volume"], errors="coerce")
    data = data.dropna(subset=["timestamp_10min"])

    # A leitura atual do medidor é acumulada. Calculamos o volume entre
    # leituras, preservando a linha (e a safra, se ela estiver no DataFrame).
    group_columns = ["line"] if "line" in data.columns else []
    if "safra" in data.columns:
        group_columns.insert(0, "safra")
    data = data.sort_values(group_columns + ["timestamp_10min"])
    if group_columns:
        data["_water_volume_filled"] = data.groupby(group_columns, dropna=False)[
            "water_volume"
        ].ffill()
        data["irrigation_volume"] = data.groupby(group_columns, dropna=False)[
            "_water_volume_filled"
        ].diff()
    else:
        data["_water_volume_filled"] = data["water_volume"].ffill()
        data["irrigation_volume"] = data["_water_volume_filled"].diff()
    data["irrigation_volume"] = data["irrigation_volume"].clip(lower=0).fillna(0)

    series = (
        data.groupby("timestamp_10min", as_index=False)
        .agg(
            soil_humidity=("soil_humidity", "mean"),
            irrigation_volume=("irrigation_volume", "sum"),
        )
        .sort_values("timestamp_10min")
    )
    # A resolução de 10 minutos gera dezenas de milhares de barras quando as
    # safras são analisadas juntas. Mantemos a série agregada, mas desenhamos
    # a figura em janelas horárias para que ela permaneça legível e leve.
    series_plot = (
        series.set_index("timestamp_10min")
        .resample("1h")
        .agg({"soil_humidity": "mean", "irrigation_volume": "sum"})
        .reset_index()
    )

    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig, ax_humidity = plt.subplots(figsize=(16, 6))
    ax_volume = ax_humidity.twinx()

    ax_humidity.bar(
        series_plot["timestamp_10min"],
        series_plot["soil_humidity"],
        width=0.035,
        color="#6baed6",
        alpha=0.72,
        label="Umidade do solo (média)",
    )
    ax_volume.plot(
        series_plot["timestamp_10min"],
        series_plot["irrigation_volume"],
        color="#08519c",
        linestyle="--",
        linewidth=1.5,
        label="Volume de irrigação por intervalo",
    )

    ax_humidity.set_xlabel("Timestamp")
    ax_humidity.set_ylabel("Umidade do solo", color="#2171b5")
    ax_volume.set_ylabel("Volume de água", color="#08519c")
    ax_humidity.tick_params(axis="y", labelcolor="#2171b5")
    ax_volume.tick_params(axis="y", labelcolor="#08519c")
    ax_humidity.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax_humidity.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax_humidity.xaxis.get_major_locator()))
    ax_humidity.grid(axis="y", color="#c6dbef", alpha=0.45)

    handles_left, labels_left = ax_humidity.get_legend_handles_labels()
    handles_right, labels_right = ax_volume.get_legend_handles_labels()
    ax_humidity.legend(
        handles_left + handles_right,
        labels_left + labels_right,
        loc="upper left",
        frameon=False,
    )
    fig.tight_layout()
    fig.savefig(_OUTPUT_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return _OUTPUT_PATH
