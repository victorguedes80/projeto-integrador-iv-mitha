# v3.1 — estado da execução

O código e os testes de regressão da v3.1 foram corrigidos. Os resultados numéricos
não foram gerados neste pacote porque os arquivos de entrada necessários não estão
presentes:

- `data/processed/dataset_m2_2023.csv`
- `data/processed/dataset_m2_2024.csv`
- `data/processed/dataset_m2_2025.csv`
- CSVs brutos `environmental`, `soil`, `indicators`, `water_meter` e `valve_controller`/
  `water_valve` de cada safra.

Antes de interpretar parâmetros ou classes, regenere os dados processados com
`src/data_processing/merge_m2.py` e execute a análise v3.1. Os arquivos em `v3/`
são resultados da implementação anterior e não foram reutilizados como resultados
corrigidos.

Testes executados: `python -m unittest discover -s tests -v` — 5 testes aprovados.
