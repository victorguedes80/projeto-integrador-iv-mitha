# Metodologia

Dados da linha 3 de 2024, com passo de 10 min ±20 s. As variantes usam os mesmos inícios e exigem histórico contínuo de água e umidade, sem preencher lacunas dessas entradas.

A memória do ARX e a regularização são escolhidas em quatro rodadas temporais com treino crescente. A grade combina atrasos de umidade [1, 2, 3, 4, 5, 6], de água [1, 2, 3, 4, 5, 6, 12, 18] e alpha [0.1, 1.0, 10.0, 100.0]. O critério é o MAE recursivo de 2 e 6 h, com pesos iguais para os horizontes disponíveis e para as rodadas. A última rodada só tem janelas de 2 h, sem irrigação. Imputação das variáveis extras, padronização e coeficientes usam apenas o treino de cada rodada.

Após a escolha, o modelo é reajustado em 01–18/08. A avaliação de 19/08–03/09 é exploratória: esse período já havia sido inspecionado. As janelas se sobrepõem; não são amostras independentes. A configuração salva usa 6 atrasos de umidade, 12 de água e alpha=0.1.

As previsões recebem umidade real apenas na inicialização. Depois usam a própria saída, com água e clima históricos. A condutividade fica congelada no início de cada janela. A chuva de Parma Urbana/ARPAE é observada a cada 15 min e rateada nos intervalos do medidor; não é uma medição no talhão.

Os erros são diferenças absolutas na escala de umidade, não percentuais relativos. Sem cruzamentos reais de 24%, não se valida o acionamento nesse limiar. A estabilidade autorregressiva não comprova resposta física correta nem economia de irrigação.

A comparação com o modelo de duas componentes é retrospectiva, com calibrações de períodos diferentes, e não participa da escolha do ARX.
