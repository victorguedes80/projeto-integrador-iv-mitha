# Dinâmica da umidade do solo em eventos de irrigação

> **Estado atual: código corrigido na v3.1; resultados recalculados ainda pendentes.**
> O pacote recebido não inclui os CSVs brutos nem `data/processed/dataset_m2_{2023,2024,2025}.csv`.
> Portanto, os números e gráficos salvos em `v3/` são apenas resultados históricos da
> implementação anterior e **não devem ser apresentados como resultados da v3.1**.

A v3.1 corrige três pontos que afetam as inferências: estimação AR(1) por máxima
verossimilhança gaussiana completa; busca do pico pós-fechamento por toda a janela
configurada de até 120 min; e critério explícito para a amostra principal, incluindo
resíduos branqueados e uma amostra secundária com parâmetros identificáveis.

## Como reproduzir a v3.1

Primeiro, disponibilize os arquivos brutos do dataset para as safras 2023, 2024 e 2025
(`environmental`, `soil`, `indicators`, `water_meter` e `valve_controller` ou
`water_valve`) em `data/raw/` ou em subpastas por safra. Em seguida execute:

```bash
python src/data_processing/merge_m2.py --root data/raw --out data/processed --seasons 2023 2024 2025
python src/data_processing/auditoria_dinamica.py
python src/utils/resposta_irrigacao.py
python src/data_processing/comparar_versoes.py
python src/view/plotar_dinamica_irrigacao.py
python -m unittest discover -s tests -v
```

A análise e as figuras são gravadas em `results/dinamica_irrigacao/v3_1/` e
`imgs/dinamica_irrigacao/v3_1/`. A auditoria usa a pasta de saída da versão atual
importada por `resposta_irrigacao.py`. O script de comparação também requer que os
resultados históricos de `v2/` estejam presentes.

## Correções aplicadas na v3.1

1. **MLE AR(1) completa.** Antes, `least_squares` minimizava somente a soma dos
   resíduos transformados e o termo do determinante `0,5·log(1−φ²)` era acrescentado
   apenas depois, ao calcular o log-verossímil. Assim, φ e os demais parâmetros não
   maximizavam a mesma função usada no AICc. Agora a otimização conjunta minimiza
   `n·log(SSW/n) − log(1−φ²)`, com σ² perfilada e multistart conjunto em
   parâmetros e φ. Os erros-padrão e correlações são aproximados por informação
   de Fisher/Gauss-Newton, incluindo a contribuição do determinante AR(1).
   O AICc conta os parâmetros do modelo, φ e σ².
2. **Pico da recessão.** A seleção do máximo após o fechamento agora percorre do
   instante de fechamento até `PICO_APOS_FECHAR` (12 passos de 10 min), respeitando
   o início do próximo evento. A implementação anterior limitava a busca a seis
   passos e descartava picos entre 70 e 120 min após fechar.
3. **Amostra principal.** O filtro principal exige dados sem ressalvas e ajuste
   adequado (R², NRMSE e ausência de autocorrelação forte nos resíduos branqueados).
   `amostra_principal_relaxada` preserva o filtro anterior para análise de
   sensibilidade. `amostra_principal_identificavel` é o subconjunto adicional em
   que os parâmetros do modelo escolhido também passam os critérios de
   identificabilidade. Não se confundem qualidade do ajuste e identificação dos
   parâmetros.
4. **Auditoria/regressão.** Foram incluídos testes para recuperação de φ em dados
   sintéticos, branqueamento dos resíduos, janela de pico pós-fechamento e agregação
   do contador acumulado por máximo dentro de cada janela de 10 min.
5. **Regeneração dos dados.** O `merge_m2.py` agrupa `current_volume` com `max()` por
   `(timestamp_10min, line)`, apropriado para leituras de contador acumulado. É
   obrigatório regerar os CSVs processados antes da nova análise; resultados v3
   anteriores não foram recalculados a partir dessa correção.

## Critérios de interpretação

Mesmo após recalcular a v3.1, a interpretação deve respeitar a amostragem de 10 min.
Constantes de tempo menores que esse intervalo não são resolvidas diretamente.
Os tratamentos de 2023, 2024 e 2025 estão descritos na versão 1 do dataset oficial
Mendeley Data (DOI `10.17632/h8sfcf9487.1`). A v3.1 registra esse mapeamento como
documentado, substituindo as inferências antigas: 2024 L3 é controle por limiar de
umidade; 2025 L3 é controle por limiar de umidade, L4 por temperatura foliar e L5
por estratégia baseada em IA. A amostra também deve ser apresentada por safra e
linha, sem generalizar a partir de grupos pequenos ou desbalanceados.

Fonte oficial: <https://data.mendeley.com/datasets/h8sfcf9487/1> (publicada em
09/05/2026; licença CC BY 4.0).

---

## Histórico da v3 (não recalculada)

Os conteúdos abaixo descrevem os resultados arquivados da v3 anterior. Eles foram
mantidos para rastreabilidade, mas devem ser substituídos pelos resultados da v3.1
após regenerar os dados brutos e executar novamente o pipeline.

Pergunta: na subida (resposta à irrigação) e na recessão (após o fechamento), a
umidade do solo se aproxima melhor de um modelo de 1ª ou de 2ª ordem? Qual o
tempo característico?

Fonte: `data/processed/dataset_m2_{2023,2024,2025}.csv` (passo de 10 min).

## Como reproduzir

```bash
python src/utils/resposta_irrigacao.py           # análise   -> results/dinamica_irrigacao/v3/  (~3,5 min)
python src/data_processing/auditoria_dinamica.py # auditoria -> results/dinamica_irrigacao/v3/auditoria/
python src/data_processing/comparar_versoes.py   # v2 × v3   -> results/dinamica_irrigacao/v3/comparacao_v2_v3*.csv
python src/view/plotar_dinamica_irrigacao.py     # figuras   -> imgs/dinamica_irrigacao/v3/
```

## Versões

| Versão | Pasta | Situação |
|---|---|---|
| v1 | `v1/` | Preliminar. Mantida sem alterações. |
| v2 | `v2/` | 1ª revisão (`recomendacoes_dinamica_umidade_solo.txt`). Mantida sem alterações. |
| **v3** | `v3/` | Histórica. Resultados anteriores à correção da MLE AR(1), do pico de recessão e do critério amostral. |
| **v3.1** | `v3_1/` | Código corrigido; execução dos resultados depende da regeneração dos CSVs processados a partir dos brutos. |

## v3

### Arquivos

| Arquivo | Conteúdo |
|---|---|
| `eventos_todos.csv` | Todos os eventos detectados: status e motivo; métricas sem modelo; parâmetros ± erro-padrão, R², RMSE, ρ1 e AICc de cada modelo, com erro i.i.d. e com erro AR(1) (prefixo `…ar`, ex. `M1qar_tau`); classes por AICc AR(1), i.i.d. e n efetivo; qualidade em três dimensões (`qual_dados`, `qual_ajuste`, `qual_ident` + flags); `amostra_principal`. |
| `eventos_descartados.csv` | Eventos descartados e o motivo. |
| `residuos.csv` | Dados, ajuste e resíduo por evento, fase e modelo. |
| `resumo_por_safra.csv`, `resumo_por_safra_linha.csv` | Contagens (zero = nenhum evento) e medianas/quartis (NaN = sem estimativa). |
| `sensibilidade_amostra.csv` | Classes e parâmetros na amostra principal, em todos os eventos com modelo de vazão e só nos com vazão reconstruída. |
| `comparacao_v2_v3.csv`, `comparacao_v2_v3_resumo.csv` | Comparação evento a evento entre as versões. |
| `config_execucao.json` | Regras, limiares, mapeamento de tratamentos e grau de confiança. |
| `auditoria/` | Lacunas, hidrômetro, umidade e `valve_state`. |

Figuras em `imgs/dinamica_irrigacao/v3/`: `resumo.png`, `residuos_exemplos.png` (resíduos × tempo e ACF), `eventos_<ano>.pdf` (cada evento ajustado, com flags) e `descartados.pdf` (tabela de motivos + cada evento descartado).

### Modelos

**Principal — vazão medida como entrada.** Cada passo de 10 min do hidrômetro é um pulso de vazão (normalizada pela vazão típica da linha). A resposta é a superposição das respostas ao degrau, com atraso θ contínuo. O ajuste cobre o evento inteiro: 1 h antes da abertura até o fim da recessão (≤ 12 h). Todos os modelos têm baseline com deriva linear (y0 + b·t).

| Modelo | Função de transferência | Leitura física |
|---|---|---|
| M1q | K e^{-θs} / (τs + 1) | um reservatório |
| M2q | K e^{-θs} / ((τ1 s + 1)(τ2 s + 1)) | dois reservatórios em série |
| M2p | [K1/(τa s + 1) + K2/(τb s + 1)] e^{-θs} | dois reservatórios em paralelo (2ª ordem com zero) |

M2q e M2p contêm M1q como caso particular e partem da solução de M1q, de modo que nunca ajustam pior.

**Aproximação — degrau.** Os modelos FOPDT/SOPDT da v2 são mantidos, mas só na janela compatível com a hipótese de degrau: da abertura até o fechamento.

**Recessão (descritiva).** Exponencial simples × dupla, após o fechamento.

### Estatística

- **Critério principal:** AICc com erro AR(1) explícito, por máxima verossimilhança (Prais-Winsten). Depois do AR(1), o resíduo branqueado tem ρ1 mediano ≈ 0.
- **Sensibilidade:** AICc com erro i.i.d. e AICc com n efetivo (aproximação).
- **Contagem de parâmetros:** a variância residual (e φ, no AR(1)) entra no k do AICc.
- **Limiar:** |ΔAICc| > 2.

**Classes:**

| Classe | Critério |
|---|---|
| 1a ordem | M1q preferido, ou o 2º polo/reservatório é degenerado |
| 1 polo + componente rápida | M2p preferido, as duas componentes contribuem (5–95% da resposta na janela), mas τa < 10 min. O reservatório rápido não é resolvido: funciona como resposta quase instantânea (um zero), e não como um 2º polo mensurável. |
| 2a ordem (série / com zero) | M2q ou M2p preferido, com o 2º polo identificável (≥ 10 min) |
| indistinto | |ΔAICc| ≤ 2, ou o modelo complexo vence mas com parâmetro degenerado |

### Avaliação da 2ª revisão

| Item | Procede? | O que foi feito |
|---|---|---|
| 1. Vazão não entra no modelo | **Sim** | Modelos com a vazão medida como entrada (M1q, M2q, M2p), ajustados no evento inteiro. O degrau virou aproximação, restrita até o fechamento. |
| 2. Qualidade em três dimensões | **Sim** | `qual_dados` (interpolação, picos corrigidos, vazão reconstruída/desconhecida, contador corrigido), `qual_ajuste` (R², RMSE/ΔY, resíduo branqueado) e `qual_ident` (limites, erro-padrão relativo > 100%, |correlação| > 0,95, τ < 10 min) para M1q, M2q e M2p. Amostra principal = dados bons e ajuste com R²/NRMSE bons. |
| 3. AICc / n efetivo | **Sim** | AR(1) explícito virou o critério principal; i.i.d. e n efetivo ficam como sensibilidade; variância e φ contados em k. |
| 4. Lacunas na vazão | **Sim, com um refinamento** | A vazão distribuída sobre lacuna é marcada e fica fora da amostra principal, com análise separada em `sensibilidade_amostra.csv`. Vazão ausente nunca é tratada como zero: a recessão para em vazão desconhecida e o modelo de entrada exige vazão conhecida. **Refinamento:** lacuna com Δcontador = 0 não é ambígua (o contador é monotônico, então a vazão foi zero) e não é marcada como reconstruída. Proteção contra janela vazia no pico da recessão. |
| 5. Bruto / corrigido / interpolado | **Sim, e revelou um bug** | Colunas `umid_bruta`, `umid_corrigida`, `umid_obs` (original válida e não substituída), `umid_interp` e `umid`. Ao separá-las, apareceu um **bug presente na v1 e na v2**: o filtro de Hampel (mediana móvel de 5) "corrigia" o início das subidas reais, porque num degrau a mediana ainda contém o baseline. Eram 321 correções durante irrigações, mediana de 1,1 p.p. O Hampel foi **substituído** por um detector de pico isolado (desvio dos dois vizinhos na mesma direção, vizinhos concordantes e um lado plano), que preserva subidas e picos reais. Restam 53 correções durante irrigações, todas falhas de 4–6 p.p. por uma amostra. |
| 6. NaN nos resumos | **Sim** | Só as contagens recebem zero; medianas e percentis sem estimativa ficam NaN. |
| 7. Figuras | **Sim** | Denominadores e descartados no título; AICc AR(1)/i.i.d./n efetivo lado a lado; leituras corrigidas e interpoladas e vazão reconstruída diferenciadas; τ lenta não identificável destacada; resíduos × tempo e ACF; PDF de descartados; safra sem eventos tratada. |
| 8. Tratamentos | **Parcial na v3; corrigido na v3.1** | A v3 usava inferências e não tinha a documentação de 2025 incorporada. A v3.1 utiliza os regimes por linha descritos na página oficial do dataset para as três safras. |

### Resultados v3

**Contagem:** 260 eventos detectados, 66 descartados, 191 com modelo de vazão e **77 na amostra principal**.

A amostra principal se concentra na linha 3: 27 de 37 eventos em 2024 e 27 de 27 em 2025. É a linha de pulsos curtos e frequentes (A(sh)? em 2024).

**Evento completo, com a vazão como entrada (amostra principal, n = 77):**

| Critério | 1a ordem | 1 polo + comp. rápida | 2a ordem (com zero) | indistinto |
|---|---|---|---|---|
| AICc AR(1) (principal) | 3 | 46 | 22 | 6 |
| AICc i.i.d. | 2 | 46 | 23 | 6 |
| AICc n efetivo | 25 | 40 | 4 | 8 |

- **1 polo + componente rápida** (medianas): atraso θ ≈ 14 min; cerca de 42% da resposta é quase instantânea (< 10 min) e o restante passa por um polo lento de τ ≈ 3,4 h (205 min).
- **2a ordem com zero** (medianas): θ ≈ 7 min, τa ≈ 22 min, τb ≈ 8,7 h (521 min), e as duas componentes respondem por partes iguais.
- **1ª ordem pura (M1q):** com uma única τ para a subida e para a recessão, chega a τ ≈ 2 h e deixa resíduos fortemente correlacionados (ρ1 mediano 0,44). Ela não descreve o evento inteiro.

**Sem modelo** (amostra principal): atraso até 5% da resposta = 21 min; t63 = 31 min.

**Degrau até o fechamento (aproximação, n = 113):** 1a ordem em 89, 2a ordem em 14 e indistinto em 10. Medianas τ ≈ 35 min e θ ≈ 36 min.

**Recessão (n = 184):**

| Critério | dupla | dupla (τ lenta não identificável) | simples | indistinto |
|---|---|---|---|---|
| AICc AR(1) | 113 | 16 | 52 | 3 |
| AICc n efetivo | 76 | 14 | 89 | 5 |

Nas recessões duplas, a τ rápida tem mediana ≈ 20 min e a lenta ≈ 4 h. A exponencial simples dá τ ≈ 68 min.

**Sensibilidade** (`sensibilidade_amostra.csv`): em todos os 191 eventos com modelo de vazão, a 1ª ordem pura é minoria no AR(1) (34 eventos) e no i.i.d. (15). Mas, pelo critério aproximado de n efetivo, ela vira **maioria** (114 de 191). A escolha do modelo de erro pesa na conclusão.

**Identificabilidade:** 65 dos 77 eventos principais têm alguma ressalva. Na maioria é correlação entre parâmetros ou erro-padrão alto de θ: atraso, componente rápida e τ trocam entre si na resolução de 10 min. A **classe** (estrutura do modelo) é bem mais estável que os **valores** individuais dos parâmetros.

### Leitura (v3)

1. **Na subida isolada**, até o fechamento, a resposta é bem aproximada por 1ª ordem com atraso, como nas versões anteriores.
2. **No evento completo, com a vazão real como entrada**, um único reservatório de 1ª ordem não descreve ao mesmo tempo a subida rápida e a descida lenta. O padrão preferido é uma resposta rápida (abaixo da resolução de 10 min, ou com τ ≈ 20 min) somada a um reservatório lento de horas. Isso equivale a uma estrutura de 2ª ordem com zero (dois reservatórios em paralelo), em que muitas vezes só o polo lento é mensurável.
3. A conclusão vale **dentro da resolução de 10 min, dos dados processados (média 15/30 cm em 2024/2025) e de uma amostra principal dominada pela linha 3**. Não é identificação definitiva da física do solo.
4. Pelo critério de n efetivo, a 1ª ordem vence na maioria dos 191 eventos (114) e em 25 dos 77 principais. A conclusão depende do modelo de erro. O AR(1) explícito é o mais defensável dos três: ele modela a autocorrelação em vez de só descontar amostras, e o resíduo branqueado fica com ρ1 ≈ 0. Mesmo assim, a escolha entre 1ª ordem e "1 polo + componente rápida" deve ser tratada como sensível ao critério.

### Mudanças de resultado entre v2 e v3

`comparacao_v2_v3_resumo.csv`:

- Os 191 eventos ajustados são os mesmos nas duas versões.
- Na janela de degrau, a classificação é estável (86 eventos "1a ordem" em ambas).
- O que muda é a pergunta: com a vazão como entrada e o evento completo, 71 eventos "1a ordem" da v2 passam a "1 polo + componente rápida" e 37 a "2a ordem com zero".
- A correção do filtro de picos mudou pouco o t63 (diferença mediana ≈ 0 min).

### Limitações (v3)

- A correção do `merge_m2.py` só tem efeito depois de regerar o processado a partir dos dados brutos (ainda não feito).
- Em 2024/2025, a umidade é a média de 15 e 30 cm; a análise por profundidade exige os dados brutos.
- Os tratamentos de 2023/2024 são prováveis e os de 2025 são desconhecidos.
- A amostra principal é desbalanceada entre linhas (dominada pela L3).
- A deriva linear do baseline é uma simplificação da evapotranspiração diurna.
- Algumas recessões têm novos aumentos de umidade sem vazão registrada (chuva ou vazão não medida), que nenhum modelo de entrada explica.

## v2 (histórico)

> A v2 foi substituída pela v3. Os números abaixo são da v2 e foram afetados pelo bug do filtro de Hampel (ver v3).

### Arquivos da v2

| Arquivo | Conteúdo |
|---|---|
| `eventos_todos.csv` | Todos os eventos detectados, com status (`ajustado`/`descartado`), motivo, qualidade (`boa`/`ressalva`), flags, parâmetros ± erro-padrão, R², RMSE, ρ1, Durbin-Watson, AICc convencional e com n efetivo, e classes. |
| `residuos.csv` | Dados, ajuste e resíduo de cada modelo em cada evento. |
| `resumo_por_safra.csv`, `resumo_por_safra_linha.csv` | Eventos detectados, descartados, ajustados e de qualidade boa; medianas e quartis; contagem das classes. |
| `config_execucao.json` | Regras e limiares usados e data da execução. |
| `auditoria/lacunas.csv` | Início, fim e duração de cada lacuna, por tipo. |
| `auditoria/hidrometro.csv`, `umidade.csv`, `valve_state.csv` | Auditoria das variáveis. |

### Avaliação da 1ª revisão (v1 → v2)

| Item | Procede? | O que foi verificado / feito |
|---|---|---|
| 3.1 Semântica do hidrômetro | **Sim** | `current_volume` é um **contador acumulado**: não-decrescente em mais de 99,9% das leituras, então `diff()` está correto. Mas o `merge_m2.py` **somava** as leituras da mesma janela de 10 min, o que dobra o contador. Aparecem valores exatamente 2× (16659 → 33318; 68711 → 137422). **Corrigido** em `merge_m2.py` para `max()`; é preciso regerar o processado a partir do bruto. Na v2 esses picos são removidos por mediana móvel, e as pequenas quedas (±1) são absorvidas por um envelope monotônico. |
| 3.2 Interpolação | **Sim** | `interpolate(limit=2)` do pandas preenche as 2 primeiras amostras de lacunas **longas**. Agora só se interpolam lacunas internas de até 2 amostras, sempre marcadas (`umid_interp`). A vazão só é calculada entre leituras reais separadas por até 3 passos. |
| 3.3 Lacunas | **Sim** | A maior lacuna é de 17 dias em 2024 (07/07–24/07); as lacunas são comuns a todas as linhas. Como a grade do processado vem do sensor ambiental, a lacuna pode não existir no bruto do solo. Nenhuma janela de subida ou recessão atravessa lacuna; a recessão termina antes de qualquer NaN ou nova vazão. |
| 3.4 `cruza()` | **Sim, em parte** | Até o pico, os níveis de 10% a 90% sempre são atingidos. O problema real era `j == 0` quando a série já começa acima do nível. Agora retorna NaN, com interpolação linear entre amostras. |
| 3.5 Seleção por R² | **Sim** | Todos os eventos ficam registrados, com motivo de descarte. `sem_resposta_fisica` é separado de `lacuna_na_janela`, `poucos_pontos`, `hidrometro_glitch` e `irrigacao_curta`. A qualidade usa R², parâmetros no limite e monotonicidade. |
| 3.6 Autocorrelação | **Sim** | O ρ1 mediano dos resíduos é ≈ 0,58, então o AICc convencional é otimista. A v2 usa um n efetivo n(1−ρ)/(1+ρ), com ρ estimado nos resíduos do modelo **mais flexível**. Com ρ do modelo simples, o próprio desajuste reduziria o n e mascararia a diferença. |
| 3.7 Identificabilidade | **Sim** | Parâmetros no limite são sinalizados; τ < 10 min é marcado; a correlação τ–θ é calculada (mediana −0,66, ou seja, há troca entre atraso e constante). M2 com τ2 < 10 min é considerado **degenerado**: o 2º polo não é identificável com amostragem de 10 min. |
| 4 Recessão | **Sim** | Começa no máximo após o fechamento; para antes de nova vazão ou lacuna; exige ≥ 3 h e amplitudes ≥ 0. Degenerações sinalizadas: componente desprezível (< 5%), τ rápida < 10 min, τ lenta > 2× a janela ou no limite. |
| 5 Estratificação | **Sim** | Resultados por safra, linha e tratamento. Os tratamentos foram identificados pela Fig. 1 de Oddi et al. (2026) e pelos volumes aplicados (mapeamento **provável**, ver tabela abaixo). |
| 6 Sensores | **Sim** | Umidade = 0 (sequências de até ~8 h em 2024) e 338% (2024 L4, 28/06) foram tratadas como inválidas: a faixa do EM500-SMTC é 0–100%. `valve_state` não serve como detector **universal**: em 2023 fica em 1 em 94–100% do tempo, com ou sem vazão; em 2024 é coerente (=1 em 80–92% dos passos com vazão e ≈0 sem vazão); em 2025 varia por linha (11% em L1, 31% em L4, 77–100% nas demais). Por isso os eventos são detectados pelo hidrômetro. A média das profundidades de 15/30 cm (2024/2025) não pode ser desfeita sem os dados brutos; 2023 tem um único sensor a 20 cm. |

### Tratamentos registrados na v3 (histórico; substituídos na v3.1)

A tabela abaixo documenta apenas o mapeamento disponível quando a v3 foi gerada.
A descrição oficial do dataset foi publicada em 09/05/2026 e agora confirma os
regimes das três safras; consulte o resumo da v3.1 no início deste README.

| Safra | L1 | L2 | L3 | L4 | L5 | Evidência |
|---|---|---|---|---|---|---|
| 2023 | I100 | I60 | I30 | — | — | Volumes 1 : 0,66 : 0,39 |
| 2024 | Î80 | Î60 | A(sh) | Î100 | Î30 | Fig. 1; volumes 0,71 : 0,56 : – : 1 : 0,32; L3 com pulsos curtos e frequentes ("sip irrigation") |
| 2025 | ? | ? | ? | ? | ? | Não descrito no artigo |

### Resultados v2 (eventos de qualidade boa)

260 eventos detectados, 191 ajustados, 162 de qualidade boa.

**Subida**

| Medida | Mediana |
|---|---|
| Atraso até 5% da resposta | 23 min |
| t63 | 41 min |
| Constante τ (1ª ordem) | 23 min |
| Atraso θ (1ª ordem) | 26 min |

Classificação dos 162 eventos:

| Critério | 1ª ordem | 2ª ordem | Indistinto |
|---|---|---|---|
| AICc convencional | 136 | 16 | 10 |
| n efetivo + 2º polo identificável | 152 | 4 | 6 |

- Em 140 dos 152 eventos de "1ª ordem", o modelo de 2ª ordem degenera (τ2 < 10 min).
- Isso significa que **não há evidência de um 2º polo acima da resolução de 10 min**, e não que o sistema físico seja de 1ª ordem.
- Em 30 eventos, τ ficou abaixo de 10 min (no limite da resolução).

**Recessão** (156 eventos)

| Critério | Simples | Dupla | Indistinto |
|---|---|---|---|
| AICc convencional | 42 | 106 | 8 |
| n efetivo + checagem de degeneração | 84 | 70 (54 identificáveis + 16 com τ lenta não identificável) | 2 |

- A recessão dupla domina em 2023 (manual, sensor único a 20 cm). Em 2024, a exponencial simples domina.
- Nas recessões duplas, a τ rápida tem mediana de 39 min e a τ lenta, quando identificável, ≈ 5 h. A exponencial simples tem τ mediana ≈ 2,7 h.

**Leitura:** a 1ª ordem com atraso é a aproximação mais adequada para a subida
**dentro da resolução de 10 min**. A evidência de duas escalas na recessão
existe, mas depende da safra e do critério. Isso é evidência estatística, não
identificação de mecanismos físicos.

### Limitações registradas na v2

- Os dados brutos não estão disponíveis nesta execução. A correção do `merge_m2.py` só tem efeito após regerar o processado.
- Em 2024/2025, a umidade é a média de 15 e 30 cm.
- Os tratamentos de 2023/2024 são inferidos e os de 2025 são desconhecidos.
- Os resíduos continuam autocorrelacionados mesmo no modelo de 2ª ordem (ρ1 ≈ 0,6). Há estrutura não capturada por modelos lineares de degrau, como a vazão não constante e a não linearidade do solo.
