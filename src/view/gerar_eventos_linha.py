"""Atalho simples para gerar os plots de eventos de uma linha."""

from pathlib import Path

from plotar_solo_2024 import (
    carregar_dados,
    carregar_dados_ambientais,
    carregar_eventos_valvula,
    gerar_plots_eventos_valvula,
    mapear_dispositivos,
    salvar_mapeamento_dispositivos,
)


RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def main() -> None:
    """Altere somente ``linha_eventos`` para escolher a linha."""
    ano = 2024
    linha_eventos = 3
    timezone = "UTC"

    arquivo_solo = RAIZ_PROJETO / "data" / "raw" / str(ano) / f"soil{ano}.csv"
    arquivo_ambiental = (
        RAIZ_PROJETO
        / "data"
        / "raw"
        / str(ano)
        / f"environmental{ano}.csv"
    )
    arquivo_valvula = (
        RAIZ_PROJETO
        / "data"
        / "raw"
        / str(ano)
        / f"valve_controller{ano}.csv"
    )
    diretorio_saida = RAIZ_PROJETO / "imgs" / f"solo{ano}-eventos-linha{linha_eventos}"

    dados = carregar_dados(arquivo_solo, ano, timezone)
    dados_ambientais = carregar_dados_ambientais(
        arquivo_ambiental,
        ano,
        timezone,
    )
    eventos = carregar_eventos_valvula(
        arquivo_valvula,
        ano=ano,
        timezone=timezone,
        linha=linha_eventos,
    )
    quantidade = gerar_plots_eventos_valvula(
        dados,
        eventos,
        dados_ambientais=dados_ambientais,
        ano=ano,
        linha=linha_eventos,
        timezone=timezone,
        diretorio_saida=diretorio_saida,
    )

    dados_linha = dados.loc[dados["linha"].eq(linha_eventos)]
    salvar_mapeamento_dispositivos(
        dados_linha,
        mapear_dispositivos(dados_linha),
        nome_dataset=arquivo_solo.name,
        ano=ano,
        caminho=diretorio_saida / "mapeamento-dispositivos.txt",
    )
    print(f"{len(eventos)} eventos encontrados na linha {linha_eventos}.")
    print(f"{quantidade} figuras salvas em: {diretorio_saida}")


if __name__ == "__main__":
    main()
