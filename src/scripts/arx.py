"""ARX escolhido: uma planta linear, com memórias independentes de solo e água.

Passo de 10 min. Memórias de solo e água selecionadas pela validação temporal;
temperatura e umidade do ar. Prevê ΔH e soma à umidade anterior.
O ajuste/figuras ficam em gerar_resultados.py; o fuzzy não é alterado.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

CORE = ['temperature_env', 'humidity_env']
EXTRAS = ['gdd', 'pressure', 'co2', 'electrical_conductivity']


def janelas(d, horizonte, inicio, fim):
    """Mesmos inícios para todas as variantes: 3h contínuas, sem imputar água/H.

    inicio/fim em timestamp ms; fim exclusivo. Chuva conhecida para permitir
    comparação justa da variante com chuva; não se exige chuva igual a zero.
    """
    t = d.ts_generation.to_numpy()
    h = d.humidity_soil.to_numpy()
    u = d.delta_volume.to_numpy()
    y = d.humidity_soil_fim.to_numpy()
    env = d[CORE + ['precipitation_mm']].to_numpy()
    regular = np.abs(np.diff(t) - 600_000) <= 20_000
    ids = []
    for i in range(18, len(d) - horizonte):
        if t[i] < inicio or t[i + horizonte] >= fim:
            continue
        if not regular[i - 18:i + horizonte].all():
            continue
        if not np.isfinite(h[i - 6:i + horizonte + 1]).all():
            continue
        if (h[i - 6:i + horizonte + 1] <= 0).any():
            continue
        if not np.isfinite(u[i - 18:i + horizonte]).all():
            continue
        if not np.isfinite(y[i:i + horizonte]).all():
            continue
        if (y[i:i + horizonte] <= 0).any() or not np.isfinite(env[i:i + horizonte]).all():
            continue
        ids.append(i)
    return np.asarray(ids, dtype=int)


@dataclass
class ARX:
    p: int
    q: int
    alpha: float
    ambientais: list
    medianas: dict
    coeficientes: list
    intercepto: float

    @classmethod
    def ajustar(cls, d, ids, q=18, alpha=100., ambientais=None, p=6):
        ambientais = list(CORE if ambientais is None else ambientais)
        if p not in [1,2,3,4,5,6] or q not in [1,2,3,4,5,6,12,18]:
            raise ValueError('Quantidade de atrasos fora da grade avaliada')
        # Ajusta imputação, escala e regressão com os dados de treino.
        med = d.iloc[ids][ambientais].median()
        if med.isna().any():
            raise ValueError('Variável ambiental sem dados no treino')
        env = d[ambientais].fillna(med).to_numpy()
        h, u = d.humidity_soil.to_numpy(), d.delta_volume.to_numpy()
        x = np.column_stack([h[ids-k] for k in range(p+1)]
                            + [u[ids-k] for k in range(q+1)]
                            + [env[ids, j] for j in range(len(ambientais))])
        target = d.humidity_soil_fim.to_numpy()[ids] - h[ids]
        scale = StandardScaler().fit(x)
        fit = Ridge(alpha=alpha).fit(scale.transform(x), target)
        coef = fit.coef_ / scale.scale_
        intercept = float(fit.intercept_ - coef @ scale.mean_)
        return cls(p, q, alpha, ambientais, med.to_dict(), coef.tolist(), intercept)

    def passo(self, umidades, volumes, ambiente):
        """Uma transição de 10 min; históricos em ordem antiga → recente.

        volumes inclui a água aplicada no intervalo que será simulado.
        Retorna a umidade seguinte, sem truncamento ou correção por medidas.
        """
        h, u = np.asarray(umidades, float), np.asarray(volumes, float)
        if len(h) < self.p+1 or len(u) < self.q+1:
            raise ValueError('Históricos insuficientes')
        x = np.r_[h[-self.p-1:][::-1], u[-self.q-1:][::-1],
                  [ambiente.get(c, self.medianas[c]) for c in self.ambientais]]
        if not np.isfinite(x).all():
            raise ValueError('Entradas ausentes ou não finitas')
        return float(h[-1] + x @ self.coeficientes + self.intercepto)

    def trajetorias(self, d, ids, horizonte):
        """Replay recursivo de várias janelas; só a inicialização usa H real."""
        if not len(ids):
            return np.empty((0, horizonte))
        h, u = d.humidity_soil.to_numpy(), d.delta_volume.to_numpy()
        history = np.column_stack([h[ids-k] for k in range(self.p, -1, -1)])
        volumes = np.column_stack([u[ids-k] for k in range(self.q, 0, -1)])
        env = d[self.ambientais].fillna(self.medianas).to_numpy()
        result = np.empty((len(ids), horizonte))
        for step in range(horizonte):
            i = ids + step
            volumes = np.column_stack([volumes, u[i]])
            x = np.column_stack([history[:, -1-k] for k in range(self.p+1)]
                                + [volumes[:, -1-k] for k in range(self.q+1)]
                                + [env[ids if c == 'electrical_conductivity' else i, j]
                                   for j, c in enumerate(self.ambientais)])
            pred = history[:, -1] + x @ self.coeficientes + self.intercepto
            result[:, step] = pred
            history = np.column_stack([history, pred])[:, -self.p-1:]
            volumes = volumes[:, -self.q:]
        return result

    @property
    def maior_polo(self):
        a = np.asarray(self.coeficientes[:self.p+1]).copy()
        a[0] += 1
        return float(np.abs(np.roots(np.r_[1., -a])).max())

    def salvar(self, path):
        Path(path).write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))

    @classmethod
    def carregar(cls, path):
        return cls(**json.loads(Path(path).read_text()))
