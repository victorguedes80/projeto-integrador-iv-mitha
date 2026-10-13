
# import mpl_axes_aligner
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np


# ================================
# tratando nan com median
# ================================
def median_Nan(X_train, X_test):
    nan_For_column = X_train.isna().sum()
    columns = X_train.columns

    # add marcador de ausencia
    for column, count in zip(columns, nan_For_column):
        if count > 0:
            X_train[column + "_ausente"] = X_train[column].isna()
            X_test[column + "_ausente"] = X_test[column].isna()

    # tratando Nan com mediana
    median =  X_train.median()
    X_train = X_train.fillna(median)
    X_test  = X_test.fillna(median)
    return X_train, X_test


# ================================
#pca
# ================================
def pca(X_train):
    # Padronização
    scaler = StandardScaler(with_mean=True, with_std=True)
    Z = scaler.fit_transform(X_train)

    # Matriz de covariância
    Cov = pd.DataFrame(Z, columns=X_train.columns).cov()

    # Autovalores e autovetores
    vals, vecs = np.linalg.eigh(Cov)

    # Ordenar (decrescente)
    order = np.argsort(vals)[::-1]
    vals = vals[order]
    vecs = vecs[:, order]
    
    return vals, vecs, scaler, Z


# ================================
# Variancia acumulada
# ================================
def Var_cum(vals, plot=True, ret: bool = False):
    var = vals / vals.sum()
    var_cum = np.cumsum(var)

    if plot:
        x = range(1, len(var)+1)

        # cores para valores
        azul = '#1f4e79'     
        laranja = '#cc6600'
        
        plt.figure(figsize=(6,4))
        plt.plot(x, var, marker='o', label='Variância por PC')
        plt.plot(x, var_cum, marker='s', label='Acumulada')

        # deslocamento vertical -> p/ não ficar em cima dos pontos
        offset_var = 0.025
        offset_cum = 0.025

        # anotando valores (%)
        for i, v in enumerate(var):
            plt.text(i+1, v + offset_var, f'{v*100:.1f}%', ha='center', va='bottom', fontsize=9, color=azul)

        # anotações acumulada
        for i, v in enumerate(var_cum):
            plt.text(i+1, v + offset_cum, f'{v*100:.1f}%', ha='center', va='bottom', fontsize=9, color=laranja)

        plt.xlabel('Componente Principal')
        plt.ylabel('Proporção da Variância')
        plt.xticks(x)
        plt.legend()
        plt.tight_layout()
        plt.show()

    return var, var_cum


# ================================
# T2 e Q
# ================================
def t2_q(Z, vals, vecs, k=2, confidence_lim=97, ids=None, plot=True, name_IMG = ""):
    # Seleção dos k componentes
    lam = vals[:k]
    P = vecs[:, :k]

    # Scores
    T = Z @ P

    # Hotelling T2
    T2 = np.sum((T**2) / lam, axis=1)

    # Reconstrução e erro
    Z_hat = T @ P.T
    E = Z - Z_hat

    # Q residual
    Q = np.sum(E**2, axis=1)

    # limite de confiança por percentil
    T2_lim = np.percentile(T2, confidence_lim)
    Q_lim = np.percentile(Q, confidence_lim)

    # Normalização
    T2_norm = T2 / T2_lim
    Q_norm = Q / Q_lim

    # Máscaras das 4 regiões
    regiao_normal = (T2_norm <= 1) & (Q_norm <= 1)
    regiao_t2 = (T2_norm > 1) & (Q_norm <= 1)
    regiao_q = (T2_norm <= 1) & (Q_norm > 1)
    regiao_t2_q = (T2_norm > 1) & (Q_norm > 1)

    # IDs
    if ids is None:
        ids = np.arange(len(T2_norm))
    else:
        ids = np.array(ids)

    # Gráfico
    
    if plot:
        
        cores = {
            "normal": "#b48f1f",
            "anomalia_T2": "#ff7f0e",
            "anomalia_Q": "#9445de",
            "anomalia_T2_Q": "#d6278493"
        }

        plt.figure(figsize=(8, 6))

        plt.scatter(T2_norm[regiao_normal], Q_norm[regiao_normal],
                    label="Normal", alpha=0.8, c=cores["normal"])

        plt.scatter(T2_norm[regiao_t2], Q_norm[regiao_t2],
                    label="Anomalia T2", alpha=0.8, c=cores["anomalia_T2"])

        plt.scatter(T2_norm[regiao_q], Q_norm[regiao_q],
                    label="Anomalia Q", alpha=0.8, c=cores['anomalia_Q'])

        plt.scatter(T2_norm[regiao_t2_q], Q_norm[regiao_t2_q],
                    label="Anomalia T2 + Q", alpha=0.8, c=cores['anomalia_T2_Q'])

        plt.axvline(1, linestyle='--', color='r', linewidth=2, label=r"Hotelling's $T^2$")
        plt.axhline(1, linestyle='--', color='g', linewidth=2, label="Q-Residuals")

        plt.xlabel("Hotelling T2 (normalizado)")
        plt.ylabel("Q residual (normalizado)")
        # plt.title("T2 vs Q")
        plt.legend(title=f"Limite de confiança {confidence_lim}%")
        plt.tight_layout()
        # img_save(file_name=name_IMG, dir_name="RemocaoPCA/")

    return {
        "T2_norm": T2_norm,
        "Q_norm": Q_norm,
        "regiao_normal": regiao_normal,
        "regiao_t2": regiao_t2,
        "regiao_q": regiao_q,
        "regiao_t2_q": regiao_t2_q
    }


def serieT2_Q(X: pd.DataFrame, meta, name_timeCol: str, res):

    meta_plot = meta.copy()
    
    meta_plot["classe"] = "normal"
    meta_plot.loc[res["regiao_t2"], "classe"] = "anomalia_T2"
    meta_plot.loc[res["regiao_q"], "classe"] = "anomalia_Q"
    meta_plot.loc[res["regiao_t2_q"], "classe"] = "anomalia_T2_Q"

    # garantindo ordenação
    meta_plot[name_timeCol] = pd.to_datetime(meta_plot[name_timeCol])
    meta_plot = meta_plot.sort_values(name_timeCol)
    X = X.loc[meta_plot.index]

    cores = {
        "normal": "#1f77b4",
        "anomalia_T2": "#ff7f0e",
        "anomalia_Q": "#9467bd",
        "anomalia_T2_Q": "#d62728"
    }

    n = len(X.columns)
    fig, axes = plt.subplots(n, 1, figsize=(10, 4*n), sharex=True)

    if n == 1:
        axes = [axes]

    for ax, col in zip(axes, X.columns):
        for classe, cor in cores.items():
            mask = meta_plot["classe"] == classe
            ax.scatter(
                meta_plot.loc[mask, name_timeCol],
                X.loc[mask, col],
                color=cor,
                label=classe,
                s=30
            )

        ax.set_ylabel(col)

    axes[-1].set_xlabel(name_timeCol)
    axes[0].legend()
    plt.tight_layout()
    plt.show()


# ================================
# BIPLOT adaptado kkk ai mds
# ================================
#Fonte base: https://insidelearningmachines.com/biplot/#:~:text=We%20can%20make%20a%20biplot%20in%20Python%20that,%23set%20x-axis%20label%20ax.set_xlabel%28%22PC1%22%2Cfontsize%3D10%29%20%23set%20y-axis%20label%20
# def biplot(dfScores, dfLoadings, y, target_name, k_loadings=8):
#     # --- Cores fixas das classes
#     palette = {'0': '#1f77b4', '1': '#d62728'}  # azul e vermelho
#     markers = {'0': 'o', '1': 'o'}              # ou 'o' e 'x' se quiser
#     label_map = {'0': 'Não potável', '1': 'Potável'}

#     fig, ax = plt.subplots(figsize=(12, 7))

#     # --- Pontos (scores)
#     y = pd.Series(y).astype(str).values
#     for c in pd.unique(y):
#         m = (y == c)
#         ax.scatter(dfScores.loc[m, 'PC1'], dfScores.loc[m, 'PC2'],
#                    s=8, alpha=0.55, c=[palette.get(c, 'grey')], marker=markers.get(c, 'o'),
#                    label=label_map.get(c, c))

#     ax.set_xlabel('PC1'); ax.set_ylabel('PC2')
#     ax.legend(title=target_name, frameon=False, loc='upper left', bbox_to_anchor=(1.02, 1.02))
#     ax.grid(alpha=0.15)

#     # --- Seleção dos loadings mais fortes
#     L = dfLoadings.loc[['PC1','PC2']].copy()
#     strength = np.sqrt(L.loc['PC1']**2 + L.loc['PC2']**2)
#     cols = strength.sort_values(ascending=False).head(k_loadings).index

#     # --- Escala dos vetores para caber no painel
#     # raio ~ 0.9 do alcance dos scores
#     xspan = np.ptp(dfScores['PC1']); yspan = np.ptp(dfScores['PC2'])
#     radius = 0.9 * min(xspan, yspan) / 2
#     scale = radius / strength[cols].max()

#     # --- Eixos para setas
#     ax2 = ax.twinx().twiny()

#     for col in cols:
#         x = L.loc['PC1', col] * scale
#         yv = L.loc['PC2', col] * scale
#         ax2.arrow(0, 0, x, yv,
#                   color='#555', lw=1.5, alpha=0.8, length_includes_head=True,
#                   head_width=0.06*radius*0.1, head_length=0.09*radius*0.1, zorder=3)
#         ax2.text(x*1.06, yv*1.06, col,
#                  fontsize=9, color='black', ha='center', va='center',
#                  bbox=dict(facecolor='white', edgecolor='none', alpha=0.6),
#                  zorder=4)

#     # alinhar eixos
#     mpl_axes_aligner.align.xaxes(ax, 0, ax2, 0, 0.5)
#     mpl_axes_aligner.align.yaxes(ax, 0, ax2, 0, 0.5)

#     plt.tight_layout()
#     # img_save('biplot','biplot_2pcs')



def plot_classes_anomalias(y, res, color_map=None):
    """
    Plota a contagem de cada classe (y) dentro das anomalias T² + Q.
    
    Parâmetros:
    - y: pd.Series com as labels
    - res: dict com 'regiao_t2_q'
    - colors: lista de cores (opcional), na mesma ordem das classes ordenadas
    """
    
    idx_red = res["regiao_t2_q"]
    y_red = y.loc[idx_red]
    
    counts = y_red.value_counts().sort_index()
    
    if color_map is None:
        cores = ["gray"] * len(counts)
    else:
        cores = [color_map.get(c, "gray") for c in counts.index]
    
    ax = counts.plot(kind="bar", color=cores)
    
    for i, v in enumerate(counts.values):
        ax.text(i, v, str(v), ha='center', va='bottom')
    
    plt.ylabel("Quantidade")
    plt.xlabel("Classe")
    plt.title("Distribuição das classes nas anomalias T² + Q")
    plt.tight_layout()
    plt.show()


def remove_anomalias_t2_q(X, y, res, meta=None):
    mask = ~res["regiao_t2_q"]  # mantém tudo que não é anomalia t2q

    print(f"Total de linhas removidas por T² + Q: {(~mask).sum()}")
    
    X_clean = X.loc[mask]
    y_clean = y.loc[mask]
    
    if meta is not None:
        meta_clean = meta.loc[mask]
        return X_clean, y_clean, meta_clean
    
    return X_clean, y_clean