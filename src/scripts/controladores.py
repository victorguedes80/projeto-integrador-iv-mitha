"""Baseline e fuzzy de analispi4.ipynb; saída em minutos: 0, 10 ou 30."""
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl


def baseline(umidade, estado_valvula):
    """Histerese: abre em ≤24%, fecha em ≥27%, mantém no intervalo."""
    if umidade >= 27:
        return 0
    return 30 if umidade <= 24 or estado_valvula == 1 else 0


# Define as entradas, a saída e as nove regras do fuzzy.
erro = ctrl.Antecedent(np.linspace(-10, 27, 4701), "erro")
erro["ex"] = fuzz.trapmf(erro.universe, [-10, -10, -1.60, 0])
erro["tr"] = fuzz.trapmf(erro.universe, [-1.60, 0, 3, 5.07])
erro["def"] = fuzz.trapmf(erro.universe, [0, 3, 27, 27])

dh = ctrl.Antecedent(np.linspace(-0.18050, 0.8720, 3196), "dh_20min")
dh["dim"] = fuzz.trapmf(dh.universe, [-0.18050, -0.18050, -0.010, 0])
dh["est"] = fuzz.trimf(dh.universe, [-0.010, 0, 0.009])
dh["aum"] = fuzz.trapmf(dh.universe, [0, 0.009, 0.8720, 0.8720])

ti = ctrl.Consequent(np.linspace(0, 30, 301), "tempo_irrigacao")
ti["D"] = fuzz.trimf(ti.universe, [0, 0, 10])
ti["C"] = fuzz.trimf(ti.universe, [0, 10, 20])
ti["L"] = fuzz.trimf(ti.universe, [10, 30, 30])

regras = [ctrl.Rule(erro[e] & dh[d], ti[t])
          for e, saidas in [("ex", ["D", "D", "D"]),
                            ("tr", ["D", "D", "D"]),
                            ("def", ["L", "L", "C"])]
          for d, t in zip(["dim", "est", "aum"], saidas)]
sistema = ctrl.ControlSystem(regras)
inferencia = ctrl.ControlSystemSimulation(sistema)


def fuzzy(umidade, dh_20min, continuo=False):
    """Mamdani/centroide original, seguido de arredondamento para 0/10/30.

    dh_20min = (H atual − H de 20 min atrás) / 20, em p.p./min.
    Entradas saturam nos universos do notebook. continuo=True devolve o
    centroide sem arredondamento; empates de arredondamento usam menor tempo.
    """
    inferencia.input["erro"] = 27 - umidade
    inferencia.input["dh_20min"] = dh_20min
    inferencia.compute()
    minutos = float(inferencia.output["tempo_irrigacao"])
    tempos = np.array([0, 10, 30])
    return minutos if continuo else int(tempos[np.argmin(abs(tempos - minutos))])
