# MITHA - Mini Tomato Hydration Assistant

Projeto desenvolvido na disciplina de **Projeto Integrador IV**, integrando conhecimentos das disciplinas de **Internet das Coisas (IoT)** e **Inteligência Computacional Aplicada**.

O **MITHA (Mini Tomato Hydration Assistant)** propõe o desenvolvimento de um sistema inteligente de irrigação voltado ao cultivo de tomateiro-cereja.

## Objetivo

Desenvolver um sistema inteligente capaz de auxiliar e automatizar a irrigação de tomateiro-cereja por meio da integração entre **sensoriamento IoT**, **dados ambientais** e **técnicas de Inteligência Computacional**.

O sistema deverá monitorar as condições do cultivo, estimar sua necessidade hídrica e utilizar essas informações como apoio à decisão de irrigação.

## Inteligência Computacional

A partir das condições ambientais e do solo, será desenvolvido um modelo de Inteligência Computacional para auxiliar na identificação das situações em que a irrigação deve ser acionada.

Inicialmente, o problema será abordado como uma tarefa de **classificação binária**, considerando os estados:

- Válvula aberta;
- Válvula fechada.

## Dataset

O conjunto de dados utilizado inicialmente no desenvolvimento do modelo está disponível no **Mendeley Data**:

https://data.mendeley.com/datasets/h8sfcf9487/1

O dataset contém dados obtidos em cultivos de tomate e será utilizado como base experimental inicial para o desenvolvimento do modelo de Inteligência Computacional.

> **Observação:** o sistema MITHA tem como cultura-alvo o tomateiro-cereja. O dataset selecionado é proveniente de cultivo de tomate e será utilizado como aproximação inicial durante o desenvolvimento do modelo.

Os dados originais não são versionados neste repositório devido ao tamanho dos arquivos. Para reproduzir as análises, o dataset deve ser baixado diretamente da fonte indicada acima.

## Estrutura do Repositório

```text
.
├── data/
│   ├── raw/                 # Dados originais do Mendeley (não versionados)
│   │   ├── 2023/
│   │   ├── 2024/
│   │   └── 2025/
│   │
│   └── processed/           # Dados integrados e preparados para análise
│
├── notebooks/
│   └── 01_analise_exploratoria.ipynb
│
├── src/
│   └── data_processing/
│       ├── parse_readmes.py
│       ├── check_schema.py
│       ├── merge_m2.py
│       └── eda_descritiva.py
│
├── experiments/             # Experimentos dos modelos de IC
│
├── results/
│   ├── schema/              # Informações sobre a estrutura dos datasets
│   └── statistics/          # Estatísticas descritivas e resultados
│
├── docs/                    # Documentação e entregas da disciplina
│
├── .gitignore
├── requirements.txt
└── README.md
```

## Configuração do Ambiente

### 1. Clonar o repositório

```bash
git clone <URL_DO_REPOSITORIO>
cd projeto-integrador-iv-mitha
```

### 2. Criar um ambiente virtual

No Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar as dependências

```powershell
pip install -r requirements.txt
```

O arquivo `requirements.txt` deve conter as bibliotecas utilizadas pelo projeto, como:

```text
pandas
numpy
matplotlib
jupyter
```

Outras dependências poderão ser adicionadas conforme o desenvolvimento dos modelos de Inteligência Computacional.

## Preparação dos Dados

### 1. Baixar o dataset

Faça o download dos arquivos disponibilizados no Mendeley Data:

https://data.mendeley.com/datasets/h8sfcf9487/1

### 2. Organizar os arquivos

Os arquivos originais devem ser mantidos com seus nomes originais e organizados por safra:

```text
data/
└── raw/
    ├── 2023/
    │   └── arquivos da safra de 2023
    │
    ├── 2024/
    │   └── arquivos da safra de 2024
    │
    └── 2025/
        └── arquivos da safra de 2025
```

Os dados presentes em `data/raw/` não são enviados ao GitHub.

## Pipeline de Processamento

Todos os comandos abaixo devem ser executados a partir da **raiz do repositório**.

### 1. Analisar os READMEs do dataset

O script `parse_readmes.py` extrai informações sobre os arquivos, campos, sensores e características das diferentes safras.

```powershell
python src/data_processing/parse_readmes.py --root data/raw --out results/schema
```

### 2. Verificar a compatibilidade dos CSVs

O script `check_schema.py` compara as colunas existentes nos arquivos das safras de 2023, 2024 e 2025.

```powershell
python src/data_processing/check_schema.py --root data/raw --out results/schema
```

Os resultados dessas verificações são armazenados em:

```text
results/schema/
```

### 3. Gerar os datasets processados

O script `merge_m2.py` integra os dados necessários para o desenvolvimento do modelo, incluindo informações ambientais, de solo, indicadores, estado da válvula e medição de água.

```powershell
python src/data_processing/merge_m2.py --root data/raw --out data/processed
```

Ao final da execução, serão gerados:

```text
data/processed/
├── dataset_m2_2023.csv
├── dataset_m2_2024.csv
└── dataset_m2_2025.csv
```

Esses arquivos possuem os dados das diferentes fontes integrados em uma estrutura adequada para a análise exploratória e desenvolvimento dos modelos.

### 4. Gerar estatísticas descritivas

O script `eda_descritiva.py` calcula estatísticas descritivas para cada safra e também para as variáveis comuns às três safras.

```powershell
python src/data_processing/eda_descritiva.py --root data/processed --out results/statistics
```

Entre os resultados gerados estão:

```text
results/statistics/
├── descritiva_2023.csv
├── descritiva_2024.csv
├── descritiva_2025.csv
├── descritiva_consolidado.csv
├── media_por_safra.csv
└── mediana_por_safra.csv
```

## Análise Exploratória

A análise exploratória dos dados é realizada no notebook:

```text
notebooks/01_analise_exploratoria.ipynb
```

O notebook utiliza como entrada os arquivos presentes em:

```text
data/processed/
```

A análise inclui, entre outros aspectos:

- estrutura e dimensão dos datasets;
- análise de valores ausentes;
- estatísticas descritivas;
- distribuição das variáveis;
- identificação e investigação de possíveis outliers;
- distribuição da variável-alvo `valve_state`;
- comparação entre as diferentes safras;
- análise das relações entre variáveis ambientais, de solo e o estado da válvula.

## Fluxo dos Dados

```text
Dataset original
      │
      ▼
data/raw/
      │
      ├── parse_readmes.py
      │         └──► results/schema/
      │
      ├── check_schema.py
      │         └──► results/schema/
      │
      ▼
  merge_m2.py
      │
      ▼
data/processed/
      │
      ├── eda_descritiva.py
      │         └──► results/statistics/
      │
      ▼
01_analise_exploratoria.ipynb
      │
      ▼
Desenvolvimento dos modelos
```

## Entregas

O desenvolvimento do projeto é organizado de forma incremental ao longo da disciplina.

### M1 - Problem & Dataset

- Definição do problema;
- Seleção e descrição do dataset;
- Definição da hipótese inicial.

### M2 - First Model

- Exploração dos dados;
- Pré-processamento dos dados;
- Definição e implementação do baseline;
- Desenvolvimento do primeiro modelo de Inteligência Computacional;
- Avaliação dos resultados iniciais.

### M3 - Model Validation

- Avaliação experimental;
- Análise de erros;
- Seleção do modelo.

### M4 - IoT Architecture

- Definição dos sensores;
- Comunicação;
- Arquitetura Edge/Cloud.

### M5 - Prototype

- Desenvolvimento do hardware;
- Comunicação;
- Aquisição de dados.

### M6 - Final Demonstration

- Integração do sistema;
- Validação;
- Relatório técnico.

## Equipe

- **Anderson Moura Costa do Nascimento**
- **Matheus Simão Sales**
- **Victor Guedes Alves Teixeira**

## Instituição

**Universidade Federal do Ceará - UFC**
**Curso de Engenharia de Computação**
**Projeto Integrador IV**
