"""Séries temporais das variáveis de solo por linha e dispositivo.
data: ``data/raw/2024/soil2024.csv`` 
figuras individuais: ``imgs/solo2024``
figuras com os dois dispositivos da mesma linha:``imgs/solo2024-dois-dispositivos``. 
figuras das variáveis do solo com os acionamentos da válvula:``imgs/solo2024-umidade-valvula``.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
import pandas as pd


ANO_PADRAO = 2024
RAIZ_PROJETO = Path(__file__).resolve().parents[2]
ENTRADA_PADRAO = RAIZ_PROJETO / "data" / "raw" / "2024" / "soil2024.csv"
ENTRADA_VALVULA_PADRAO = (
    RAIZ_PROJETO / "data" / "raw" / "2024" / "valve_controller2024.csv"
)
SAIDA_PADRAO = RAIZ_PROJETO / "imgs" / "solo2024"
SAIDA_COMBINADA_PADRAO = RAIZ_PROJETO / "imgs" / "solo2024-dois-dispositivos"
SAIDA_VALVULA_PADRAO = RAIZ_PROJETO / "imgs" / "solo2024-umidade-valvula"
SAIDA_EVENTOS_PADRAO = RAIZ_PROJETO / "imgs" / "solo2024-eventos-linha1"

VARIAVEIS = {
    "electrical_conductivity": {
        "nome": "Condutividade elétrica do solo",
        "unidade": "µS/cm",
        "arquivo": "condutividade-eletrica-do-solo",
    },
    "humidity": {
        "nome": "Umidade do solo",
        "unidade": "%RH",
        "arquivo": "umidade-do-solo",
    },
    "temperature": {
        "nome": "Temperatura do solo",
        "unidade": "°C",
        "arquivo": "temperatura-do-solo",
    },
}

COLUNAS_OBRIGATORIAS = {
    "ts_generation",
    "generated_by",
    "line",
    *VARIAVEIS,
}

CORES = {
    "texto": "#222222",
    "fundo": "white",
    "sem_borda": "none",
    "dispositivo_fallback": "#0D0D0D",
    "dispositivo_evento_1": "#434242",
    "dispositivo_evento_2": "#c72396",
    "referencia_umidade": "black",
    "valvula": "#355140",
    "hotbar_temperatura": [
        "#fff7bc",
        "#fec44f",
        "#fe9929",
        "#d95f0e",
        "#7f0000",
    ],
    "hotbar_umidade": [
        "#c6dbef",
        "#6baed6",
        "#9e9ac8",
        "#756bb1",
        "#542788",
    ],
}


def argumentos() -> argparse.Namespace:
    """Lê os parâmetros da linha de comando."""
    parser = argparse.ArgumentParser(
        description=(
            "Gera plots de dispersão com linhas das variáveis de solo "
            "separados por linha e dispositivo."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ENTRADA_PADRAO,
        help=f"CSV de entrada (padrão: {ENTRADA_PADRAO})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SAIDA_PADRAO,
        help=f"Diretório das imagens (padrão: {SAIDA_PADRAO})",
    )
    parser.add_argument(
        "--ano",
        type=int,
        default=ANO_PADRAO,
        help=f"Ano a plotar (padrão: {ANO_PADRAO})",
    )
    parser.add_argument(
        "--timezone",
        default="UTC",
        help="Fuso para exibir e filtrar o timestamp (padrão: UTC)",
    )
    parser.add_argument(
        "--output-combinado",
        type=Path,
        default=SAIDA_COMBINADA_PADRAO,
        help=(
            "Diretório das figuras com dois dispositivos "
            f"(padrão: {SAIDA_COMBINADA_PADRAO})"
        ),
    )
    parser.add_argument(
        "--input-valvula",
        type=Path,
        default=ENTRADA_VALVULA_PADRAO,
        help=f"CSV de válvulas (padrão: {ENTRADA_VALVULA_PADRAO})",
    )
    parser.add_argument(
        "--input-ambiental",
        type=Path,
        default=None,
        help=(
            "CSV ambiental usado pela hotbar; por padrão, usa "
            "data/raw/<ano>/environmental<ano>.csv."
        ),
    )
    parser.add_argument(
        "--output-valvula",
        type=Path,
        default=SAIDA_VALVULA_PADRAO,
        help=(
            "Diretório das figuras de umidade com acionamentos da válvula "
            f"(padrão: {SAIDA_VALVULA_PADRAO})"
        ),
    )
    parser.add_argument(
        "--somente-combinados",
        action="store_true",
        help="Gera somente as figuras com os dois dispositivos.",
    )
    parser.add_argument(
        "--somente-umidade-valvula",
        action="store_true",
        help="Gera somente as figuras com acionamentos da válvula.",
    )
    parser.add_argument(
        "--linha-eventos",
        type=int,
        default=1,
        help="Linha usada na análise de eventos (padrão: 1).",
    )
    parser.add_argument(
        "--output-eventos",
        type=Path,
        default=SAIDA_EVENTOS_PADRAO,
        help=f"Diretório da análise de eventos (padrão: {SAIDA_EVENTOS_PADRAO})",
    )
    parser.add_argument(
        "--somente-eventos",
        action="store_true",
        help="Gera somente os plots dos eventos válidos da válvula.",
    )
    return parser.parse_args()


def slug(texto: str) -> str:
    """Mantém nomes de arquivos legíveis, sem acentos nem sublinhados."""
    texto = (
        texto.replace("á", "a")
        .replace("à", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    texto = texto.lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")


def carregar_dados(caminho: Path, ano: int, timezone: str) -> pd.DataFrame:
    """Carrega, valida, converte e filtra os dados do ano solicitado."""
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {caminho}")

    dados = pd.read_csv(caminho, low_memory=False)
    faltantes = sorted(COLUNAS_OBRIGATORIAS - set(dados.columns))
    if faltantes:
        raise ValueError(
            "O CSV não contém as colunas obrigatórias: " + ", ".join(faltantes)
        )

    dados["timestamp"] = pd.to_datetime(
        pd.to_numeric(dados["ts_generation"], errors="coerce"),
        unit="ms",
        errors="coerce",
        utc=True,
    )
    try:
        dados["timestamp"] = dados["timestamp"].dt.tz_convert(timezone)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Fuso horário inválido: {timezone}") from exc

    dados["linha"] = pd.to_numeric(dados["line"], errors="coerce")
    dados["dispositivo"] = dados["generated_by"].astype("string").str.strip()

    for variavel in VARIAVEIS:
        dados[variavel] = pd.to_numeric(dados[variavel], errors="coerce")

    dados = dados.loc[
        dados["timestamp"].dt.year.eq(ano)
        & dados["linha"].notna()
        & dados["dispositivo"].notna()
    ].copy()
    dados["linha"] = dados["linha"].astype(int)
    return dados.sort_values(["linha", "dispositivo", "timestamp"])


def carregar_dados_ambientais(
    caminho: Path,
    ano: int,
    timezone: str,
) -> pd.DataFrame:
    """Carrega a temperatura do ar do CSV ambiental do ano escolhido."""
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo ambiental não encontrado: {caminho}")

    dados = pd.read_csv(caminho, low_memory=False)
    colunas_obrigatorias = {"ts_generation", "temperature", "humidity"}
    faltantes = sorted(colunas_obrigatorias - set(dados.columns))
    if faltantes:
        raise ValueError(
            "O CSV ambiental não contém as colunas obrigatórias: "
            + ", ".join(faltantes)
        )

    dados["timestamp"] = pd.to_datetime(
        pd.to_numeric(dados["ts_generation"], errors="coerce"),
        unit="ms",
        errors="coerce",
        utc=True,
    )
    try:
        dados["timestamp"] = dados["timestamp"].dt.tz_convert(timezone)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Fuso horário inválido: {timezone}") from exc

    dados["temperature"] = pd.to_numeric(dados["temperature"], errors="coerce")
    dados["humidity"] = pd.to_numeric(dados["humidity"], errors="coerce")
    dados = dados.loc[
        dados["timestamp"].dt.year.eq(ano)
        & dados["timestamp"].notna(),
        ["timestamp", "temperature", "humidity"],
    ].sort_values("timestamp")
    if dados.empty or dados["temperature"].notna().sum() == 0:
        raise ValueError(f"Não há temperaturas ambientais válidas para {ano}.")
    if dados["humidity"].notna().sum() == 0:
        raise ValueError(f"Não há umidade ambiental válida para {ano}.")
    return dados.reset_index(drop=True)


def carregar_acionamentos_valvula(
    caminho: Path,
    ano: int,
    timezone: str,
) -> pd.DataFrame:
    """Carrega os registros em que o estado da válvula é exatamente 1.0."""
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo de válvulas não encontrado: {caminho}")

    dados = pd.read_csv(caminho, low_memory=False)
    colunas_obrigatorias = {"ts_generation", "line", "valve_state"}
    faltantes = sorted(colunas_obrigatorias - set(dados.columns))
    if faltantes:
        raise ValueError(
            "O CSV de válvulas não contém as colunas obrigatórias: "
            + ", ".join(faltantes)
        )

    dados["timestamp"] = pd.to_datetime(
        pd.to_numeric(dados["ts_generation"], errors="coerce"),
        unit="ms",
        errors="coerce",
        utc=True,
    )
    try:
        dados["timestamp"] = dados["timestamp"].dt.tz_convert(timezone)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Fuso horário inválido: {timezone}") from exc

    dados["linha"] = pd.to_numeric(dados["line"], errors="coerce")
    dados["estado"] = pd.to_numeric(dados["valve_state"], errors="coerce")
    dados = dados.loc[
        dados["timestamp"].dt.year.eq(ano)
        & dados["linha"].notna()
        & dados["estado"].notna()
    ].copy()
    dados["linha"] = dados["linha"].astype(int)
    dados = dados.sort_values(["linha", "timestamp"])
    return dados.loc[dados["estado"].eq(1), ["linha", "timestamp"]].reset_index(
        drop=True
    )


def carregar_eventos_valvula(
    caminho: Path,
    ano: int,
    timezone: str,
    linha: int,
) -> pd.DataFrame:
    """Identifica eventos 0 → 1 → ... → 1 → 0 pela linha e pelos timestamps."""
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo de válvulas não encontrado: {caminho}")

    dados = pd.read_csv(caminho, low_memory=False)
    colunas_obrigatorias = {"ts_generation", "line", "valve_state"}
    faltantes = sorted(colunas_obrigatorias - set(dados.columns))
    if faltantes:
        raise ValueError(
            "O CSV de válvulas não contém as colunas obrigatórias: "
            + ", ".join(faltantes)
        )

    dados["timestamp"] = pd.to_datetime(
        pd.to_numeric(dados["ts_generation"], errors="coerce"),
        unit="ms",
        errors="coerce",
        utc=True,
    )
    try:
        dados["timestamp"] = dados["timestamp"].dt.tz_convert(timezone)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Fuso horário inválido: {timezone}") from exc

    dados["linha"] = pd.to_numeric(dados["line"], errors="coerce")
    dados["estado"] = pd.to_numeric(dados["valve_state"], errors="coerce")
    dados = dados.loc[
        dados["timestamp"].dt.year.eq(ano)
        & dados["linha"].eq(linha)
        & dados["estado"].isin([0, 1])
    ].copy()
    dados = dados.sort_values("timestamp").reset_index(drop=True)

    estados = dados["estado"].to_numpy()
    timestamps = dados["timestamp"].to_numpy()
    eventos = []
    for indice in range(1, len(dados)):
        if estados[indice - 1] != 0 or estados[indice] != 1:
            continue

        fechamento = indice + 1
        while fechamento < len(dados) and estados[fechamento] == 1:
            fechamento += 1

        if fechamento >= len(dados) or estados[fechamento] != 0:
            continue

        inicio = pd.Timestamp(timestamps[indice])
        fim = pd.Timestamp(timestamps[fechamento])
        eventos.append(
            {
                "inicio": inicio,
                "fechamento": fim,
                "duracao_minutos": (fim - inicio).total_seconds() / 60,
            }
        )

    return pd.DataFrame(eventos)


def calcular_medias_ambientais_eventos(
    dados_ambientais: pd.DataFrame,
    eventos: pd.DataFrame,
    coluna: str,
) -> pd.Series:
    """Calcula a média de uma variável ambiental no intervalo de cada evento.

    A média usa o mesmo intervalo exibido nos gráficos de eventos:
    30 minutos antes do início até 120 minutos depois.
    """
    medias = []
    for _, evento in eventos.iterrows():
        inicio = pd.Timestamp(evento["inicio"])
        inicio_janela = inicio - pd.to_timedelta(30, unit="min")
        fim_janela = inicio + pd.to_timedelta(120, unit="min")
        temperaturas = dados_ambientais.loc[
            dados_ambientais["timestamp"].between(inicio_janela, fim_janela),
            coluna,
        ].dropna()
        medias.append(float(temperaturas.mean()) if not temperaturas.empty else float("nan"))

    return pd.Series(medias, dtype="float64")


def calcular_temperaturas_medias_eventos(
    dados_ambientais: pd.DataFrame,
    eventos: pd.DataFrame,
) -> pd.Series:
    """Calcula a temperatura média do ar para cada evento."""
    return calcular_medias_ambientais_eventos(
        dados_ambientais,
        eventos,
        "temperature",
    )


def calcular_umidades_medias_eventos(
    dados_ambientais: pd.DataFrame,
    eventos: pd.DataFrame,
) -> pd.Series:
    """Calcula a umidade média do ar para cada evento."""
    return calcular_medias_ambientais_eventos(
        dados_ambientais,
        eventos,
        "humidity",
    )


def criar_normalizacao_hotbar(
    temperaturas_ambientais: pd.Series,
) -> Normalize | None:
    """Cria uma escala global usando todo o CSV ambiental do ano."""
    valores_validos = pd.to_numeric(
        temperaturas_ambientais,
        errors="coerce",
    ).dropna()
    if valores_validos.empty:
        return None

    valor_minimo = float(valores_validos.min())
    valor_maximo = float(valores_validos.max())
    if valor_minimo == valor_maximo:
        margem = max(abs(valor_minimo) * 0.01, 0.5)
        valor_minimo -= margem
        valor_maximo += margem
    if valor_minimo == 0 or valor_maximo == 100:
        valor_maximo = 100
        valor_minimo = 0

    return Normalize(vmin=valor_minimo, vmax=valor_maximo)


def adicionar_hotbar_ambiental(
    figura: plt.Figure,
    eixo: plt.Axes,
    normalizacao: Normalize,
    media_evento: float | None,
    *,
    unidade: str,
    cores: list[str],
    pad: float,
) -> None:
    """Adiciona uma hotbar ambiental com escala global e média do evento."""
    paleta = LinearSegmentedColormap.from_list(
        "hotbar_ambiental",
        cores,
    )
    mapeador = ScalarMappable(norm=normalizacao, cmap=paleta)
    mapeador.set_array([])
    barra = figura.colorbar(
        mapeador,
        ax=eixo,
        fraction=0.025,
        pad=pad,
        aspect=32,
    )
    barra.set_ticks([normalizacao.vmin, normalizacao.vmax])
    barra.set_ticklabels(
        [
            f"{normalizacao.vmin:.1f} {unidade}".replace(".", ","),
            f"{normalizacao.vmax:.1f} {unidade}".replace(".", ","),
        ]
    )
    barra.ax.tick_params(length=0, labelsize=8, pad=2)

    if media_evento is not None and pd.notna(media_evento):
        media_evento = float(media_evento)
        barra.ax.axhline(
            media_evento,
            color=CORES["texto"],
            linewidth=2.8,
            alpha=0.8,
            zorder=5,
        )
        barra.ax.text(
            1.15,
            media_evento,
            f"{media_evento:.1f} {unidade}".replace(".", ","),
            transform=barra.ax.get_yaxis_transform(),
            ha="left",
            va="center",
            fontsize=8,
            color=CORES["texto"],
            bbox={
                "facecolor": CORES["fundo"],
                "edgecolor": CORES["sem_borda"],
                "alpha": 0.75,
                "pad": 1,
            },
            clip_on=False,
        )


def adicionar_hotbar_temperatura(
    figura: plt.Figure,
    eixo: plt.Axes,
    normalizacao: Normalize,
    temperatura_media: float | None,
) -> None:
    """Adiciona a hotbar global de temperatura do ar."""
    adicionar_hotbar_ambiental(
        figura,
        eixo,
        normalizacao,
        temperatura_media,
        unidade="°C",
        cores=CORES["hotbar_temperatura"],
        pad=0.02,
    )


def adicionar_hotbar_umidade(
    figura: plt.Figure,
    eixo: plt.Axes,
    normalizacao: Normalize,
    umidade_media: float | None,
) -> None:
    """Adiciona a hotbar global de umidade relativa do ar."""
    adicionar_hotbar_ambiental(
        figura,
        eixo,
        normalizacao,
        umidade_media,
        unidade="%RH",
        cores=CORES["hotbar_umidade"],
        pad=0.08,
    )


def mapear_dispositivos(dados: pd.DataFrame) -> dict[tuple[int, str], int]:
    """Associa cada identificador original ao número usado nos gráficos."""
    mapeamento: dict[tuple[int, str], int] = {}
    for linha in sorted(dados["linha"].unique()):
        identificadores = sorted(
            dados.loc[dados["linha"].eq(linha), "dispositivo"]
            .dropna()
            .astype(str)
            .unique()
        )
        for numero, identificador in enumerate(identificadores, start=1):
            mapeamento[(int(linha), identificador)] = numero
    return mapeamento


def salvar_mapeamento_dispositivos(
    dados: pd.DataFrame,
    mapeamento: dict[tuple[int, str], int],
    *,
    nome_dataset: str,
    ano: int,
    caminho: Path,
) -> None:
    """Salva a correspondência entre ``generated_by`` e dispositivo 1 ou 2."""
    linhas = [f"Dado {nome_dataset} de {ano}"]
    for linha in sorted(dados["linha"].unique()):
        linhas.append(f"linha {int(linha)}:")
        dispositivos = sorted(
            (chave for chave in mapeamento if chave[0] == int(linha)),
            key=lambda chave: mapeamento[chave],
        )
        for _, identificador in dispositivos:
            numero = mapeamento[(int(linha), identificador)]
            linhas.append(f"dispositivo {identificador}: dispositivo {numero}")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def ajustar_anotacoes_sobrepostas(
    figura: plt.Figure,
    eixo: plt.Axes,
    anotacoes: list[tuple[int, object]],
) -> None:
    """Separa labels sobrepostas sem mover as que já estão legíveis."""
    anotacoes_por_dispositivo = {
        numero: anotacao for numero, anotacao in anotacoes
    }
    if not {1, 2}.issubset(anotacoes_por_dispositivo):
        return

    figura.canvas.draw()
    renderizador = figura.canvas.get_renderer()
    anotacao_1 = anotacoes_por_dispositivo[1]
    anotacao_2 = anotacoes_por_dispositivo[2]
    caixa_1 = anotacao_1.get_window_extent(renderizador)
    caixa_2 = anotacao_2.get_window_extent(renderizador)
    if not caixa_1.overlaps(caixa_2):
        return

    caixa_eixo = eixo.get_window_extent(renderizador)
    separacao = max(caixa_1.height, caixa_2.height) + 6.0
    centro_medio = (
        (caixa_1.y0 + caixa_1.y1) / 2
        + (caixa_2.y0 + caixa_2.y1) / 2
    ) / 2
    centro_1 = centro_medio + separacao / 2
    centro_2 = centro_medio - separacao / 2
    centro_1 = min(
        max(centro_1, caixa_eixo.y0 + caixa_1.height / 2),
        caixa_eixo.y1 - caixa_1.height / 2,
    )
    centro_2 = min(
        max(centro_2, caixa_eixo.y0 + caixa_2.height / 2),
        caixa_eixo.y1 - caixa_2.height / 2,
    )

    fator_pontos_por_pixel = 72 / figura.dpi
    atual_1 = (caixa_1.y0 + caixa_1.y1) / 2
    atual_2 = (caixa_2.y0 + caixa_2.y1) / 2
    anotacao_1.set_position(
        (0, (centro_1 - atual_1) * fator_pontos_por_pixel)
    )
    anotacao_2.set_position(
        (0, (centro_2 - atual_2) * fator_pontos_por_pixel)
    )


def criar_plot(
    serie: pd.DataFrame,
    *,
    ano: int,
    linha: int,
    numero_dispositivo: int,
    identificador: str,
    variavel: str,
    timezone: str,
    caminho_saida: Path,
) -> None:
    """Cria e salva uma única figura para uma variável."""
    configuracao = VARIAVEIS[variavel]
    serie = serie.dropna(subset=["timestamp", variavel]).sort_values("timestamp")
    if serie.empty:
        return

    fig, ax = plt.subplots(figsize=(14, 6), constrained_layout=True)
    ax.plot(
        serie["timestamp"],
        serie[variavel],
        color=CORES["dispositivo_evento_1"],
        linewidth=0.55,
        marker=".",
        markersize=1.8,
        linestyle="-",
    )
    ax.set_title(
        f"Série temporal do solo em {ano} — linha {linha} — "
        f"dispositivo {numero_dispositivo}"
    )
    ax.set_xlabel(f"Data e hora ({timezone})")
    ax.set_ylabel(f"{configuracao['nome']} ({configuracao['unidade']})")
    ax.grid(True, which="major", linestyle="--", linewidth=0.45, alpha=0.5)
    ax.margins(x=0.01)

    localizador = mdates.AutoDateLocator(minticks=6, maxticks=10)
    ax.xaxis.set_major_locator(localizador)
    ax.xaxis.set_major_formatter(
        mdates.DateFormatter("%d/%m/%Y\n%H:%M", tz=serie["timestamp"].dt.tz)
    )

    nome_arquivo = "-".join(
        [
            f"solo{ano}",
            f"linha{linha}",
            f"dispositivo{numero_dispositivo}",
            identificador,
            configuracao["arquivo"],
        ]
    )
    fig.savefig(caminho_saida / f"{slug(nome_arquivo)}.png", dpi=160)
    plt.close(fig)


def gerar_plots(
    dados: pd.DataFrame,
    *,
    ano: int,
    timezone: str,
    diretorio_saida: Path,
) -> int:
    """Gera todas as figuras e retorna a quantidade criada."""
    diretorio_saida.mkdir(parents=True, exist_ok=True)
    quantidade = 0
    mapeamento = mapear_dispositivos(dados)

    agrupado = dados.groupby(["linha", "dispositivo"], sort=True)
    for (linha, identificador), grupo in agrupado:
        identificador = str(identificador)
        numero_dispositivo = mapeamento[(int(linha), identificador)]

        for variavel in VARIAVEIS:
            pontos_validos = grupo[variavel].notna().sum()
            if pontos_validos == 0:
                continue
            criar_plot(
                grupo,
                ano=ano,
                linha=int(linha),
                numero_dispositivo=numero_dispositivo,
                identificador=identificador,
                variavel=variavel,
                timezone=timezone,
                caminho_saida=diretorio_saida,
            )
            quantidade += 1

    return quantidade


def criar_plot_com_dois_dispositivos(
    grupo_linha: pd.DataFrame,
    *,
    ano: int,
    linha: int,
    variavel: str,
    timezone: str,
    caminho_saida: Path,
    mapeamento: dict[tuple[int, str], int],
) -> None:
    """Cria uma figura contendo os dois dispositivos de uma linha."""
    configuracao = VARIAVEIS[variavel]
    fig, ax = plt.subplots(figsize=(14, 6), constrained_layout=True)

    cores = {
        1: CORES["dispositivo_evento_1"],
        2: CORES["dispositivo_evento_2"],
    }
    for identificador, serie in grupo_linha.groupby("dispositivo", sort=True):
        identificador = str(identificador)
        numero_dispositivo = mapeamento[(linha, identificador)]
        serie = serie.dropna(subset=["timestamp", variavel]).sort_values("timestamp")
        if serie.empty:
            continue
        ax.plot(
            serie["timestamp"],
            serie[variavel],
            color=cores.get(numero_dispositivo, CORES["dispositivo_fallback"]),
            linewidth=0.55,
            marker=".",
            markersize=1.8,
            linestyle="-",
            label=f"Dispositivo {numero_dispositivo}",
        )

    ax.set_title(f"Série temporal do solo em {ano} — linha {linha}")
    ax.set_xlabel(f"Data e hora ({timezone})")
    ax.set_ylabel(f"{configuracao['nome']} ({configuracao['unidade']})")
    ax.grid(True, which="major", linestyle="--", linewidth=0.45, alpha=0.5)
    ax.margins(x=0.01)
    ax.legend(title="Dispositivo")

    localizador = mdates.AutoDateLocator(minticks=6, maxticks=10)
    ax.xaxis.set_major_locator(localizador)
    ax.xaxis.set_major_formatter(
        mdates.DateFormatter(
            "%d/%m/%Y\n%H:%M",
            tz=grupo_linha["timestamp"].dt.tz,
        )
    )

    nome_arquivo = "-".join(
        [f"solo{ano}", f"linha{linha}", configuracao["arquivo"]]
    )
    fig.savefig(caminho_saida / f"{slug(nome_arquivo)}.png", dpi=160)
    plt.close(fig)


def gerar_plots_com_dois_dispositivos(
    dados: pd.DataFrame,
    *,
    ano: int,
    timezone: str,
    diretorio_saida: Path,
) -> int:
    """Gera uma figura por linha e variável, com os dois dispositivos."""
    diretorio_saida.mkdir(parents=True, exist_ok=True)
    mapeamento = mapear_dispositivos(dados)
    quantidade = 0

    for linha, grupo_linha in dados.groupby("linha", sort=True):
        for variavel in VARIAVEIS:
            pontos_validos = grupo_linha[variavel].notna().sum()
            if pontos_validos == 0:
                continue
            criar_plot_com_dois_dispositivos(
                grupo_linha,
                ano=ano,
                linha=int(linha),
                variavel=variavel,
                timezone=timezone,
                caminho_saida=diretorio_saida,
                mapeamento=mapeamento,
            )
            quantidade += 1

    return quantidade


def criar_plot_solo_com_valvula(
    grupo_linha: pd.DataFrame,
    acionamentos_linha: pd.DataFrame,
    *,
    ano: int,
    linha: int,
    variavel: str,
    timezone: str,
    caminho_saida: Path,
    mapeamento: dict[tuple[int, str], int],
) -> None:
    """Cria uma figura de solo com os registros de válvula em estado 1.0."""
    configuracao = VARIAVEIS[variavel]
    fig, ax = plt.subplots(figsize=(14, 6), constrained_layout=True)

    cores = {
        1: CORES["dispositivo_evento_1"],
        2: CORES["dispositivo_evento_2"],
    }
    for identificador, serie in grupo_linha.groupby("dispositivo", sort=True):
        identificador = str(identificador)
        numero_dispositivo = mapeamento[(linha, identificador)]
        serie = serie.dropna(subset=["timestamp", variavel]).sort_values(
            "timestamp"
        )
        if serie.empty:
            continue
        ax.scatter(
            serie["timestamp"],
            serie[variavel],
            color=cores.get(numero_dispositivo, CORES["dispositivo_fallback"]),
            s=5,
            alpha=0.8,
            label=f"Dispositivo {numero_dispositivo}",
        )

    for indice, timestamp in enumerate(acionamentos_linha["timestamp"]):
        ax.axvline(
            timestamp,
            color=CORES["valvula"],
            linewidth=0.7,
            alpha=0.35,
            zorder=0,
            label="Acionamento da válvula" if indice == 0 else "_nolegend_",
        )

    ax.set_title(
        f"{configuracao['nome']} e acionamentos da válvula em {ano} — linha {linha}"
    )
    ax.set_xlabel(f"Data e hora ({timezone})")
    ax.set_ylabel(f"{configuracao['nome']} ({configuracao['unidade']})")
    ax.grid(True, which="major", linestyle="--", linewidth=0.45, alpha=0.5)
    ax.margins(x=0.01)
    ax.legend(title="Legenda")

    localizador = mdates.AutoDateLocator(minticks=6, maxticks=10)
    ax.xaxis.set_major_locator(localizador)
    ax.xaxis.set_major_formatter(
        mdates.DateFormatter(
            "%d/%m/%Y\n%H:%M",
            tz=grupo_linha["timestamp"].dt.tz,
        )
    )

    nome_arquivo = "-".join(
        [
            f"solo{ano}",
            f"linha{linha}",
            f"{configuracao['arquivo']}-com-acionamentos-da-valvula",
        ]
    )
    fig.savefig(caminho_saida / f"{slug(nome_arquivo)}.png", dpi=160)
    plt.close(fig)


def gerar_plots_com_valvula(
    dados: pd.DataFrame,
    acionamentos_valvula: pd.DataFrame,
    *,
    ano: int,
    timezone: str,
    diretorio_saida: Path,
) -> int:
    """Gera uma figura por linha e variável com os dispositivos e a válvula."""
    diretorio_saida.mkdir(parents=True, exist_ok=True)
    mapeamento = mapear_dispositivos(dados)
    quantidade = 0

    for linha, grupo_linha in dados.groupby("linha", sort=True):
        acionamentos_linha = acionamentos_valvula.loc[
            acionamentos_valvula["linha"].eq(linha)
        ]
        for variavel in VARIAVEIS:
            criar_plot_solo_com_valvula(
                grupo_linha,
                acionamentos_linha,
                ano=ano,
                linha=int(linha),
                variavel=variavel,
                timezone=timezone,
                caminho_saida=diretorio_saida,
                mapeamento=mapeamento,
            )
            quantidade += 1

    return quantidade


def criar_plot_evento_valvula(
    grupo_linha: pd.DataFrame,
    evento: pd.Series,
    *,
    ano: int,
    linha: int,
    numero_evento: int,
    variavel: str,
    timezone: str,
    caminho_saida: Path,
    mapeamento: dict[tuple[int, str], int],
    normalizacao_hotbar: Normalize | None = None,
    temperatura_media_evento: float | None = None,
    normalizacao_umidade_hotbar: Normalize | None = None,
    umidade_media_evento: float | None = None,
    mostrar_hotbar: bool = True,
) -> None:
    """Cria um plot de -30 a +120 minutos ao redor de um evento válido."""
    configuracao = VARIAVEIS[variavel]
    inicio = pd.Timestamp(evento["inicio"])
    fechamento = pd.Timestamp(evento["fechamento"])
    inicio_janela = inicio - pd.to_timedelta(30, unit="min")
    fim_janela = inicio + pd.to_timedelta(120, unit="min")

    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    cores = {
        1: CORES["dispositivo_evento_1"],
        2: CORES["dispositivo_evento_2"],
    }

    anotacoes: list[tuple[int, object]] = []

    for identificador, serie in grupo_linha.groupby("dispositivo", sort=True):
        identificador = str(identificador)
        numero_dispositivo = mapeamento[(linha, identificador)]
        serie = serie.loc[
            serie["timestamp"].between(inicio_janela, fim_janela),
            ["timestamp", variavel],
        ].dropna()
        serie = serie.sort_values("timestamp")
        if serie.empty:
            continue

        tempo_relativo = (
            serie["timestamp"] - inicio
        ).dt.total_seconds() / 60
        cor = cores.get(numero_dispositivo, CORES["dispositivo_fallback"])

        alpha_linha = 0.4 if numero_dispositivo == 1 else 0.9
        alpha_pontos = 0.15 if numero_dispositivo == 1 else 0.35

        ax.plot(
            tempo_relativo,
            serie[variavel],
            color=cor,
            linewidth=1.0,
            alpha=alpha_linha,
            label="_nolegend_",
        )
        ax.scatter(
            tempo_relativo,
            serie[variavel],
            color=cor,
            s=14,
            alpha=alpha_pontos,
            zorder=3,
        )

        # Identifica cada série diretamente no gráfico, sem ocupar a legenda.
        rotulo_x = 112.0
        pontos_ate_rotulo = serie.loc[tempo_relativo <= rotulo_x, variavel]
        base_rotulo = (
            pontos_ate_rotulo.iloc[-1]
            if not pontos_ate_rotulo.empty
            else serie[variavel].iloc[-1]
        )
        anotacao = ax.annotate(
            f"dispositivo {numero_dispositivo}",
            xy=(rotulo_x, base_rotulo),
            xytext=(0, 0),
            textcoords="offset points",
            color=cor,
            fontsize=9,
            ha="right",
            va="center",
            clip_on=True,
        )

        anotacoes.append((numero_dispositivo, anotacao))

    if variavel == "humidity":
        for nivel_umidade in (27, 24):
            ax.axhline(
                nivel_umidade,
                color=CORES["referencia_umidade"],
                linestyle="--",
                linewidth=0.8,
                alpha=0.45,
                zorder=1,
            )

    duracao_exibida = min(float(evento["duracao_minutos"]), 120.0)
    ax.axvspan(
        0,
        duracao_exibida,
        color=CORES["valvula"],
        alpha=0.12,
        label="Válvula aberta",
    )
    ax.axvline(0, color=CORES["texto"], linewidth=1.0, label="_nolegend_")

    inicio_texto = inicio.strftime("%d/%m/%Y %H:%M:%S")
    ax.set_title(
        # f"{configuracao['nome']} no evento {numero_evento:02d} "
        f"Início: {inicio_texto} ({timezone}) - "
        f"duração: {float(evento['duracao_minutos']):.1f} min - "
        f"linha {linha} em {ano}"
    )
    ax.set_xlabel("Tempo relativo ao início da irrigação (min)")
    ax.set_ylabel(f"{configuracao['nome']} ({configuracao['unidade']})")
    ax.set_xlim(-30, 120)
    ax.set_xticks([-30, 0, 30, 60, 90, 120])
    ax.grid(False)

    # Para ocultar a hotbar, comente esta chamada ou use mostrar_hotbar=False.
    if mostrar_hotbar:
        if normalizacao_umidade_hotbar is not None:
            adicionar_hotbar_umidade(
                figura=fig,
                eixo=ax,
                normalizacao=normalizacao_umidade_hotbar,
                umidade_media=umidade_media_evento,
            )
        if normalizacao_hotbar is not None:
            adicionar_hotbar_temperatura(
                figura=fig,
                eixo=ax,
                normalizacao=normalizacao_hotbar,
                temperatura_media=temperatura_media_evento,
            )

    ax.legend()

    nome_arquivo = "-".join(
        [
            # f"evento-valvula-linha{linha}",
            f"evento{numero_evento:02d}",
            configuracao["arquivo"],
        ]
    )

    ajustar_anotacoes_sobrepostas(fig, ax, anotacoes)
    fig.savefig(caminho_saida / f"{slug(nome_arquivo)}.png", dpi=160)
    plt.close(fig)


def gerar_plots_eventos_valvula(
    dados: pd.DataFrame,
    eventos: pd.DataFrame,
    *,
    dados_ambientais: pd.DataFrame,
    ano: int,
    linha: int,
    timezone: str,
    diretorio_saida: Path,
    mostrar_hotbar: bool = True,
) -> int:
    """Gera umidade e temperatura para cada evento válido da linha."""
    diretorio_saida.mkdir(parents=True, exist_ok=True)
    dados_linha = dados.loc[dados["linha"].eq(linha)]
    if dados_linha.empty:
        raise ValueError(f"Não há dados de solo para a linha {linha}.")

    mapeamento = mapear_dispositivos(dados_linha)
    temperaturas_medias = calcular_temperaturas_medias_eventos(
        dados_ambientais,
        eventos,
    )
    umidades_medias = calcular_umidades_medias_eventos(
        dados_ambientais,
        eventos,
    )
    normalizacao_hotbar = criar_normalizacao_hotbar(
        dados_ambientais["temperature"]
    )
    normalizacao_umidade_hotbar = criar_normalizacao_hotbar(
        dados_ambientais["humidity"]
    )
    quantidade = 0
    for numero_evento, (_, evento) in enumerate(eventos.iterrows(), start=1):
        for variavel in ("humidity", "temperature"):
            criar_plot_evento_valvula(
                dados_linha,
                evento,
                ano=ano,
                linha=linha,
                numero_evento=numero_evento,
                variavel=variavel,
                timezone=timezone,
                caminho_saida=diretorio_saida,
                mapeamento=mapeamento,
                normalizacao_hotbar=normalizacao_hotbar,
                temperatura_media_evento=temperaturas_medias.iloc[numero_evento - 1],
                normalizacao_umidade_hotbar=normalizacao_umidade_hotbar,
                umidade_media_evento=umidades_medias.iloc[numero_evento - 1],
                mostrar_hotbar=mostrar_hotbar,
            )
            quantidade += 1
    return quantidade


def main() -> None:
    """Ponto de entrada do gerador de figuras."""
    args = argumentos()
    dados = carregar_dados(args.input, args.ano, args.timezone)
    if dados.empty:
        raise ValueError(f"Não há registros de solo para o ano {args.ano}.")
    acionamentos_valvula = carregar_acionamentos_valvula(
        args.input_valvula,
        args.ano,
        args.timezone,
    )
    eventos_valvula = carregar_eventos_valvula(
        args.input_valvula,
        args.ano,
        args.timezone,
        args.linha_eventos,
    )
    dados_ambientais = None
    if args.somente_eventos:
        caminho_ambiental = args.input_ambiental or (
            RAIZ_PROJETO
            / "data"
            / "raw"
            / str(args.ano)
            / f"environmental{args.ano}.csv"
        )
        dados_ambientais = carregar_dados_ambientais(
            caminho_ambiental,
            args.ano,
            args.timezone,
        )

    quantidade = 0
    if (
        not args.somente_combinados
        and not args.somente_umidade_valvula
        and not args.somente_eventos
    ):
        quantidade = gerar_plots(
            dados,
            ano=args.ano,
            timezone=args.timezone,
            diretorio_saida=args.output,
        )
    quantidade_combinada = 0
    if not args.somente_umidade_valvula and not args.somente_eventos:
        quantidade_combinada = gerar_plots_com_dois_dispositivos(
            dados,
            ano=args.ano,
            timezone=args.timezone,
            diretorio_saida=args.output_combinado,
        )
        salvar_mapeamento_dispositivos(
            dados,
            mapear_dispositivos(dados),
            nome_dataset=args.input.name,
            ano=args.ano,
            caminho=args.output_combinado / "mapeamento-dispositivos.txt",
        )
    quantidade_valvula = 0
    if not args.somente_eventos:
        quantidade_valvula = gerar_plots_com_valvula(
            dados,
            acionamentos_valvula,
            ano=args.ano,
            timezone=args.timezone,
            diretorio_saida=args.output_valvula,
        )
        salvar_mapeamento_dispositivos(
            dados,
            mapear_dispositivos(dados),
            nome_dataset=args.input.name,
            ano=args.ano,
            caminho=args.output_valvula / "mapeamento-dispositivos.txt",
        )
    quantidade_eventos = 0
    if args.somente_eventos:
        quantidade_eventos = gerar_plots_eventos_valvula(
            dados,
            eventos_valvula,
            dados_ambientais=dados_ambientais,
            ano=args.ano,
            linha=args.linha_eventos,
            timezone=args.timezone,
            diretorio_saida=args.output_eventos,
        )
        dados_linha_eventos = dados.loc[dados["linha"].eq(args.linha_eventos)]
        salvar_mapeamento_dispositivos(
            dados_linha_eventos,
            mapear_dispositivos(dados_linha_eventos),
            nome_dataset=args.input.name,
            ano=args.ano,
            caminho=args.output_eventos / "mapeamento-dispositivos.txt",
        )
    linhas = dados["linha"].nunique()
    dispositivos = dados[["linha", "dispositivo"]].drop_duplicates().shape[0]
    print(
        f"{quantidade} figuras individuais e {quantidade_combinada} figuras "
        f"combinadas e {quantidade_valvula} figuras com válvula geradas "
        f"e {quantidade_eventos} figuras de eventos geradas "
        f"para {len(dados):,} registros, "
        f"{linhas} linhas e {dispositivos} dispositivos."
    )
    print(f"Saída: {args.output.resolve()}")
    print(f"Saída combinada: {args.output_combinado.resolve()}")
    print(f"Saída umidade e válvula: {args.output_valvula.resolve()}")
    print(f"Saída eventos: {args.output_eventos.resolve()}")


if __name__ == "__main__":
    main()
