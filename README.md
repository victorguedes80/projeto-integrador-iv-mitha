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

https://data.mendeley.com/datasets/35wh56287y/2

O dataset contém dados obtidos em um cultivo de tomate e será utilizado como base experimental inicial para o desenvolvimento do modelo de Inteligência Computacional.

> **Observação:** o sistema MITHA tem como cultura-alvo o tomateiro-cereja. O dataset selecionado é proveniente de cultivo de tomate e será utilizado como aproximação inicial durante o desenvolvimento do modelo.

## Estrutura do Repositório

```text
.
├── data/           # Dados utilizados no projeto
├── notebooks/      # Exploração dos dados e desenvolvimento dos modelos
├── src/            # Código-fonte reutilizável
├── experiments/    # Experimentos realizados
├── results/        # Métricas, gráficos e resultados
└── docs/           # Documentação e entregas do projeto
