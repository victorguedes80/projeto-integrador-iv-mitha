"""Figuras da análise de dinâmica da umidade do solo — v3.1.

Gera em imgs/dinamica_irrigacao/v3_1/:
  resumo.png                figura-resumo estratificada por safra/linha
  residuos_exemplos.png     resíduos x tempo e ACF para eventos representativos
  eventos_<ano>.pdf         um painel por evento ajustado (dados, ajustes com vazão, flags)
  descartados.pdf           eventos descartados, com o motivo

Requer: python src/utils/resposta_irrigacao.py (gera results/dinamica_irrigacao/v3_1/)
"""
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "utils"))
import resposta_irrigacao as R  # noqa: E402

RES = RAIZ / "results" / "dinamica_irrigacao" / R.VERSAO
IMG = RAIZ / "imgs" / "dinamica_irrigacao" / R.VERSAO
CL_ENT = {"1a ordem": "#4C78A8", "1 polo + componente rápida": "#72B7B2",
          "2a ordem (série)": "#F58518", "2a ordem (com zero)": "#E45756", "indistinto": "#BBBBBB"}
CL_REC = {"simples": "#4C78A8", "dupla": "#E45756",
          "dupla (lenta não identificável)": "#F2A6A5", "indistinto": "#BBBBBB"}


def rotulo(ano, linha, trat):
    t = "" if trat == "não identificado" else f"\n{trat}"
    return f"{ano} L{linha}{t}"


def barras(ax, df, col, cores, titulo, nota=""):
    anos = [2023, 2024, 2025]
    tab = pd.crosstab(df["ano"], df[col]).reindex(index=anos, columns=list(cores), fill_value=0)
    base = np.zeros(len(tab))
    for c in cores:
        ax.bar([str(a) for a in anos], tab[c], bottom=base, color=cores[c], label=c)
        for x, b, v in zip(range(len(tab)), base, tab[c]):
            if v:
                ax.text(x, b + v / 2, int(v), ha="center", va="center", fontsize=7)
        base += tab[c].values
    for x, v in enumerate(base):
        ax.text(x, v, f"n={int(v)}", ha="center", va="bottom", fontsize=7)
    ax.set_title(titulo, fontsize=9)
    ax.set_ylim(0, max(base.max(), 1) * 1.25)
    if nota:
        ax.text(0.02, 0.97, nota, transform=ax.transAxes, fontsize=6.5, va="top", color="0.35")


def resumo(ev):
    aj = ev[ev.status.eq("ajustado")]
    com = aj[aj.entrada_motivo.eq("ok")]
    pri = com[com.amostra_principal.fillna(False).astype(bool)].copy()
    pri_ident = com[com.amostra_principal_identificavel.fillna(False).astype(bool)]
    n_desc = int(ev.status.eq("descartado").sum())
    n_res = len(com) - len(pri)
    den = (f"{len(ev)} detectados · {n_desc} descartados · {len(com)} com modelo de vazão · "
           f"{len(pri)} na amostra principal · {len(pri_ident)} com identificabilidade adequada · "
           f"{n_res} fora da principal")

    fig = plt.figure(figsize=(16, 13))
    gs = fig.add_gridspec(3, 4, height_ratios=[1.2, 1, 1])
    fig.suptitle(f"Dinâmica da umidade do solo — v3.1 (MLE AR(1) completa; vazão medida como entrada)   |   {den}", fontsize=10)

    # (a) parâmetros por safra/linha
    ax = fig.add_subplot(gs[0, :])
    grupos = pri.sort_values(["ano", "linha"])[["ano", "linha", "tratamento"]].drop_duplicates()
    pos = np.arange(len(grupos))
    if grupos.empty:
        ax.text(0.5, 0.5, "Nenhum evento atende aos critérios da amostra principal",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
    else:
        series = [("M2par_theta", "#72B7B2", "atraso θ (M2p)"), ("t63", "#54A24B", "t63 sem modelo"),
                  ("M1qar_tau", "#4C78A8", "τ da 1ª ordem (M1q)"), ("M2par_tau_b", "#E45756", "τ lenta (M2p)")]
        for k, (col, cor, nome) in enumerate(series):
            dados = [pri.loc[pri.ano.eq(r.ano) & pri.linha.eq(r.linha), col].dropna().values
                     for r in grupos.itertuples()]
            dados = [d if len(d) else np.array([np.nan]) for d in dados]
            bp = ax.boxplot(dados, positions=pos + (k - 1.5) * 0.2, widths=0.17, patch_artist=True,
                            showfliers=False, medianprops=dict(color="k"))
            for b in bp["boxes"]:
                b.set_facecolor(cor)
            ax.plot([], [], "s", color=cor, label=nome)
        ax.set_yscale("log"); ax.set_ylim(1, 5000)
        ax.axhline(10, color="0.5", ls=":", lw=1)
        ax.text(pos[0] - 0.45, 11, "resolução 10 min", fontsize=7, color="0.4")
        ax.set_xticks(pos, [rotulo(r.ano, r.linha, r.tratamento) for r in grupos.itertuples()], fontsize=8)
        for i, r in enumerate(grupos.itertuples()):
            ax.text(i, 1.3, f"n={int((pri.ano.eq(r.ano) & pri.linha.eq(r.linha)).sum())}", ha="center", fontsize=7)
        ax.set_ylabel("minutos (log)")
        ax.legend(ncol=4, fontsize=8, loc="upper left")
    ax.set_title("(a) Parâmetros por safra/linha — amostra principal. A faixa de n no título distingue "
                 "ajuste adequado de identificabilidade adequada. Tratamentos conforme a descrição "
                 "oficial do dataset", fontsize=9)

    # (b)-(e) classificação
    barras(fig.add_subplot(gs[1, 0]), aj.dropna(subset=["classe_degrau"]).rename(columns={"classe_degrau": "c"}),
           "c", {k: CL_ENT[k] for k in ("1a ordem", "2a ordem (série)", "indistinto")} | {},
           "(b) Degrau até o fechamento\n(aproximação; AICc i.i.d.)",
           "todos os ajustados com janela ≥ 6 pts")
    barras(fig.add_subplot(gs[1, 1]), pri, "classe_iid", CL_ENT, "(c) Vazão como entrada\nAICc erro i.i.d.",
           "amostra principal")
    a = fig.add_subplot(gs[1, 2])
    barras(a, pri, "classe_ar1", CL_ENT, "(d) Vazão como entrada\nAICc erro AR(1) — critério principal",
           "amostra principal")
    barras(fig.add_subplot(gs[1, 3]), pri, "classe_neff", CL_ENT, "(e) Vazão como entrada\nAICc n efetivo (aproximação)",
           "amostra principal")
    a.legend(fontsize=6.5, loc="upper right", framealpha=.9)
    a.set_ylim(0, a.get_ylim()[1] * 1.45)

    # (f) recessão
    rec = aj.dropna(subset=["classe_recessao_ar1"])
    barras(fig.add_subplot(gs[2, 0]), rec, "classe_recessao_ar1", CL_REC, "(f) Recessão — AICc AR(1)",
           "todos os ajustados com recessão ≥ 3 h")
    barras(fig.add_subplot(gs[2, 1]), rec, "classe_recessao_neff", CL_REC, "(g) Recessão — AICc n efetivo")

    # (h) resíduos
    a = fig.add_subplot(gs[2, 2])
    bins = np.linspace(-1, 1, 21)
    a.hist(pri.M1q_rho1.dropna(), bins, alpha=.5, label=f"M1q i.i.d. (med {pri.M1q_rho1.median():.2f})")
    a.hist(pri.M2p_rho1.dropna(), bins, alpha=.5, label=f"M2p i.i.d. (med {pri.M2p_rho1.median():.2f})")
    a.hist(pri.M2par_rho1_branco.dropna(), bins, histtype="step", lw=2, color="k",
           label=f"M2p AR(1), resíduo branqueado (med {pri.M2par_rho1_branco.median():.2f})")
    a.set_xlabel("autocorrelação lag-1 dos resíduos"); a.legend(fontsize=6.5)
    a.set_title("(h) Resíduos do evento completo", fontsize=9)

    # (i) recessão: τ rápida x lenta, marcando não identificáveis
    a = fig.add_subplot(gs[2, 3])
    d = rec[rec.classe_recessao_ar1.str.startswith("dupla")]
    ok = d.rec_tau_l_identificavel.astype(bool)
    a.scatter(d.E2_tau_r[ok], d.rec_tau_l[ok], s=14, c="#E45756", label=f"τ lenta identificável ({ok.sum()})")
    a.scatter(d.E2_tau_r[~ok], d.rec_tau_l[~ok].clip(upper=5000), s=18, facecolors="none", edgecolors="0.4",
              label=f"τ lenta NÃO identificável ({(~ok).sum()}, ≥5000 agrupado)")
    a.set_xscale("log"); a.set_yscale("log")
    a.set_xlabel("τ rápida (min)"); a.set_ylabel("τ lenta (min)")
    a.legend(fontsize=6.5); a.set_title("(i) Recessões duplas (AR(1))", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.subplots_adjust(hspace=0.55)
    fig.savefig(IMG / "resumo.png", dpi=105)
    plt.close(fig)


def residuos_exemplos(ev, res):
    pri = ev[ev.entrada_motivo.eq("ok") & ev.amostra_principal.fillna(False).astype(bool)]
    if pri.empty:
        return
    escolha = []
    for cl in ("1 polo + componente rápida", "2a ordem (com zero)", "1a ordem"):
        s = pri[pri.classe_ar1.eq(cl)]
        if len(s):
            escolha.append(s.iloc[len(s) // 2])
    fig, axs = plt.subplots(len(escolha), 3, figsize=(14, 3.3 * len(escolha)), squeeze=False)
    for row, r in zip(axs, escolha):
        rr = res[res.evento_id.eq(r.evento_id) & res.fase.eq("evento")]
        x = rr[rr.modelo.eq("M1q")]
        row[0].plot(x.t_min, x.y, ".", color="0.3", ms=3)
        for mod, cor in (("M1q", "C0"), ("M2q", "C1"), ("M2p", "C3")):
            m = rr[rr.modelo.eq(mod)]
            row[0].plot(m.t_min, m.y_ajuste, color=cor, lw=1.2, label=mod)
            row[1].plot(m.t_min, m.residuo, color=cor, lw=.8)
            e = m.residuo.values - m.residuo.mean()
            ac = [1] + [np.corrcoef(e[:-k], e[k:])[0, 1] for k in range(1, 13)]
            row[2].plot(range(13), ac, "o-", color=cor, ms=3)
        row[0].legend(fontsize=7); row[0].set_title(f"{r.evento_id} — classe AR(1): {r.classe_ar1}", fontsize=9)
        row[1].axhline(0, color="k", lw=.5); row[1].set_title("resíduos × tempo (min)", fontsize=9)
        row[2].axhline(0, color="k", lw=.5); row[2].axhspan(-2 / np.sqrt(len(e)), 2 / np.sqrt(len(e)), color="0.9")
        row[2].set_title("ACF dos resíduos (lags de 10 min)", fontsize=9)
    fig.tight_layout()
    fig.savefig(IMG / "residuos_exemplos.png", dpi=100)
    plt.close(fig)


def _painel_dados(ax, g, t0, t1):
    s = g.loc[t0 - pd.Timedelta("1h"): t1]
    tm = (s.index - t0).total_seconds() / 60
    ax.plot(tm[s.umid_obs], s.umid[s.umid_obs], ".", ms=3, color="0.3")
    ax.plot(tm[s.umid_corrigida], s.umid_bruta[s.umid_corrigida], "v", ms=4, color="C4", mfc="none")
    ax.plot(tm[s.umid_corrigida], s.umid[s.umid_corrigida], "v", ms=3, color="C4")
    ax.plot(tm[s.umid_interp], s.umid[s.umid_interp], "x", ms=4, color="C1")
    a2 = ax.twinx()
    a2.step(tm, s.vazao, "C2", where="pre", alpha=.4, lw=.8)
    rec = s.vazao_reconstruida.values
    if rec.any():
        a2.plot(tm[rec], s.vazao[rec], "s", ms=3, color="C2", mfc="none")
    a2.set_yticks([])
    ax.axvline(0, color="k", ls=":", lw=.8)
    ax.tick_params(labelsize=7)
    return tm


LEGENDA = ("min desde a abertura · ●: umidade observada · ▽ vazio/cheio: leitura bruta/corrigida (pico isolado) · "
           "x: interpolada · verde: vazão (□ reconstruída) · azul M1q, laranja M2q, vermelho M2p (AR(1))")


def pdf_eventos(ev, res):
    for ano in (2023, 2024, 2025):
        dados = dict(R.carregar(ano))
        sub = ev[ev.ano.eq(ano) & ev.status.eq("ajustado")].sort_values(["linha", "inicio"])
        with PdfPages(IMG / f"eventos_{ano}.pdf") as pdf:
            if sub.empty:
                fig = plt.figure(figsize=(11.7, 8.3)); fig.text(.5, .5, f"Sem eventos ajustados em {ano}", ha="center")
                pdf.savefig(fig); plt.close(fig); continue
            for i0 in range(0, len(sub), 6):
                fig, axs = plt.subplots(3, 2, figsize=(11.7, 8.3))
                for ax, (_, r) in zip(axs.flat, sub.iloc[i0:i0 + 6].iterrows()):
                    t0 = pd.Timestamp(r.inicio)
                    fim = t0 + pd.Timedelta(minutes=(r.ev_dur_min if pd.notna(r.ev_dur_min) else 600) + 30)
                    _painel_dados(ax, dados[r.linha], t0, fim)
                    rr = res[res.evento_id.eq(r.evento_id) & res.fase.eq("evento")]
                    for mod, cor in (("M1q", "C0"), ("M2q", "C1"), ("M2p", "C3")):
                        m = rr[rr.modelo.eq(mod)]
                        ax.plot(m.t_min, m.y_ajuste, color=cor, lw=1.1)
                    trat = "" if r.tratamento == "não identificado" else str(r.tratamento)
                    cl = r.classe_ar1 if isinstance(r.classe_ar1, str) else f"sem modelo de vazão ({r.entrada_motivo})"
                    ax.set_title(f"{r.evento_id} {trat} {t0:%d/%m %H:%M} | AR(1): {cl} | degrau: "
                                 f"{r.classe_degrau if isinstance(r.classe_degrau, str) else '—'}", fontsize=7)
                    txt = (f"dados: {r.qual_dados if isinstance(r.qual_dados, str) else '—'} "
                           f"{r.flags_dados if isinstance(r.flags_dados, str) else ''}\n"
                           f"ajuste: {r.qual_ajuste if isinstance(r.qual_ajuste, str) else '—'} "
                           f"{r.flags_ajuste if isinstance(r.flags_ajuste, str) else ''}\n"
                           f"ident.: {r.qual_ident if isinstance(r.qual_ident, str) else '—'} "
                           f"{r.flags_identificabilidade if isinstance(r.flags_identificabilidade, str) else ''}")
                    principal = bool(r.amostra_principal) if pd.notna(r.amostra_principal) else False
                    ax.text(0.01, 0.02, txt, transform=ax.transAxes, fontsize=5.5,
                            color="0.35" if principal else "C3", va="bottom")
                for ax in axs.flat[len(sub.iloc[i0:i0 + 6]):]:
                    ax.axis("off")
                fig.text(0.5, 0.005, LEGENDA, ha="center", fontsize=6.5)
                fig.tight_layout(rect=(0, 0.02, 1, 1))
                pdf.savefig(fig)
                plt.close(fig)


def pdf_descartados(ev):
    sub = ev[ev.status.eq("descartado")].sort_values(["ano", "linha", "inicio"])
    dados = {a: dict(R.carregar(a)) for a in sub.ano.unique()}
    with PdfPages(IMG / "descartados.pdf") as pdf:
        fig, ax = plt.subplots(figsize=(11.7, 8.3))
        tab = pd.crosstab([sub.ano, sub.linha], sub.motivo)
        ax.axis("off")
        ax.set_title("Eventos descartados por motivo (safra, linha)", fontsize=11)
        if not tab.empty:
            t = ax.table(cellText=tab.values, rowLabels=[f"{a} L{l}" for a, l in tab.index],
                         colLabels=list(tab.columns), loc="center")
            t.auto_set_font_size(False); t.set_fontsize(8)
        pdf.savefig(fig); plt.close(fig)
        for i0 in range(0, len(sub), 6):
            fig, axs = plt.subplots(3, 2, figsize=(11.7, 8.3))
            for ax, (_, r) in zip(axs.flat, sub.iloc[i0:i0 + 6].iterrows()):
                t0 = pd.Timestamp(r.inicio)
                _painel_dados(ax, dados[r.ano][r.linha], t0, t0 + pd.Timedelta(minutes=r.dur_irrig_min + 360))
                ax.set_title(f"{r.evento_id} | motivo: {r.motivo} | ΔY={r.dY:.1f}" if pd.notna(r.dY)
                             else f"{r.evento_id} | motivo: {r.motivo}", fontsize=7)
            for ax in axs.flat[len(sub.iloc[i0:i0 + 6]):]:
                ax.axis("off")
            fig.text(0.5, 0.005, LEGENDA, ha="center", fontsize=6.5)
            fig.tight_layout(rect=(0, 0.02, 1, 1))
            pdf.savefig(fig); plt.close(fig)


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    ev = pd.read_csv(RES / "eventos_todos.csv")
    res = pd.read_csv(RES / "residuos.csv")
    resumo(ev)
    residuos_exemplos(ev, res)
    pdf_eventos(ev, res)
    pdf_descartados(ev)


if __name__ == "__main__":
    main()
