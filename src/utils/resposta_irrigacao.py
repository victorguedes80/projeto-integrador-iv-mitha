"""Dinâmica da umidade do solo em eventos de irrigação (dados da Itália / Mendeley) — v3.1.

v3.1 = correções estatísticas e de seleção sobre a implementação v3:

1. A VAZÃO MEDIDA É A ENTRADA DOS MODELOS PRINCIPAIS. Cada intervalo de 10 min
   do hidrômetro é um pulso retangular de vazão (normalizada pela vazão típica
   da linha); a resposta é a superposição das respostas ao degrau, com atraso θ
   contínuo. Assim a irrigação tem duração finita e vazão variável, e o
   ajuste cobre o evento inteiro (subida + recessão até 12 h):
     M1q   1ª ordem:              τ dy/dt = -(y - ȳ) + K q(t-θ)
     M2q   2ª ordem em série:     K / ((τ1 s+1)(τ2 s+1)) · e^{-θs}
     M2p   2ª ordem com zero:     [K1/(τa s+1) + K2/(τb s+1)] · e^{-θs}  (dois reservatórios)
   ȳ(t) = y0 + b·t (deriva lenta comum a todos os modelos).
   Os modelos de degrau da v2 (M1/M2) são mantidos só como APROXIMAÇÃO, numa
   janela compatível com a hipótese de degrau (da abertura até o fechamento).
2. Qualidade em três dimensões separadas: dados, ajuste, identificabilidade.
3. Comparação estatística principal: AICc com erro AR(1) explícito (máxima
   verossimilhança, transformação de Prais-Winsten). AICc com erro i.i.d. e
   AICc com n efetivo ficam como análises de sensibilidade. A variância
   residual (e φ no AR(1)) entra na contagem de parâmetros.
4. Vazão reconstruída sobre lacunas fica fora da amostra principal (análise de
   sensibilidade separada); vazão ausente nunca é tratada como zero.
5. Leitura bruta, corrigida, interpolada e observada são separadas. O filtro de
   Hampel foi SUBSTITUÍDO por um detector de pico isolado: o Hampel achatava o
   início das subidas reais (bug presente na v1 e na v2).
6. Resumos preservam NaN nas métricas; só contagens recebem zero.

Recessão (após o fechamento, descritiva): E1 = y∞ + A e^{-t/τ};
E2 = y∞ + A1 e^{-t/τr} + A2 e^{-t/τl}.

Uso: python src/utils/resposta_irrigacao.py
"""

from datetime import datetime, timezone
from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd
from scipy.optimize import least_squares, minimize
from scipy.optimize._numdiff import approx_derivative

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[2]
VERSAO = "v3_1"
SAIDA = RAIZ / "results" / "dinamica_irrigacao" / VERSAO

# ------------------------------------------------------------- regras
REGRAS = dict(
    DT_MIN=10,                 # passo de amostragem (min)
    MAX_GAP_INTERP=2,          # nº máx. de amostras faltantes interpoladas (umidade)
    MAX_GAP_VAZAO=3,           # Δcontador distribuído entre leituras separadas por até 3 passos (marcado como reconstruído)
    JANELA_CONTADOR=3,         # mediana móvel centrada de 2·3+1 passos
    TOL_CONTADOR=200,          # desvio mínimo (unid. do hidrômetro) p/ pico ou reset
    GAP_EVENTO=2,              # passos sem vazão (ou sem dado) que ainda unem dois pulsos
    DUR_MIN_EVENTO=3,          # passos com vazão (30 min) para analisar o evento
    FATOR_GLITCH_VAZAO=5,      # vazão > 5× mediana da linha = falha do hidrômetro
    BASELINE_MIN=60,           # janela de baseline antes da abertura (min)
    PICO_APOS_FECHAR=12,       # passos após o fechamento para procurar o pico
    DY_MIN=1.5,                # aumento mínimo (p.p.) para considerar resposta
    N_MIN_DEGRAU=6,            # pontos mínimos para o ajuste por degrau (aproximação)
    N_MIN_EVENTO=12,           # pontos mínimos para os modelos com vazão
    FRAC_INTERP_MAX=0.2,       # fração máx. de pontos interpolados numa janela (senão descarta)
    FRAC_INTERP_BOA=0.1,       # acima disso: qualidade de dados com ressalva
    PICOS_MAX_BOA=1,           # picos isolados corrigidos tolerados na janela p/ dados "bons"
    REC_MAX=72,                # recessão até 12 h
    REC_N_MIN=18,              # recessão com ≥ 3 h
    RES_TEMPORAL=10,           # constantes < 10 min: abaixo da resolução
    R2_BOA=0.9,
    NRMSE_BOA=0.10,            # RMSE / ΔY
    SE_REL_MAX=1.0,            # erro-padrão relativo > 100 % = parâmetro mal identificado
    CORR_MAX=0.95,             # |correlação| entre parâmetros acima disso = mal identificado
    DAICC=2.0,
)
DT = REGRAS["DT_MIN"]

# Tratamentos documentados na descrição oficial do dataset Mendeley Data.
# DOI: 10.17632/h8sfcf9487.1 (versão 1, publicada em 09/05/2026).
# Os rótulos percentuais representam frações da recomendação Irriframe (R).
TRATAMENTOS = {
    2023: {1: "I100", 2: "I60", 3: "I30"},
    2024: {1: "I80", 2: "I60", 3: "limiar_umidade_solo", 4: "I100", 5: "I30"},
    2025: {1: "I100", 2: "I30", 3: "limiar_umidade_solo",
           4: "limiar_temperatura_foliar", 5: "estrategia_IA"},
}
CONFIANCA = {
    2023: "documentado (descrição oficial do dataset Mendeley)",
    2024: "documentado (descrição oficial do dataset Mendeley)",
    2025: "documentado (descrição oficial do dataset Mendeley)",
}


def tratamento(ano, linha):
    return TRATAMENTOS.get(ano, {}).get(int(linha), "não identificado")


def tratamento_confianca(ano):
    return CONFIANCA.get(ano, "não documentado")


# ------------------------------------------------------------- limpeza
def runs(mask):
    """(início, fim_inclusivo) de cada sequência True."""
    m = np.r_[False, np.asarray(mask, bool), False]
    d = np.diff(m.astype(int))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0] - 1))


def interp_curto(s, max_gap):
    """Interpola linearmente só lacunas internas com ≤ max_gap amostras."""
    s = s.copy()
    full = s.interpolate(limit_area="inside")
    for a, b in runs(s.isna().values):
        if b - a + 1 <= max_gap and a > 0 and b < len(s) - 1:
            s.iloc[a:b + 1] = full.iloc[a:b + 1]
    return s


def corrigir_picos(s, n_sig=5.0, piso=1.0):
    """Remove picos/quedas ISOLADOS de uma amostra (falha de leitura do sensor).

    Substitui a v1/v2, que usava filtro de Hampel (mediana móvel de 5): aquele
    filtro também "corrigia" o início das subidas reais — num degrau, a mediana
    da janela ainda contém o baseline —, atrasando a resposta e inflando θ.

    Critério: x_i se afasta dos DOIS vizinhos na mesma direção (d1, d2 com o
    mesmo sinal), por mais que o limiar, os vizinhos concordam entre si
    (|x_{i+1} - x_{i-1}| < metade do menor salto) e pelo menos um dos lados é
    plano (|x_{i-1} - x_{i-2}| ou |x_{i+2} - x_{i+1}| < metade do menor salto).
    Uma subida/descida monotônica ou um pico real de irrigação (subindo antes e
    descendo depois) não satisfaz o critério. Limiar = max(piso, n_sig · 1,4826 ·
    MAD das diferenças da linha). O ponto é substituído pela média dos vizinhos.
    """
    x = s.values.astype(float)
    dif = np.diff(x)
    mad = np.nanmedian(np.abs(dif - np.nanmedian(dif)))
    thr = max(piso, n_sig * 1.4826 * mad)
    xm, xp = np.r_[np.nan, x[:-1]], np.r_[x[1:], np.nan]
    xmm, xpp = np.r_[np.nan, np.nan, x[:-2]], np.r_[x[2:], np.nan, np.nan]
    d1, d2 = x - xm, x - xp
    menor = np.minimum(np.abs(d1), np.abs(d2))
    lado_plano = (np.abs(xm - xmm) < 0.5 * menor) | (np.abs(xpp - xp) < 0.5 * menor)
    pico = ((np.sign(d1) == np.sign(d2)) & (menor > thr)
            & (np.abs(xp - xm) < 0.5 * menor) & lado_plano)
    pico = np.nan_to_num(pico, nan=False).astype(bool)
    y = x.copy()
    y[pico] = 0.5 * (xm[pico] + xp[pico])
    return pd.Series(y, index=s.index), pd.Series(pico, index=s.index)


def limpar_contador(v, w, tol):
    """Limpa o contador acumulado do hidrômetro.

    1. zero após valores positivos -> leitura inválida;
    2. pico/queda isolados (ex.: valor dobrado pela soma de leituras duplicadas
       no merge) -> desvio da mediana móvel centrada > max(tol, 10 %) -> inválido;
    3. quedas grandes PERSISTENTES restantes = reset/troca do contador -> rebase;
    4. pequenas quedas (ruído de ±1 unidade) são absorvidas pelo envelope
       monotônico (cummax), sem criar vazão espúria.
    """
    x = v.values.astype(float).copy()
    motivo = np.array([""] * len(x), dtype=object)
    pm = pd.Series(x).cummax().shift(1).values
    z = (x == 0) & (pm > 0)
    x[z] = np.nan; motivo[z] = "zero"
    med = pd.Series(x).rolling(2 * w + 1, center=True, min_periods=3).median().values
    dev = np.abs(x - med) > np.maximum(tol, 0.10 * np.abs(med))
    x[dev] = np.nan; motivo[dev] = "pico"
    ult, offset = None, 0.0
    for i in np.where(np.isfinite(x))[0]:
        val = x[i] + offset
        if ult is not None and val < ult - tol:
            offset += ult - val; val = ult; motivo[i] = "reset"
        val = max(val, ult) if ult is not None else val
        x[i] = ult = val
    return pd.Series(x, index=v.index), pd.Series(motivo, index=v.index)


def vazao_do_contador(vv, max_gap):
    """Δvolume por passo entre leituras válidas.

    Entre leituras consecutivas: medição. Entre leituras separadas por 2..max_gap
    passos: o Δ total é conhecido mas a distribuição no tempo NÃO — os passos são
    preenchidos com a média e marcados como reconstruídos (só se Δ > 0: com
    Δ = 0 o contador monotônico garante vazão zero). Lacunas maiores: NaN
    (vazão desconhecida, nunca zero).
    """
    x = vv.values
    q = np.full(len(x), np.nan)
    rec = np.zeros(len(x), bool)
    idx = np.where(np.isfinite(x))[0]
    for i0, i1 in zip(idx[:-1], idx[1:]):
        n = i1 - i0
        if n <= max_gap:
            q[i0 + 1:i1 + 1] = (x[i1] - x[i0]) / n
            # Δ = 0 numa lacuna: contador não-decrescente => vazão zero em todos os passos (não ambíguo)
            rec[i0 + 1:i1 + 1] = n > 1 and x[i1] - x[i0] > 0
    return pd.Series(q, index=vv.index), pd.Series(rec, index=vv.index)


def carregar(ano):
    """Gera (linha, DataFrame limpo em grade de 10 min) para a safra.

    Colunas de umidade:
      umid_bruta    leitura original do sensor (NaN se não houve registro)
      umid_invalida leitura fora da faixa física (0 ou > 100 %)
      umid_corrigida leitura detectada como pico isolado e substituída pela média dos vizinhos
      umid_obs      leitura original válida e NÃO substituída
      umid_interp   valor preenchido por interpolação (lacuna curta)
      umid          série usada na análise
    """
    df = pd.read_csv(RAIZ / "data" / "processed" / f"dataset_m2_{ano}.csv",
                     parse_dates=["timestamp_10min"])
    for linha, g in df.groupby("line"):
        g = g.set_index("timestamp_10min").sort_index()
        g = g[~g.index.duplicated()]
        obs = pd.Series(True, index=g.index)
        g = g.asfreq(f"{DT}min")
        g["registro_existe"] = obs.reindex(g.index, fill_value=False)

        s = g["soil_humidity"].astype(float)
        g["umid_bruta"] = s
        g["umid_invalida"] = (s <= 0) | (s > 100)
        s = s.where(~g["umid_invalida"])
        sh, spk = corrigir_picos(s)
        g["umid_corrigida"] = spk
        g["umid_obs"] = s.notna() & ~spk
        g["umid"] = interp_curto(sh, REGRAS["MAX_GAP_INTERP"])
        g["umid_interp"] = g["umid"].notna() & s.isna()

        vv, mot = limpar_contador(g["water_volume"], REGRAS["JANELA_CONTADOR"], REGRAS["TOL_CONTADOR"])
        g["vol_limpo"], g["vol_motivo"] = vv, mot
        g["vazao"], g["vazao_reconstruida"] = vazao_do_contador(vv, REGRAS["MAX_GAP_VAZAO"])
        yield int(linha), g


# ------------------------------------------------------------- modelos de degrau (aproximação)
def fopdt(p, t):
    y0, K, tau, th = p
    s = np.clip(t - th, 0, None)
    return y0 + K * (1 - np.exp(-s / tau))


def sopdt(p, t):
    y0, K, t1, r, th = p          # τ2 = r·τ1, 0 < r ≤ 1
    t2 = r * t1
    s = np.clip(t - th, 0, None)
    if abs(t1 - t2) < 1e-6 * t1:
        h = 1 - (1 + s / t1) * np.exp(-s / t1)
    else:
        h = 1 - (t1 * np.exp(-s / t1) - t2 * np.exp(-s / t2)) / (t1 - t2)
    return y0 + K * h


# ------------------------------------------------------------- modelos com vazão medida
def _degrau1(s, tau):
    return np.where(s > 0, 1 - np.exp(-np.clip(s, 0, None) / tau), 0.0)


def _degrau2s(s, t1, t2):
    sp = np.clip(s, 0, None)
    if abs(t1 - t2) < 1e-6 * t1:
        h = 1 - (1 + sp / t1) * np.exp(-sp / t1)
    else:
        h = 1 - (t1 * np.exp(-sp / t1) - t2 * np.exp(-sp / t2)) / (t1 - t2)
    return np.where(s > 0, h, 0.0)


class Entrada:
    """Pulsos de vazão (u_j constante em (ini_j, fim_j]) e superposição."""

    def __init__(self, ini, fim, u):
        self.ini, self.fim, self.u = np.asarray(ini), np.asarray(fim), np.asarray(u)

    def resposta(self, t, degrau, th):
        T = t[:, None] - th
        return ((degrau(T - self.ini[None, :]) - degrau(T - self.fim[None, :])) * self.u[None, :]).sum(1)


def m1q(p, t, e):
    y0, b, K, tau, th = p
    return y0 + b * t + K * e.resposta(t, lambda s: _degrau1(s, tau), th)


def m2q(p, t, e):
    y0, b, K, t1, r, th = p
    return y0 + b * t + K * e.resposta(t, lambda s: _degrau2s(s, t1, r * t1), th)


def m2p(p, t, e):
    y0, b, K1, ta, K2, d, th = p
    tb = ta + d
    return y0 + b * t + e.resposta(t, lambda s: K1 * _degrau1(s, ta) + K2 * _degrau1(s, tb), th)


def exp1(p, t):
    return p[0] + p[1] * np.exp(-t / p[2])


def exp2(p, t):
    return p[0] + p[1] * np.exp(-t / p[2]) + p[3] * np.exp(-t / (p[2] + p[4]))


# ------------------------------------------------------------- ajuste + estatística
def _aicc(loglik, n, k):
    a = -2 * loglik + 2 * k
    return a + 2 * k * (k + 1) / (n - k - 1) if n - k - 1 > 0 else np.nan


def _resumo_cov(jac, rss, n, k):
    try:
        cov = np.linalg.pinv(jac.T @ jac) * rss / max(n - k, 1)
        se = np.sqrt(np.clip(np.diag(cov), 0, None))
        corr = cov / np.outer(se, se).clip(min=1e-30)
    except Exception:
        se, corr = np.full(k, np.nan), np.full((k, k), np.nan)
    return se, corr


def _cov_gauss_newton_ar1(resid_fun, x, escala, ssw, n, phi):
    """Covariância aproximada por informação de Fisher/Gauss-Newton.

    Usa o jacobiano dos resíduos branqueados e acrescenta a informação do
    determinante AR(1). É uma aproximação local para erros-padrão/identificação;
    a maximização da verossimilhança usada no AICc continua sendo conjunta e
    completa.
    """
    try:
        J = approx_derivative(
            resid_fun, x, method="2-point",
            bounds=(np.zeros_like(x), np.ones_like(x)), rel_step=1e-5
        )
        hess = (2 * n / max(ssw, 1e-24)) * (J.T @ J)
        hess[-1, -1] += 2 * (1 + phi ** 2) / (1 - phi ** 2) ** 2
        hess = (hess + hess.T) / 2
        vals, vecs = np.linalg.eigh(hess)
        tol = max(float(np.max(np.abs(vals))) * 1e-8, 1e-8)
        cov_x = 2 * (vecs * (1 / np.maximum(vals, tol))) @ vecs.T
        escala = np.asarray(escala, float)
        cov = cov_x * np.outer(escala, escala)
        se = np.sqrt(np.clip(np.diag(cov), 0, None))
        corr = cov / np.outer(se, se).clip(min=1e-30)
        return se, np.clip(corr, -1, 1)
    except Exception:
        npar = len(x)
        return np.full(npar, np.nan), np.full((npar, npar), np.nan)


def ajusta(f, chutes, lb, ub, t, y, nomes, ar1=False):
    """Ajusta por mínimos quadrados (i.i.d.) ou MLE gaussiana com erro AR(1).

    Para AR(1), e_t = φ e_(t-1) + ε_t com e_0 estacionário. A função
    maximizada é a verossimilhança completa, incluindo o determinante
    (1 - φ²) da matriz de correlação. Portanto φ e os parâmetros do modelo
    são estimados conjuntamente, e não por Prais-Winsten seguido de uma
    correção do log-verossímil apenas na etapa do AICc.

    A variância σ² é perfilada: σ²_MV = SSW/n. No AICc são contados os
    parâmetros do modelo, φ (quando aplicável) e σ².
    """
    lb, ub = np.asarray(lb, float), np.asarray(ub, float)
    t = np.asarray(t, float)
    y = np.asarray(y, float)
    if len(y) <= len(nomes) + (2 if ar1 else 1):
        raise ValueError("Amostra insuficiente para estimar os parâmetros do modelo.")
    if not np.isfinite(t).all() or not np.isfinite(y).all():
        raise ValueError("O ajuste recebeu tempos ou observações não finitos.")
    if np.any(ub <= lb):
        raise ValueError("Cada limite superior deve ser maior que o inferior.")

    if not ar1:
        best = None
        for p0 in chutes:
            p0 = np.asarray(p0, float)
            p0 = np.clip(p0, lb + 1e-6 * (ub - lb), ub - 1e-6 * (ub - lb))
            r = least_squares(lambda p: y - f(p, t), p0, bounds=(lb, ub),
                              x_scale="jac", max_nfev=5000)
            if best is None or r.cost < best.cost:
                best = r
        p = best.x
        e = y - f(p, t)
        rss = float(np.sum(e ** 2))
        n = len(y)
        sig2 = max(rss / n, 1e-12)
        loglik = -0.5 * n * (np.log(2 * np.pi * sig2) + 1)
        k = len(p) + 1  # + σ²
        se, corr = _resumo_cov(best.jac, rss, n, len(p))
        nomes_all = list(nomes)
        no_limite = [nm for nm, v, a, b, sp in
                     zip(nomes_all, p, lb, ub, ub - lb)
                     if (v - a) < 1e-3 * sp or (b - v) < 1e-3 * sp]
        w = e
        rho_w = np.nan
    else:
        lb_ar = np.r_[lb, -0.98]
        ub_ar = np.r_[ub, 0.98]
        escala = ub_ar - lb_ar
        n = len(y)

        def componentes(x):
            p_all = lb_ar + np.asarray(x) * escala
            e_local = y - f(p_all[:len(nomes)], t)
            phi = float(p_all[-1])
            w_local = np.r_[np.sqrt(max(1 - phi ** 2, 1e-12)) * e_local[0],
                            e_local[1:] - phi * e_local[:-1]]
            ssw_local = float(np.dot(w_local, w_local))
            return p_all, e_local, w_local, ssw_local

        def objetivo(x):
            try:
                p_all, _, _, ssw_local = componentes(x)
                if not np.isfinite(ssw_local) or ssw_local <= 0:
                    return 1e100
                phi = float(p_all[-1])
                # -2 log L perfilada, omitindo apenas constantes comuns aos modelos.
                return n * np.log(max(ssw_local / n, 1e-24)) - np.log1p(-phi ** 2)
            except (ValueError, FloatingPointError, OverflowError):
                return 1e100

        # Multistart conjunto para o modelo e φ. Para cada vetor inicial de
        # parâmetros, usa a ACF(1) do resíduo i.i.d., φ=0 e um ponto de 0,6
        # no mesmo sentido. Evita dezenas de reinícios redundantes por evento.
        chutes_arr = [np.asarray(c, float) for c in chutes]
        inicios = []
        for p0 in chutes_arr:
            e0 = y - f(p0, t)
            rho0 = (float(np.corrcoef(e0[:-1], e0[1:])[0, 1])
                    if n > 3 and np.std(e0) > 0 else 0.0)
            if not np.isfinite(rho0):
                rho0 = 0.0
            phi_candidatos = []
            for valor in (np.clip(rho0, -0.9, 0.9), 0.0,
                          0.6 if rho0 >= 0 else -0.6):
                valor = float(np.clip(valor, -0.95, 0.95))
                if all(abs(valor - existente) > 1e-3 for existente in phi_candidatos):
                    phi_candidatos.append(valor)
            for phi0 in phi_candidatos:
                pp = np.r_[p0, phi0]
                pp = np.clip(pp, lb_ar + 1e-7 * escala, ub_ar - 1e-7 * escala)
                inicios.append((pp - lb_ar) / escala)

        melhor = None
        for x0 in inicios:
            opt = minimize(objetivo, x0, method="L-BFGS-B", jac="2-point",
                           bounds=[(1e-8, 1 - 1e-8)] * len(lb_ar),
                           options={"maxiter": 1500, "ftol": 1e-10,
                                    "gtol": 1e-7, "maxls": 30})
            valor = objetivo(opt.x)
            if np.isfinite(valor) and (melhor is None or valor < melhor[0]):
                melhor = (valor, opt.x.copy())
        if melhor is None:
            raise RuntimeError("Falha em todos os pontos iniciais do ajuste AR(1).")

        x = melhor[1]
        p_all, e, w, ssw = componentes(x)
        p = p_all
        sig2 = max(ssw / n, 1e-12)
        phi = float(p[-1])
        loglik = -0.5 * n * (np.log(2 * np.pi * sig2) + 1) + 0.5 * np.log1p(-phi ** 2)
        k = len(p) + 1  # parâmetros do modelo + φ + σ²
        se, corr = _cov_gauss_newton_ar1(
            lambda z: componentes(z)[2], x, escala, ssw, n, phi
        )
        nomes_all = list(nomes) + ["phi"]
        no_limite = [nm for nm, v, a, b, sp in
                     zip(nomes_all, p, lb_ar, ub_ar, ub_ar - lb_ar)
                     if (v - a) < 1e-3 * sp or (b - v) < 1e-3 * sp]
        rho_w = float(np.corrcoef(w[:-1], w[1:])[0, 1]) if n > 3 and np.std(w) > 0 else np.nan

    rss = float(np.sum(e ** 2))
    rho = float(np.corrcoef(e[:-1], e[1:])[0, 1]) if n > 3 and np.std(e) > 0 else np.nan
    return dict(p=p, nomes=nomes_all, rss=rss, res=e, n=n, k=k, se=se, corr=corr,
                no_limite=no_limite, rho1=rho, rho1_branco=rho_w, loglik=loglik,
                aicc=_aicc(loglik, n, k), rmse=np.sqrt(rss / n),
                r2=1 - rss / max(np.sum((y - y.mean()) ** 2), 1e-12))


def aicc_neff(fit, rho):
    """Sensibilidade: AICc i.i.d. com tamanho amostral efetivo n(1-ρ)/(1+ρ). Aproximação."""
    n, k = fit["n"], fit["k"]
    ne = n if not np.isfinite(rho) or rho <= 0 else max(n * (1 - rho) / (1 + rho), k + 3)
    ll = -0.5 * ne * (np.log(2 * np.pi * fit["rss"] / n) + 1)
    return _aicc(ll, ne, k), ne


def classe(d, lim):
    if not np.isfinite(d):
        return "indefinido"
    return "complexo" if d > lim else ("simples" if d < -lim else "indistinto")


def identificabilidade(fit, chaves, tau_nomes):
    """Problemas de identificação nos parâmetros 'chaves' de um ajuste."""
    prob = []
    idx = {nm: i for i, nm in enumerate(fit["nomes"])}
    lim = set(fit["no_limite"]) & set(chaves)
    if lim:
        prob.append("no_limite:" + ",".join(sorted(lim)))
    for nm in chaves:
        v, s = fit["p"][idx[nm]], fit["se"][idx[nm]]
        if np.isfinite(s) and abs(v) > 0 and s / abs(v) > REGRAS["SE_REL_MAX"]:
            prob.append(f"se_alto:{nm}")
    for nm in tau_nomes:
        if fit["p"][idx[nm]] < REGRAS["RES_TEMPORAL"]:
            prob.append(f"abaixo_resolucao:{nm}")
    ch = [idx[nm] for nm in chaves]
    c = fit["corr"][np.ix_(ch, ch)]
    if np.isfinite(c).all() and (np.abs(c - np.eye(len(ch))) > REGRAS["CORR_MAX"]).any():
        prob.append("parametros_correlacionados")
    return prob


def registrar_fit(reg, pref, fit):
    for nm, v, s in zip(fit["nomes"], fit["p"], fit["se"]):
        reg[f"{pref}_{nm}"] = v
        reg[f"{pref}_{nm}_se"] = s
    reg.update({f"{pref}_R2": fit["r2"], f"{pref}_RMSE": fit["rmse"], f"{pref}_rho1": fit["rho1"],
                f"{pref}_AICc": fit["aicc"], f"{pref}_no_limite": ";".join(fit["no_limite"])})
    if np.isfinite(fit.get("rho1_branco", np.nan)):
        reg[f"{pref}_rho1_branco"] = fit["rho1_branco"]


# ------------------------------------------------------------- métricas sem modelo
def cruza(ts, ys, alvo):
    """Primeiro instante em que a série cruza 'alvo' de baixo para cima.

    Interpolação linear entre as duas amostras vizinhas. Retorna NaN se a
    série já começa acima do nível ou nunca o atinge.
    """
    if len(ys) == 0 or ys[0] >= alvo:
        return np.nan
    j = np.where((ys[:-1] < alvo) & (ys[1:] >= alvo))[0]
    if len(j) == 0:
        return np.nan
    j = j[0] + 1
    return ts[j - 1] + (alvo - ys[j - 1]) * (ts[j] - ts[j - 1]) / (ys[j] - ys[j - 1])


# ------------------------------------------------------------- detecção
def detectar_eventos(g):
    """Pulsos de vazão > 0; lacunas curtas (vazão zero OU desconhecida) unem pulsos."""
    q = g["vazao"].values
    flui = np.where(np.isnan(q), False, q > 0)
    ev = []
    for a, b in runs(flui):
        if ev and a - ev[-1][1] - 1 <= REGRAS["GAP_EVENTO"]:
            ev[-1] = (ev[-1][0], b)
        else:
            ev.append((a, b))
    # q[i] é o volume em (i-1, i]  ->  abertura em i-1
    return [(a - 1, b) for a, b in ev if a >= 1]


# ------------------------------------------------------------- análise
def janela_ok(g, sel):
    if len(sel) == 0:
        return False, "janela_vazia"
    u = g["umid"].values[sel]
    if np.isnan(u).any():
        return False, "lacuna_na_janela"
    if g["umid_interp"].values[sel].mean() > REGRAS["FRAC_INTERP_MAX"]:
        return False, "muita_interpolacao"
    return True, ""


def inicio_recessao(y_all, indice_fechamento, indice_proximo_evento):
    """Índice do maior valor após o fechamento, até PICO_APOS_FECHAR.

    A janela começa no fechamento, nunca no pico global da subida: o pico
    global pode ocorrer antes do fechamento ou até 120 min depois dele.
    """
    fim = min(indice_fechamento + REGRAS["PICO_APOS_FECHAR"], indice_proximo_evento - 1)
    if fim < indice_fechamento:
        return None
    candidatos = np.arange(indice_fechamento, fim + 1)
    candidatos = candidatos[np.isfinite(np.asarray(y_all)[candidatos])]
    if not len(candidatos):
        return None
    return int(candidatos[np.argmax(np.asarray(y_all)[candidatos])])


def qualidade_dados(g, sel, q_sel_idx):
    """Flags da dimensão 'dados' para um conjunto de amostras de umidade e de vazão."""
    fl = []
    fi = g["umid_interp"].values[sel].mean()
    nh = int(g["umid_corrigida"].values[sel].sum())
    if fi > REGRAS["FRAC_INTERP_BOA"]: fl.append("interpolacao")
    if nh > REGRAS["PICOS_MAX_BOA"]: fl.append("picos_corrigidos")
    if g["vazao_reconstruida"].values[q_sel_idx].any(): fl.append("vazao_reconstruida")
    if np.isnan(g["vazao"].values[q_sel_idx]).any(): fl.append("vazao_desconhecida")
    if (g["vol_motivo"].values[q_sel_idx] != "").any(): fl.append("contador_corrigido")
    return fl, fi, nh


def analisar(ano, linha, g, eventos, residuos):
    out = []
    t_all = (g.index - g.index[0]).total_seconds().values / 60
    y_all = g["umid"].values
    q_all = g["vazao"].values
    q_ref = np.nanmedian(q_all[q_all > 0]) if np.any(q_all > 0) else np.nan
    for k, (a, b) in enumerate(eventos):
        ev_id = f"{ano}_L{linha}_{k:03d}"
        prox = eventos[k + 1][0] if k + 1 < len(eventos) else len(g) - 1
        t_on, t_off = t_all[a], t_all[b]
        q = q_all[a + 1:b + 1]
        reg = dict(evento_id=ev_id, ano=ano, linha=linha, tratamento=tratamento(ano, linha),
                   tratamento_confianca=tratamento_confianca(ano),
                   inicio=g.index[a], fim_irrigacao=g.index[b],
                   dur_irrig_min=t_off - t_on, passos_com_vazao=int(np.nansum(q > 0)),
                   passos_vazao_desconhecida=int(np.isnan(q).sum()),
                   volume=float(np.nansum(q)), vazao_ref_linha=q_ref,
                   status="descartado", motivo="")
        out.append(reg)

        def fim(m):
            reg["motivo"] = m
        if reg["passos_com_vazao"] < REGRAS["DUR_MIN_EVENTO"]:
            fim("irrigacao_curta"); continue
        if np.nanmax(q) > REGRAS["FATOR_GLITCH_VAZAO"] * q_ref:
            fim("hidrometro_glitch"); continue
        pre = np.where((t_all >= t_on - REGRAS["BASELINE_MIN"]) & (t_all <= t_on)
                       & g["umid_obs"].values)[0]
        if len(pre) < 3:
            fim("sem_baseline"); continue
        base = float(np.median(y_all[pre]))
        lim = min(b + REGRAS["PICO_APOS_FECHAR"], prox - 1)
        jan = np.arange(a, lim + 1)
        ok, m = janela_ok(g, jan)
        if not ok:
            fim(m); continue
        i_pk = jan[np.argmax(y_all[jan])]
        dY = y_all[i_pk] - base
        reg.update(baseline=base, pico=y_all[i_pk], dY=dY, t_pico_min=t_all[i_pk] - t_on,
                   pico_apos_fechar_min=t_all[i_pk] - t_off)
        if dY < REGRAS["DY_MIN"]:
            fim("sem_resposta_fisica"); continue

        # ---------------- métricas sem modelo (desde a abertura, interp. linear)
        sel = np.arange(a, i_pk + 1)
        ts, ys = t_all[sel] - t_on, y_all[sel]
        t05, t10, t63, t90 = (cruza(ts, ys, base + f * dY) for f in (0.05, 0.10, 0.632, 0.90))
        quedas = -np.sum(np.clip(np.diff(ys), None, 0))
        reg.update(atraso_5pct=t05, t10=t10, t63=t63, t90=t90, t10_90=t90 - t10,
                   monotonicidade=1 - quedas / dY)

        # ---------------- janela da recessão (após o fechamento)
        # A procura do pico após o fechamento deve cobrir a mesma janela
        # permitida na identificação do pico (até PICO_APOS_FECHAR passos).
        # A antiga janela b+6 truncava picos entre 70 e 120 min após fechar.
        # A recessão termina antes de nova vazão, vazão DESCONHECIDA ou lacuna.
        i_r = inicio_recessao(y_all, b, prox)
        i_end = None
        if i_r is not None:
            lim = min(i_r + REGRAS["REC_MAX"], prox - 1)
            qq = q_all[i_r + 1:lim + 1]
            pare = np.where(np.isnan(qq) | (np.nan_to_num(qq) > 0))[0]
            if len(pare):
                lim = i_r + pare[0]
            nan_u = np.where(np.isnan(y_all[i_r:lim + 1]))[0]
            if len(nan_u):
                lim = i_r + nan_u[0] - 1
            i_end = lim
            reg.update(rec_inicio=g.index[i_r], rec_dur_min=(lim - i_r) * DT,
                       rec_inicio_apos_fechar_min=t_all[i_r] - t_off)
        reg["status"] = "ajustado"

        # ================= A) modelos com vazão medida (principal)
        fim_ev = i_end if i_end is not None else i_pk
        sel = np.where((t_all >= t_on - REGRAS["BASELINE_MIN"]) & (t_all <= t_all[fim_ev]))[0]
        q_idx = np.arange(sel[0], sel[-1] + 1)               # passos de vazão que alimentam a janela
        fl_d, fi, nh = qualidade_dados(g, sel, q_idx)
        reg.update(ev_n=len(sel), ev_dur_min=t_all[fim_ev] - t_on, ev_frac_interp=fi, ev_n_picos_corrigidos=nh,
                   flags_dados=";".join(fl_d))
        ok, m = janela_ok(g, sel)
        qwin = q_all[q_idx]
        if not ok:
            reg["entrada_motivo"] = m
        elif np.isnan(qwin).any():
            reg["entrada_motivo"] = "vazao_desconhecida"      # não dá para simular a entrada
        elif len(sel) < REGRAS["N_MIN_EVENTO"]:
            reg["entrada_motivo"] = "poucos_pontos"
        else:
            reg["entrada_motivo"] = "ok"
            t = t_all[sel] - t_on
            y = y_all[sel]
            tq = t_all[q_idx] - t_on
            u = qwin / q_ref
            e = Entrada(tq - DT, tq, u)
            tmax = t[-1]
            Kc = dY / max(np.max(u), 0.2)
            P = {
                "M1q": (m1q, ["y0", "b", "K", "tau", "theta"],
                        [[base, 0, Kc, tau0, th0] for tau0 in (15, 60) for th0 in (5, 30)],
                        [base - 5, -0.02, 0, 1, 0], [base + 5, 0.02, 30 * Kc, 3000, 120]),
                "M2q": (m2q, ["y0", "b", "K", "tau1", "r", "theta"],
                        [[base, 0, Kc, tau0, r0, th0] for tau0 in (20, 120) for r0 in (0.1, 0.6) for th0 in (5, 30)],
                        [base - 5, -0.02, 0, 1, 1e-4, 0], [base + 5, 0.02, 30 * Kc, 3000, 1.0, 120]),
                "M2p": (m2p, ["y0", "b", "K1", "tau_a", "K2", "delta", "theta"],
                        [[base, 0, Kc, ta0, Kc / 2, d0, th0] for ta0 in (10, 40) for d0 in (100, 600) for th0 in (5, 30)],
                        [base - 5, -0.02, 0, 1, 0, 1, 0], [base + 5, 0.02, 30 * Kc, 500, 30 * Kc, 1e4, 120]),
            }
            fits = {}
            for nm, (f, nomes, ch, lb, ub) in P.items():
                fe = lambda p, tt, f=f: f(p, tt, e)
                if nm != "M1q":                     # modelos aninhados partem da solução de 1ª ordem
                    y0_, b_, K_, tau_, th_ = fits["M1q"]["p"]
                    ch = ch + ([[y0_, b_, K_, tau_, 2e-4, th_]] if nm == "M2q"
                               else [[y0_, b_, K_, min(tau_, 499), 1e-3 * K_, 500, th_]])
                fits[nm] = ajusta(fe, ch, lb, ub, t, y, nomes, ar1=False)
                # Três pontos iniciais de parâmetros × cinco valores de φ.
                # Para os modelos complexos, inclui também a parametrização que
                # reproduz M1q (K2=0 em M2p; polo rápido no limite em M2q).
                ch_ar1 = [fits[nm]["p"]]
                if nm == "M2q":
                    p1 = fits["M1q_ar1"]["p"]
                    ch_ar1.append([p1[0], p1[1], p1[2], p1[3], 1e-4, p1[4]])
                elif nm == "M2p":
                    p1 = fits["M1q_ar1"]["p"]
                    ch_ar1.append([p1[0], p1[1], p1[2], p1[3], 0.0, 500.0, p1[4]])
                fits[nm + "_ar1"] = ajusta(fe, ch_ar1, lb, ub, t, y, nomes, ar1=True)
                registrar_fit(reg, nm, fits[nm])
                registrar_fit(reg, nm + "ar", fits[nm + "_ar1"])
                residuos.append(pd.DataFrame(dict(evento_id=ev_id, fase="evento", modelo=nm,
                                                  t_min=t, y=y, y_ajuste=fe(fits[nm + "_ar1"]["p"][:len(nomes)], t),
                                                  residuo=fits[nm + "_ar1"]["res"])))
            reg["M2qar_tau2"] = fits["M2q_ar1"]["p"][3] * fits["M2q_ar1"]["p"][4]
            reg["M2par_tau_b"] = fits["M2p_ar1"]["p"][3] + fits["M2p_ar1"]["p"][5]
            pa = fits["M2p_ar1"]["p"]
            # contribuição de cada reservatório para a resposta DENTRO da janela
            # (o ganho estático K1/(K1+K2) engana: com τb de horas, o reservatório
            # lento atinge só uma fração do seu ganho durante o evento)
            c1 = np.max(pa[2] * e.resposta(t, lambda s_: _degrau1(s_, pa[3]), pa[6]))
            c2 = np.max(pa[4] * e.resposta(t, lambda s_: _degrau1(s_, pa[3] + pa[5]), pa[6]))
            reg["M2par_frac_rapida"] = c1 / max(c1 + c2, 1e-12)
            reg["M2par_frac_ganho_rapido"] = pa[2] / max(pa[2] + pa[4], 1e-12)
            # degenerações dos modelos de 2ª ordem (2º polo / 2º reservatório não identificável)
            deg_q = reg["M2qar_tau2"] < REGRAS["RES_TEMPORAL"]
            # M2p: componente desprezível ou τb além da janela -> degenerado;
            # τa < resolução com as duas componentes relevantes -> "1 polo + componente rápida"
            deg_p = (reg["M2par_frac_rapida"] < 0.05 or reg["M2par_frac_rapida"] > 0.95
                     or reg["M2par_tau_b"] > 3 * tmax)
            rapida_p = (not deg_p) and pa[3] < REGRAS["RES_TEMPORAL"]
            reg.update(M2q_degenerado=bool(deg_q), M2p_degenerado=bool(deg_p),
                       M2p_componente_rapida_nao_resolvida=bool(rapida_p))

            def comparar(suf, aic):
                a1 = aic["M1q"]
                cand = {nm: aic[nm] for nm in ("M2q", "M2p") if np.isfinite(aic[nm])}
                melhor2 = min(cand, key=cand.get) if cand else None
                d = a1 - cand[melhor2] if melhor2 else np.nan
                c = classe(d, REGRAS["DAICC"])
                degen = {"M2q": deg_q, "M2p": deg_p}.get(melhor2, True)
                if c == "complexo" and melhor2 == "M2p" and rapida_p:
                    cl = "1 polo + componente rápida"   # τa < 10 min: zero/feedthrough, 2º polo não resolvido
                elif c == "complexo" and not degen:
                    cl = f"2a ordem ({'série' if melhor2 == 'M2q' else 'com zero'})"
                elif c == "complexo" and degen:
                    cl = "indistinto"           # ganho de ajuste com parâmetro não identificável
                elif c == "simples" or (degen and c == "indistinto"):
                    cl = "1a ordem"
                else:
                    cl = "indistinto"
                reg[f"dAICc_{suf}"] = d
                reg[f"melhor2_{suf}"] = melhor2
                reg[f"classe_{suf}"] = cl

            comparar("ar1", {nm: fits[nm + "_ar1"]["aicc"] for nm in ("M1q", "M2q", "M2p")})
            comparar("iid", {nm: fits[nm]["aicc"] for nm in ("M1q", "M2q", "M2p")})
            rho = max(np.nanmax([fits["M2q"]["rho1"], fits["M2p"]["rho1"]]), 0)
            comparar("neff", {nm: aicc_neff(fits[nm], rho)[0] for nm in ("M1q", "M2q", "M2p")})
            reg["neff"] = aicc_neff(fits["M1q"], rho)[1]

            # qualidade do ajuste e identificabilidade do modelo escolhido (AR1)
            esc = ("M2q" if "série" in reg["classe_ar1"] else
                   "M2p" if ("com zero" in reg["classe_ar1"] or "rápida" in reg["classe_ar1"]) else "M1q")
            fe_ = fits[esc + "_ar1"]
            reg["modelo_escolhido"] = esc
            nrmse = fe_["rmse"] / dY
            fl_a = []
            if fe_["r2"] < REGRAS["R2_BOA"]: fl_a.append("R2_baixo")
            if nrmse > REGRAS["NRMSE_BOA"]: fl_a.append("NRMSE_alto")
            if abs(fe_.get("rho1_branco", 0) or 0) > 0.3: fl_a.append("residuo_branco_autocorrelacionado")
            reg.update(escolhido_R2=fe_["r2"], escolhido_NRMSE=nrmse, flags_ajuste=";".join(fl_a))
            chaves = {"M1q": (["K", "tau", "theta"], ["tau"]),
                      "M2q": (["K", "tau1", "r", "theta"], ["tau1"]),
                      "M2p": ((["K1", "K2", "delta", "theta"], []) if "rápida" in reg["classe_ar1"]
                              else (["K1", "tau_a", "K2", "delta", "theta"], ["tau_a"]))}[esc]
            fl_i = identificabilidade(fe_, *chaves)
            reg["flags_identificabilidade"] = ";".join(fl_i)
            reg["M1q_ident"] = ";".join(identificabilidade(fits["M1q_ar1"], ["K", "tau", "theta"], ["tau"]))
            reg["qual_dados"] = "boa" if not fl_d else "ressalva"
            reg["qual_ajuste"] = "boa" if not fl_a else "ressalva"
            reg["qual_ident"] = "boa" if not fl_i else "ressalva"
            # Amostra relaxada reproduz o filtro anterior. A amostra principal
            # agora também exige resíduos branqueados sem autocorrelação forte.
            # A identificabilidade é reportada separadamente, sem esconder eventos
            # cujo ajuste é bom mas cujos parâmetros individuais são incertos.
            flags_ajuste_anteriores = {"R2_baixo", "NRMSE_alto"}
            reg["amostra_principal_relaxada"] = bool(
                not fl_d and not (set(fl_a) & flags_ajuste_anteriores))
            reg["amostra_principal"] = bool(not fl_d and not fl_a)
            reg["amostra_principal_identificavel"] = bool(
                reg["amostra_principal"] and not fl_i)

        # ================= B) degrau (aproximação, só até o fechamento)
        sel = np.where((t_all >= t_on - REGRAS["BASELINE_MIN"]) & (t_all <= min(t_all[i_pk], t_off)))[0]
        n_on = int(np.sum(t_all[sel] > t_on))
        if len(sel) and janela_ok(g, sel)[0] and n_on >= REGRAS["N_MIN_DEGRAU"]:
            t, y = t_all[sel] - t_on, y_all[sel]
            T = max(t[-1], 20)
            f1 = ajusta(fopdt, [[base, dY, T / 3, th] for th in (0, 10, 30, 60)],
                        [base - 5, 0.3 * dY, 1, 0], [base + 5, 5 * dY, 50 * T, T], t, y,
                        ["y0", "K", "tau", "theta"])
            f2 = ajusta(sopdt, [[base, dY, T / 3, r, th] for r in (0.1, 0.5, 1.0) for th in (0, 20, 50)],
                        [base - 5, 0.3 * dY, 1, 0.01, 0], [base + 5, 5 * dY, 50 * T, 1.0, T], t, y,
                        ["y0", "K", "tau1", "r", "theta"])
            registrar_fit(reg, "D1", f1)
            registrar_fit(reg, "D2", f2)
            d = f1["aicc"] - f2["aicc"]
            c = classe(d, REGRAS["DAICC"])
            deg = f2["p"][2] * f2["p"][3] < REGRAS["RES_TEMPORAL"]
            reg.update(degrau_n=len(sel), degrau_dAICc=d,
                       classe_degrau="2a ordem" if c == "complexo" and not deg else
                       "1a ordem" if c == "simples" or deg else "indistinto")
        else:
            reg["degrau_motivo"] = "janela_ate_fechamento_curta"

        # ================= C) recessão (descritiva)
        if i_end is None:
            reg["rec_motivo"] = "sem_janela"
        else:
            sel = np.arange(i_r, i_end + 1)
            if len(sel) < REGRAS["REC_N_MIN"]:
                reg["rec_motivo"] = "janela_curta"
            elif g["umid_interp"].values[sel].mean() > REGRAS["FRAC_INTERP_MAX"]:
                reg["rec_motivo"] = "muita_interpolacao"
            else:
                t, y = t_all[sel] - t_all[i_r], y_all[sel]
                n, A, Tw = len(t), max(y[0] - y[-1], 0.1), t[-1]
                ch1 = [[y[-1], A, 60], [y[-1] - A, 2 * A, 300]]
                ch2 = [[y[-1], A / 2, 20, A / 2, 300], [y[-1] - A, A / 2, 40, A, 600]]
                b1 = ([y[-1] - 50, 0, 1], [y[-1] + 5, 100, 1e4])
                b2 = ([y[-1] - 50, 0, 1, 0, 1], [y[-1] + 5, 100, 1e3, 100, 1e4])
                e1i = ajusta(exp1, ch1, *b1, t, y, ["yinf", "A", "tau"])
                e2i = ajusta(exp2, ch2, *b2, t, y, ["yinf", "A1", "tau_r", "A2", "delta"])
                e1 = ajusta(exp1, [e1i["p"]], *b1, t, y, ["yinf", "A", "tau"], ar1=True)
                e2 = ajusta(exp2, [e2i["p"]], *b2, t, y, ["yinf", "A1", "tau_r", "A2", "delta"], ar1=True)
                registrar_fit(reg, "E1", e1)
                registrar_fit(reg, "E2", e2)
                tau_l = e2["p"][2] + e2["p"][4]
                fr = e2["p"][1] / max(e2["p"][1] + e2["p"][3], 1e-9)
                degen = []
                if fr < 0.05 or fr > 0.95: degen.append("componente_desprezivel")
                if e2["p"][2] < REGRAS["RES_TEMPORAL"]: degen.append("tau_r_abaixo_resolucao")
                lenta_ni = tau_l > 2 * Tw or "delta" in e2["no_limite"]
                if lenta_ni: degen.append("tau_l_nao_identificavel")

                def cls(d):
                    c = classe(d, REGRAS["DAICC"])
                    if c == "complexo" and not ({"componente_desprezivel", "tau_r_abaixo_resolucao"} & set(degen)):
                        return "dupla (lenta não identificável)" if lenta_ni else "dupla"
                    if c == "simples" or degen:
                        return "simples"
                    return "indistinto"
                rho = max(e2i["rho1"], 0) if np.isfinite(e2i["rho1"]) else 0
                reg.update(rec_n=n, rec_tau_l=tau_l, rec_tau_l_identificavel=not lenta_ni,
                           rec_frac_rapida=fr, rec_degeneracao=";".join(degen),
                           rec_dAICc_ar1=e1["aicc"] - e2["aicc"], rec_dAICc_iid=e1i["aicc"] - e2i["aicc"],
                           rec_dAICc_neff=aicc_neff(e1i, rho)[0] - aicc_neff(e2i, rho)[0],
                           rec_flags_dados=";".join(qualidade_dados(g, sel, sel)[0]), rec_motivo="")
                reg["classe_recessao_ar1"] = cls(reg["rec_dAICc_ar1"])
                reg["classe_recessao_iid"] = cls(reg["rec_dAICc_iid"])
                reg["classe_recessao_neff"] = cls(reg["rec_dAICc_neff"])
                for nome, fit, f in (("E1", e1, exp1), ("E2", e2, exp2)):
                    residuos.append(pd.DataFrame(dict(evento_id=ev_id, fase="recessao", modelo=nome,
                                                      t_min=t, y=y, y_ajuste=f(fit["p"][:-1], t), residuo=fit["res"])))
    return out


# ------------------------------------------------------------- resumos
CONTAGENS = ["detectados", "descartados", "ajustados", "com_modelo_vazao",
             "amostra_principal", "amostra_principal_relaxada",
             "amostra_principal_identificavel"]


def resumir(ev, chaves):
    det = ev.groupby(chaves).size().rename("detectados")
    aj = ev[ev.status.eq("ajustado")]
    com = aj[aj.entrada_motivo.eq("ok")]
    pri = com[com.amostra_principal.fillna(False).astype(bool)]
    pri_rel = com[com.amostra_principal_relaxada.fillna(False).astype(bool)]
    pri_ident = com[com.amostra_principal_identificavel.fillna(False).astype(bool)]
    partes = [det,
              ev[ev.status.eq("descartado")].groupby(chaves).size().rename("descartados"),
              aj.groupby(chaves).size().rename("ajustados"),
              com.groupby(chaves).size().rename("com_modelo_vazao"),
              pri.groupby(chaves).size().rename("amostra_principal"),
              pri_rel.groupby(chaves).size().rename("amostra_principal_relaxada"),
              pri_ident.groupby(chaves).size().rename("amostra_principal_identificavel")]
    for cl in ["1a ordem", "1 polo + componente rápida", "2a ordem (série)", "2a ordem (com zero)", "indistinto"]:
        for suf in ("ar1", "iid", "neff"):
            nome = f"n_{suf}_{cl}"
            partes.append(pri.groupby(chaves)[f"classe_{suf}"].apply(lambda s, c=cl: int((s == c).sum())).rename(nome))
    rec = aj.dropna(subset=["classe_recessao_ar1"])
    for cl in ["simples", "dupla", "dupla (lenta não identificável)", "indistinto"]:
        partes.append(rec.groupby(chaves)["classe_recessao_ar1"].apply(lambda s, c=cl: int((s == c).sum()))
                      .rename(f"n_rec_ar1_{cl}"))
    r = pd.concat(partes, axis=1)
    cont = [c for c in r.columns if c in CONTAGENS or c.startswith("n_")]
    r[cont] = r[cont].fillna(0).astype(int)                 # zero só em contagens
    for col in ["atraso_5pct", "t63", "M1qar_tau", "M1qar_theta", "M1qar_K",
                "D1_tau", "D1_theta", "E2_tau_r", "E1_tau"]:
        gg = pri.groupby(chaves)[col] if col.startswith(("M1q", "atraso", "t63")) else aj.groupby(chaves)[col]
        r[f"{col}_mediana"] = gg.median()
        r[f"{col}_p25"] = gg.quantile(.25)
        r[f"{col}_p75"] = gg.quantile(.75)
    ident = rec[rec.rec_tau_l_identificavel.fillna(False).astype(bool)]
    r["rec_tau_l_identificavel_mediana"] = ident.groupby(chaves)["rec_tau_l"].median()
    r["M1qar_rho1_branco_mediana"] = pri.groupby(chaves)["M1qar_rho1_branco"].median()
    return r.reset_index()                                   # métricas sem estimativa ficam NaN


def main():
    arquivos = [RAIZ / "data" / "processed" / f"dataset_m2_{ano}.csv"
                for ano in (2023, 2024, 2025)]
    ausentes = [str(p) for p in arquivos if not p.exists()]
    if ausentes:
        raise FileNotFoundError(
            "Dados processados ausentes. Primeiro execute merge_m2.py com os CSVs brutos "
            "environmental, soil, indicators, valve_controller/water_valve e water_meter. "
            "Arquivos não encontrados: " + ", ".join(ausentes)
        )
    SAIDA.mkdir(parents=True, exist_ok=True)
    regs, residuos = [], []
    for ano in (2023, 2024, 2025):
        for linha, g in carregar(ano):
            regs += analisar(ano, linha, g, detectar_eventos(g), residuos)
    ev = pd.DataFrame(regs)
    ev.to_csv(SAIDA / "eventos_todos.csv", index=False)
    ev[ev.status.eq("descartado")][["evento_id", "ano", "linha", "tratamento", "inicio", "fim_irrigacao",
                                    "dur_irrig_min", "volume", "motivo", "baseline", "dY"]] \
        .to_csv(SAIDA / "eventos_descartados.csv", index=False)
    pd.concat(residuos).to_csv(SAIDA / "residuos.csv", index=False)
    resumir(ev, ["ano"]).to_csv(SAIDA / "resumo_por_safra.csv", index=False)
    resumir(ev, ["ano", "linha", "tratamento", "tratamento_confianca"]).to_csv(
        SAIDA / "resumo_por_safra_linha.csv", index=False)
    # sensibilidade: inclui eventos com vazão reconstruída / dados com ressalva
    aj = ev[ev.status.eq("ajustado") & ev.entrada_motivo.eq("ok")]
    sens = []
    for nome, sub in (("principal", aj[aj.amostra_principal.fillna(False).astype(bool)]),
                      ("principal_identificavel", aj[aj.amostra_principal_identificavel.fillna(False).astype(bool)]),
                      ("principal_relaxada", aj[aj.amostra_principal_relaxada.fillna(False).astype(bool)]),
                      ("todos_com_modelo_vazao", aj),
                      ("so_vazao_reconstruida", aj[aj.flags_dados.fillna("").str.contains("vazao_reconstruida")])):
        row = dict(amostra=nome, n=len(sub))
        for suf in ("ar1", "iid", "neff"):
            for cl, v in sub[f"classe_{suf}"].value_counts().items():
                row[f"{suf}:{cl}"] = int(v)
        row.update(M1q_tau_mediana=sub.M1qar_tau.median(), M1q_theta_mediana=sub.M1qar_theta.median())
        sens.append(row)
    pd.DataFrame(sens).to_csv(SAIDA / "sensibilidade_amostra.csv", index=False)
    with open(SAIDA / "config_execucao.json", "w", encoding="utf-8") as f:
        json.dump(dict(versao=VERSAO, executado_em=datetime.now(timezone.utc).isoformat(), regras=REGRAS,
                       tratamentos={str(k): v for k, v in TRATAMENTOS.items()},
                       tratamentos_confianca={str(k): v for k, v in CONFIANCA.items()},
                       criterio_amostra_principal=(
                           "dados sem ressalvas e ajuste com R2/NRMSE adequados e resíduo AR(1) branqueado "
                           "com |rho1| <= 0.3; identificabilidade reportada em subconjunto separado"),
                       estatistica_ar1="MLE gaussiana completa com variância perfilada e multistart conjunto",
                       fonte="data/processed/dataset_m2_{2023,2024,2025}.csv",
                       fonte_tratamentos={"nome": "IoT Dataset from an Evolving Tomato Cultivation Testbed",
                                          "doi": "10.17632/h8sfcf9487.1",
                                          "url": "https://data.mendeley.com/datasets/h8sfcf9487/1"}),
                  f, ensure_ascii=False, indent=2)
    print(ev.groupby(["ano", "status", "motivo"]).size().to_string())
    return ev


if __name__ == "__main__":
    main()
