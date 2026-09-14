"""
parse_readmes.py  (v6 - FINAL)

Extrai colunas dos READMEs das safras 2023, 2024 e 2025 do dataset
Mendeley Tomato Testbed.

Filtra automaticamente:
  - Blocos **Location:** (coordenadas)
  - Blocos **Parameters:** (T_base, T_cutoff)
  - Linhas "Line #N → ..." (localização de sensores)
  - Linhas "Latitude/Longitude: ..."
  - Descrições antes de **Fields:** (ex.: "Growing Degree Days", "Heat Units")

Layout suportado:
  A) READMEs e CSVs na mesma pasta
  B) READMEs e CSVs em subpastas 2023/, 2024/, 2025/

Uso:
    python parse_readmes.py
    python parse_readmes.py --root . --out .
"""

import argparse
import os
import re
import glob
import time
import pandas as pd


# ---------- normalização de encoding ----------

ENCODING_FIXES = {
    "Â°C": "°C", "Â°": "°", "â€“": "–", "â€”": "—",
    "Î¼S/cm": "µS/cm", "Â³": "³", "â†’": "->", "Â": "",
}

def fix_encoding(s: str) -> str:
    for k, v in ENCODING_FIXES.items():
        s = s.replace(k, v)
    return s.strip()


# ---------- descoberta de arquivos ----------

PASTAS_SAFRA = {"2023", "2024", "2025"}

def find_readmes(root: str):
    """
    Procura READMEs em:
      - root/*.md
      - root/2023/*.md, root/2024/*.md, root/2025/*.md
    """
    found = set()
    patterns = ["README*.md", "README*.MD", "readme*.md"]

    # nível 1 (raiz)
    for pat in patterns:
        for p in glob.glob(os.path.join(root, pat)):
            if os.path.isfile(p):
                found.add(os.path.abspath(p))

    # nível 2 (apenas pastas de safra)
    for sub in sorted(os.listdir(root)):
        if sub not in PASTAS_SAFRA:
            continue
        subpath = os.path.join(root, sub)
        if not os.path.isdir(subpath):
            continue
        for pat in patterns:
            for p in glob.glob(os.path.join(subpath, pat)):
                if os.path.isfile(p):
                    found.add(os.path.abspath(p))

    return sorted(found)


def extract_safra_from_path(path: str) -> str:
    """
    1) Tenta pelo nome do arquivo (README(2023).md)
    2) Tenta pela pasta pai (…/2023/README.md)
    """
    base = os.path.basename(path)
    m = re.search(r"(20\d{2})", base)
    if m:
        return m.group(1)

    parent = os.path.basename(os.path.dirname(path))
    if re.fullmatch(r"20\d{2}", parent):
        return parent

    return "desconhecida"


# ---------- limpeza do texto do README ----------

def clean_readme_text(text: str) -> str:
    """
    Remove blocos e linhas que NÃO representam colunas:
      - bloco **Location:** / **Locations:** (coordenadas)
      - bloco **Parameters:** (T_base, T_cutoff)
      - linhas 'Line #N → ...' remanescentes
      - linhas 'Latitude: ...' / 'Longitude: ...'
    """
    # 1. remove bloco de Location(s)
    text = re.sub(
        r"\*\*Location[s]?:\*\*.*?(?=\n\s*\n|\n\*\*|\Z)",
        "", text, flags=re.DOTALL,
    )
    # 2. remove bloco de Parameters
    text = re.sub(
        r"\*\*Parameters:\*\*.*?(?=\n\s*\n|\n\*\*|\Z)",
        "", text, flags=re.DOTALL,
    )
    # 3. remove linhas "Line #N → ..."
    text = re.sub(
        r"^-\s*Line\s*#\d+\s*(?:→|->).*$",
        "", text, flags=re.MULTILINE,
    )
    # 4. remove linhas "Latitude: ..." / "Longitude: ..."
    text = re.sub(
        r"^-\s*(Latitude|Longitude)\s*:.*$",
        "", text, flags=re.MULTILINE,
    )
    return text


def keep_only_fields(sec: str) -> str:
    """
    Se a seção tem '**Fields:**', retorna apenas o trecho a partir dele.
    Caso contrário, retorna a seção inteira.
    Remove descrições como 'Growing Degree Days (GDD)' e 'Heat Units'
    que aparecem ANTES dos fields reais.
    """
    m = re.search(r"\*\*Fields:\*\*", sec)
    if m:
        return sec[m.end():]
    return sec


# ---------- validação de nome de coluna ----------

def is_real_column(name: str) -> bool:
    """
    Descarta nomes que claramente NÃO são colunas:
      - contém ':'  (ex.: 'Base temperature: 10°C')
      - contém '→' ou '->'  (ex.: 'Line #1 →')
      - começa com 'Line #'
      - começa com 'Latitude' ou 'Longitude'
    """
    if not name:
        return False
    if ":" in name:
        return False
    if "→" in name or "->" in name:
        return False
    if re.match(r"^Line\s*#\d+", name):
        return False
    if re.match(r"^(Latitude|Longitude)", name):
        return False
    return True


# ---------- parsing de um README ----------

def parse_readme(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = fix_encoding(f.read())

    safra = extract_safra_from_path(path)
    text = clean_readme_text(text)

    sections = re.split(r"^##\s+", text, flags=re.MULTILINE)

    rows = []
    for sec in sections:
        if not sec.strip():
            continue
        first_line = sec.splitlines()[0].strip()
        m = re.match(r"([A-Za-z0-9_\-\.]+\.csv)", first_line)
        if not m:
            continue
        arquivo = m.group(1)

        # NOVO: corta tudo antes de '**Fields:**', se existir
        body = keep_only_fields(sec)

        cols = re.findall(r"^-\s+(.+)$", body, flags=re.MULTILINE)
        for c in cols:
            c = fix_encoding(c)
            c_clean = re.sub(r"\s*\(.+?\)\s*$", "", c).strip()
            if is_real_column(c_clean):
                rows.append({
                    "safra": safra,
                    "arquivo": arquivo,
                    "coluna_original": c,
                    "coluna": c_clean,
                })
    return rows


def parse_readme_meta(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = fix_encoding(f.read())

    safra = extract_safra_from_path(path)
    sections = re.split(r"^##\s+", text, flags=re.MULTILINE)

    metas = []
    for sec in sections:
        if not sec.strip():
            continue
        first_line = sec.splitlines()[0].strip()
        m = re.match(r"([A-Za-z0-9_\-\.]+\.csv)", first_line)
        if not m:
            continue
        arquivo = m.group(1)

        n_devices = None
        m_dev = re.search(
            r"(\d+)\s+(?:Milesight|Talkpool|MClimate|Decentlab|DL\-)", sec
        )
        if m_dev:
            n_devices = int(m_dev.group(1))

        sampling = None
        m_s = re.search(r"\*\*Sampling rate:\*\*\s*(.+)$", sec, flags=re.MULTILINE)
        if m_s:
            sampling = fix_encoding(m_s.group(1))

        depth = None
        m_d = re.search(r"\*\*Sensor depth:\*\*\s*(.+)$", sec, flags=re.MULTILINE)
        if m_d:
            depth = fix_encoding(m_d.group(1))

        metas.append({
            "safra": safra,
            "arquivo": arquivo,
            "n_dispositivos": n_devices,
            "sampling": sampling,
            "sensor_depth": depth,
        })
    return metas


# ---------- main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Pasta raiz (padrão: atual)")
    parser.add_argument("--out", default=".", help="Pasta de saída")
    args = parser.parse_args()

    t0 = time.time()

    readmes = find_readmes(args.root)
    if not readmes:
        print(f"[erro] Nenhum README encontrado em: {os.path.abspath(args.root)}")
        return

    print("READMES encontrados:")
    for p in readmes:
        rel = os.path.relpath(p, args.root)
        print(f"  - {rel}  (safra={extract_safra_from_path(p)})")

    all_rows, all_metas = [], []
    for p in readmes:
        all_rows.extend(parse_readme(p))
        all_metas.extend(parse_readme_meta(p))

    df = pd.DataFrame(all_rows).drop_duplicates()
    meta = pd.DataFrame(all_metas).drop_duplicates()

    # normaliza nome base do arquivo (remove ano e extensão)
    df["arquivo_base"] = (
        df["arquivo"]
        .str.replace(r"20\d{2}", "", regex=True)
        .str.replace(".csv", "", regex=False)
        .str.rstrip("_")
    )

    # matriz de compatibilidade
    pivot = (
        df.assign(presente=1)
          .pivot_table(index=["arquivo_base", "coluna"],
                       columns="safra",
                       values="presente",
                       aggfunc="max",
                       fill_value=0)
          .reset_index()
    )

    safra_cols = [c for c in pivot.columns if c in ("2023", "2024", "2025")]
    pivot["n_safras"] = pivot[safra_cols].sum(axis=1)

    # ordena para leitura
    pivot = pivot.sort_values(
        by=["arquivo_base", "n_safras", "coluna"],
        ascending=[True, False, True],
    ).reset_index(drop=True)

    out1 = os.path.join(args.out, "schema_from_readmes.csv")
    out2 = os.path.join(args.out, "schema_readmes_long.csv")
    out3 = os.path.join(args.out, "schema_meta_por_arquivo.csv")

    pivot.to_csv(out1, index=False)
    df[["safra", "arquivo", "coluna"]].to_csv(out2, index=False)
    meta.to_csv(out3, index=False)

    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 200)

    print("\n===== MATRIZ DE COMPATIBILIDADE =====\n")
    print(pivot.to_string(index=False))

    print("\n===== META POR ARQUIVO =====\n")
    print(meta.to_string(index=False))

    print(f"\n[ok] {out1}")
    print(f"[ok] {out2}")
    print(f"[ok] {out3}")
    print(f"[tempo total] {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()