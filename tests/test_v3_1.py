"""Testes de regressão para as correções da análise de dinâmica v3.1."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "utils"))
sys.path.insert(0, str(ROOT / "src" / "data_processing"))

import resposta_irrigacao as R  # noqa: E402
from merge_m2 import load_water_meter  # noqa: E402


class TestMLEAR1(unittest.TestCase):
    def test_recupera_phi_e_brande_residuos(self):
        rng = np.random.default_rng(123)
        n = 80
        t = np.arange(n, dtype=float)
        phi_real = 0.65
        erro = np.zeros(n)
        for i in range(1, n):
            erro[i] = phi_real * erro[i - 1] + rng.normal(0, 0.15)
        y = 1.8 + 0.025 * t + erro
        modelo = lambda p, tt: p[0] + p[1] * tt

        fit = R.ajusta(
            modelo,
            [[1.5, 0.02], [2.0, 0.03]],
            [0.0, -0.1],
            [5.0, 0.1],
            t,
            y,
            ["intercepto", "inclinacao"],
            ar1=True,
        )

        self.assertAlmostEqual(fit["p"][-1], phi_real, delta=0.20)
        self.assertLess(abs(fit["rho1_branco"]), 0.20)
        self.assertEqual(fit["k"], 4)  # intercepto + inclinação + φ + σ²
        residuos = y - modelo(fit["p"][:-1], t)
        phi = fit["p"][-1]
        brancos = np.r_[np.sqrt(1 - phi ** 2) * residuos[0],
                        residuos[1:] - phi * residuos[:-1]]
        sigma2 = np.sum(brancos ** 2) / n
        loglik_exato = (-0.5 * n * (np.log(2 * np.pi * sigma2) + 1)
                        + 0.5 * np.log(1 - phi ** 2))
        self.assertAlmostEqual(fit["loglik"], loglik_exato, places=8)
        self.assertTrue(np.isfinite(fit["aicc"]))
        self.assertEqual(len(fit["se"]), 3)


class TestRecessao(unittest.TestCase):
    def test_pico_100_min_apos_fechamento_e_encontrado(self):
        y = np.full(100, 30.0)
        fechamento = 10
        y[fechamento + 10] = 36.0  # 100 min após o fechamento
        y[fechamento + 11] = 34.0
        indice = R.inicio_recessao(y, fechamento, 90)
        self.assertEqual(indice, fechamento + 10)

    def test_nao_ultrapassa_proximo_evento(self):
        y = np.arange(100, dtype=float)
        indice = R.inicio_recessao(y, 10, 15)
        self.assertEqual(indice, 14)

    def test_retorna_none_quando_janela_sem_umidade(self):
        y = np.full(100, np.nan)
        self.assertIsNone(R.inicio_recessao(y, 10, 90))


    def test_evento_sintetico_completo_gera_ajuste_e_recessao(self):
        n = 130
        idx = pd.date_range("2025-06-01", periods=n, freq="10min", tz="UTC")
        t = np.arange(n) * 10.0
        a, b = 10, 15
        vazao = np.zeros(n)
        vazao[a + 1:b + 1] = 1.0
        umidade = np.full(n, 25.0)
        for i in range(a, n):
            subida = 6.0 * (1 - np.exp(-max(t[i] - t[a], 0) / 35.0))
            atraso_recessao = max(t[i] - t[b + 8], 0)
            umidade[i] = 25.0 + subida * np.exp(-atraso_recessao / 360.0)
        umidade[b + 8] = 31.0
        for i in range(b + 9, n):
            umidade[i] = 25.0 + 6.0 * np.exp(-(t[i] - t[b + 8]) / 360.0)

        g = pd.DataFrame(index=idx)
        g["umid"] = umidade
        g["umid_obs"] = True
        g["umid_interp"] = False
        g["umid_corrigida"] = False
        g["vazao"] = vazao
        g["vazao_reconstruida"] = False
        g["vol_motivo"] = ""
        g["water_volume"] = np.cumsum(vazao)
        residuos = []

        evento = R.analisar(2025, 1, g, [(a, b)], residuos)[0]

        self.assertEqual(evento["status"], "ajustado")
        self.assertEqual(evento["entrada_motivo"], "ok")
        self.assertEqual(pd.Timestamp(evento["rec_inicio"]), idx[b + 8])
        self.assertGreater(len(residuos), 0)


class TestContadorAcumulado(unittest.TestCase):
    def test_agrega_por_maximo_na_janela_de_10_minutos(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pd.Timestamp("2025-01-01T00:00:00Z")
            timestamps = [int((base + pd.Timedelta(minutes=m)).timestamp() * 1000)
                          for m in (1, 4, 8)]
            bruto = pd.DataFrame({
                "ts_generation": timestamps,
                "line": [1, 1, 1],
                "current_volume": ["9", "10", "invalid"],
            })
            bruto.to_csv(Path(tmp) / "water_meter2025.csv", index=False)
            saida = load_water_meter(tmp, "2025")

        self.assertEqual(len(saida), 1)
        self.assertEqual(float(saida.loc[0, "water_volume"]), 10.0)


class TestTratamentosDocumentados(unittest.TestCase):
    def test_mapeamento_oficial_de_2025(self):
        self.assertEqual(R.tratamento(2025, 1), "I100")
        self.assertEqual(R.tratamento(2025, 2), "I30")
        self.assertEqual(R.tratamento(2025, 3), "limiar_umidade_solo")
        self.assertEqual(R.tratamento(2025, 4), "limiar_temperatura_foliar")
        self.assertEqual(R.tratamento(2025, 5), "estrategia_IA")
        self.assertIn("documentado", R.tratamento_confianca(2025))


if __name__ == "__main__":
    unittest.main()
