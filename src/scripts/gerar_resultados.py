#!/usr/bin/env python3
"""Ajusta os modelos ARX e gera as figuras de avaliação.

Da raiz do projeto: .venv/bin/python -B src/scripts/gerar_resultados.py
--saida permite gerar em uma pasta de revisão antes de substituir as figuras.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.patches import FancyBboxPatch, Rectangle
from arx import ARX, CORE, EXTRAS, janelas
from comum import BASE, ROOT, CACHE, RESULTADOS

FOLDS = [('2024-08-08','2024-08-11'), ('2024-08-11','2024-08-14'),
         ('2024-08-14','2024-08-17'), ('2024-08-17','2024-08-19')]
STAMP = lambda x: pd.Timestamp(x,tz='UTC').value/1e6
START, CUT, END = map(STAMP, ['2024-08-01','2024-08-19','2024-09-04'])
COLORS = ['#793b99','#13877f','#3266ae']
NAMES = ['ARX base escolhido','Base + demais ambientais','Base + ambientais + chuva']
P_GRID = [1,2,3,4,5,6]
Q_GRID = [1,2,3,4,5,6,12,18]
ALPHAS = [.1,1.,10.,100.]

def lag_name(p,q):
    return f'H={p}; água={q}'


def save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def table(path, title, columns, rows, widths=None, size=(15,5),
          groups=None, highlight_cells=(), hatch_label=None):
    fig,ax=plt.subplots(figsize=size,layout='constrained');ax.axis('off')
    ax.set_title(title,loc='left',fontsize=21,pad=20)
    bottom=.02
    top=.95
    if hatch_label:
        ax.add_patch(Rectangle((0,.965),.035,.035,transform=ax.transAxes,
                              facecolor='#fff2b3',edgecolor='#d4ad35',hatch='///',lw=1))
        ax.text(.045,.9825,hatch_label,transform=ax.transAxes,fontsize=13,va='center')
        top=.93
    widths=widths or [1/len(columns)]*len(columns)
    if groups:
        height=.18
        for start,stop,text in groups:
            x=sum(widths[:start]);w=sum(widths[start:stop])
            ax.add_patch(Rectangle((x,top-height),w,height,transform=ax.transAxes,
                                  facecolor='#2f596c',edgecolor='white',lw=1))
            ax.text(x+w/2,top-height/2,text,transform=ax.transAxes,
                    ha='center',va='center',fontsize=14,color='white',weight='bold')
        top-=height
    tab=ax.table(cellText=rows,colLabels=columns,cellLoc='center',
                 colWidths=widths,bbox=[0,bottom,1,top-bottom]);tab.auto_set_font_size(False);tab.set_fontsize(14)
    for (i,j),cell in tab.get_celld().items():
        cell.set_edgecolor('white');cell.set_facecolor('#193b4d' if i==0 else '#e8eff2' if i%2 else '#f5f7f8')
        if i==0:cell.set_text_props(color='white',weight='bold')
        if (i,j) in highlight_cells:
            cell.set_facecolor('#fff2b3');cell.set_edgecolor('#d4ad35');cell.set_hatch('///')
    save(fig,path)


def fit_cv(d):
    records=[];periods=[];folds=[]
    for fold,(a,b) in enumerate(FOLDS,1):
        train=janelas(d,1,START,STAMP(a))
        vals={h:janelas(d,h,STAMP(a),STAMP(b)) for h in [12,36]}
        periods.append(dict(rodada=fold,ajuste=f'01/08–{pd.Timestamp(a).day-1:02}/08',
                            validacao=f'{pd.Timestamp(a).day:02}–{pd.Timestamp(b).day-1:02}/08',
                            n_treino=len(train),n2=len(vals[12]),n6=len(vals[36]),
                            agua2=sum((d.delta_volume.iloc[i:i+12]>0).any() for i in vals[12]),
                            agua6=sum((d.delta_volume.iloc[i:i+36]>0).any() for i in vals[36])))
        if len(train)<30 or not any(len(v) for v in vals.values()):
            raise ValueError('Rodada sem dados suficientes')
        folds.append((fold,train,vals))
    def evaluate(label,p,q,env):
        for fold,train,vals in folds:
            for alpha in ALPHAS:
                model=ARX.ajustar(d,train,q,alpha,env,p=p)
                for h,ids in vals.items():
                    if not len(ids):continue
                    truth=d.humidity_soil_fim.to_numpy()[ids[:,None]+np.arange(h)]
                    error=model.trajetorias(d,ids,h)-truth
                    records.append(dict(variante=label,p=p,q=q,rodada=fold,alpha=alpha,
                                        horizonte_h=h/6,n=len(ids),MAE=np.abs(error).mean(),
                                        maior_polo=model.maior_polo))
    # Avalia a grade de atrasos nas mesmas janelas de validação.
    for p in P_GRID:
        for q in Q_GRID:evaluate(lag_name(p,q),p,q,CORE)
    def aggregate():
        cv=pd.DataFrame(records)
        return cv,cv.groupby(['variante','alpha','rodada']).MAE.mean().groupby(['variante','alpha']).mean()
    cv,scores=aggregate()
    ranking=scores.reset_index(name='MAE_validacao')
    ranking['p']=ranking.variante.map({lag_name(p,q):p for p in P_GRID for q in Q_GRID})
    ranking['q']=ranking.variante.map({lag_name(p,q):q for p in P_GRID for q in Q_GRID})
    winner=ranking.sort_values(['MAE_validacao','p','q','alpha']).iloc[0]
    p,q=int(winner.p),int(winner.q)
    for label,env in [(NAMES[1],CORE+EXTRAS),(NAMES[2],CORE+EXTRAS+['precipitation_mm'])]:
        evaluate(label,p,q,env)
    cv,scores=aggregate();train=janelas(d,1,START,CUT);models={}
    for pp in P_GRID:
        for qq in Q_GRID:
            label=lag_name(pp,qq);alpha=float(scores.loc[label].idxmin())
            models[label]=ARX.ajustar(d,train,qq,alpha,CORE,p=pp)
    models[NAMES[0]]=models[lag_name(p,q)]
    for label,env in [(NAMES[1],CORE+EXTRAS),(NAMES[2],CORE+EXTRAS+['precipitation_mm'])]:
        models[label]=ARX.ajustar(d,train,q,float(scores.loc[label].idxmin()),env,p=p)
    return models,cv,scores,pd.DataFrame(periods),train


def metrics(d,models):
    h=d.humidity_soil.to_numpy();y=d.humidity_soil_fim.to_numpy();u=d.delta_volume.to_numpy()
    rows=[];cross=[]
    labels=NAMES+[lag_name(p,q) for p in P_GRID for q in Q_GRID]+['Última umidade constante']
    for horizon in [12,36,144]:
        ids=janelas(d,horizon,CUT,END)
        if not len(ids):continue
        truth=np.column_stack([y[ids+k] for k in range(horizon)])
        wet=np.array([(u[i:i+horizon]>0).any() for i in ids])
        for name in labels:
            pred=np.repeat(h[ids,None],horizon,axis=1) if name==labels[-1] else models[name].trajetorias(d,ids,horizon)
            if not np.isfinite(pred).all():raise ValueError('Trajetória não finita: '+name)
            for regime,mask in [('Todos',np.ones(len(ids),bool)),('Com irrigação',wet),('Sem irrigação',~wet)]:
                if not mask.any():continue
                e=pred[mask]-truth[mask]
                rows.append(dict(modelo=name,horizonte_h=horizon/6,regime=regime,n=int(mask.sum()),MAE=np.abs(e).mean(),MAE_final=np.abs(e[:,-1]).mean(),vies_final=e[:,-1].mean()))
            ac=np.column_stack([h[ids],truth]);si=np.column_stack([h[ids],pred])
            for threshold,up in [(24,False),(27,True)]:
                ar=(ac[:,:-1]<threshold)&(ac[:,1:]>=threshold) if up else (ac[:,:-1]>=threshold)&(ac[:,1:]<threshold)
                sr=(si[:,:-1]<threshold)&(si[:,1:]>=threshold) if up else (si[:,:-1]>=threshold)&(si[:,1:]<threshold)
                a,b=ar.any(axis=1),sr.any(axis=1);both=a&b
                cross.append(dict(modelo=name,horizonte_h=horizon/6,limiar=threshold,n=len(ids),reais=int(a.sum()),detectados=int(both.sum()),perdidos=int((a&~b).sum()),falsos=int((~a&b).sum()),erro_tempo_min=float(np.abs((sr.argmax(axis=1)-ar.argmax(axis=1))[both]*10).mean()) if both.any() else np.nan,lado_errado=np.mean((pred<threshold)!=(truth<threshold))))
    return pd.DataFrame(rows),pd.DataFrame(cross)


def event_indices(d):
    ids=janelas(d,36,CUT,END);u=d.delta_volume.to_numpy();t=d.ts_generation.to_numpy()
    events=[]
    for i in ids:
        if u[i]>0 and u[i-1]==0 and (not events or t[i]-t[events[-1]]>=6*3600000):events.append(i)
    if not events:raise ValueError('Nenhuma aplicação elegível')
    anomaly=[i for i in events if pd.to_datetime(t[i],unit='ms',utc=True).strftime('%Y-%m-%d')=='2024-08-28']
    if not anomaly:raise ValueError('28/08 não elegível; não ocultar diagnóstico')
    return [events[0],anomaly[0]]


def trajectories(d,models,events,out):
    fig,axs=plt.subplots(2,2,figsize=(17,9),sharex='col',layout='constrained',gridspec_kw={'height_ratios':[3,1]})
    for col,i in enumerate(events):
        times=pd.to_datetime(d.ts_generation.iloc[i:i+37],unit='ms',utc=True)
        real=np.r_[d.humidity_soil.iloc[i],d.humidity_soil_fim.iloc[i:i+36]]
        axs[0,col].plot(times,real,color='#142e3b',lw=3,label='Sensor de solo')
        for name,color in zip(NAMES,COLORS):
            pred=models[name].trajetorias(d,np.array([i]),36)[0]
            axs[0,col].plot(times,np.r_[real[0],pred],lw=2.2,ls='--',color=color,label=name)
        axs[0,col].set(title=times.iloc[0].strftime('%d/%m/%Y · trajetória de 6h'),ylabel='Umidade do solo (%RH)')
        for threshold in [24,27]:axs[0,col].axhline(threshold,color='#aaa',ls=':',lw=1)
        axs[1,col].bar(times.iloc[:-1],d.delta_volume.iloc[i:i+36],width=9/1440,align='edge',color='#5087a7')
        axs[1,col].set(ylabel='Volume de irrigação (m³)',xlabel='Horário UTC')
        axs[1,col].xaxis.set_major_locator(md.HourLocator());axs[1,col].xaxis.set_major_formatter(md.DateFormatter('%H:%M'))
        for row in range(2):axs[row,col].grid(axis='y',alpha=.18)
    handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,ncol=4,loc='upper left',bbox_to_anchor=(.055,1.055),fontsize=15,frameon=False, borderaxespad=0,columnspacing=1.2)
    fig.suptitle('Avaliação exploratória · umidade simulada sem correção pelas medidas',fontsize=21,y=1.105,x=.055,ha='left')
    save(fig,out/'arx_inicial/validacao_arx.png')


def lags_plot(d,models,events,scores,out):
    chosen=models[NAMES[0]]
    # Compara as menores memórias, a referência 6/18 e o modelo escolhido.
    best_for_p=lambda p:min((lag_name(p,q) for q in Q_GRID),key=lambda k:scores.loc[k].min())
    best_for_q=lambda q:min((lag_name(p,q) for p in P_GRID),key=lambda k:scores.loc[k].min())
    selected=list(dict.fromkeys([best_for_p(1),best_for_q(1),lag_name(6,18),lag_name(chosen.p,chosen.q)]))
    fig,axs=plt.subplots(1,2,figsize=(18,7),layout='constrained')
    for ax,i in zip(axs,events):
        times=pd.to_datetime(d.ts_generation.iloc[i:i+37],unit='ms',utc=True)
        real=np.r_[d.humidity_soil.iloc[i],d.humidity_soil_fim.iloc[i:i+36]]
        ax.plot(times,real,color='#142e3b',lw=3,label='Sensor de solo')
        for label,color in zip(selected,['#929ba1','#17897e','#bb7935','#793b99']):
            m=models[label];pred=m.trajetorias(d,np.array([i]),36)[0]
            suffix=' · escolhido' if (m.p,m.q)==(chosen.p,chosen.q) else ''
            ax.plot(times,np.r_[real[0],pred],color=color,ls='--',lw=2.2,label=f'H: {m.p}; irrigação: {m.q} atrasos'+suffix)
        ax.set(title=times.iloc[0].strftime('%d/%m/%Y · 6 h'),ylabel='Umidade do solo (%)',xlabel='Horário UTC')
        ax.xaxis.set_major_locator(md.HourLocator(interval=2));ax.xaxis.set_major_formatter(md.DateFormatter('%H:%M'));ax.grid(alpha=.2)
    handles,labels=axs[0].get_legend_handles_labels()
    fig.legend(handles,labels,ncol=3,loc='upper left',bbox_to_anchor=(.055,1.075),fontsize=13,frameon=False,borderaxespad=0,columnspacing=1.2)
    fig.suptitle('Atrasos menores e modelo anterior · cada atraso equivale a 10 minutos',fontsize=19,y=1.15,x=.055,ha='left')
    save(fig,out/'arx/comparacao_lags.png')
    grid=np.array([[scores.loc[lag_name(p,q)].min() for q in Q_GRID] for p in P_GRID])
    fig,ax=plt.subplots(figsize=(13,7),layout='constrained')
    im=ax.imshow(grid,cmap='YlGnBu',aspect='auto')
    ax.set(xticks=range(len(Q_GRID)),xticklabels=Q_GRID,yticks=range(len(P_GRID)),yticklabels=P_GRID,
           xlabel='Atrasos de volume de irrigação',ylabel='Atrasos de umidade do solo',
           title='Validação temporal · erro médio das trajetórias (p.p.)')
    for row,p in enumerate(P_GRID):
        for col,q in enumerate(Q_GRID):
            v=grid[row,col]
            ax.text(col,row,f'{v:.3f}'.replace('.',','),ha='center',va='center',fontsize=15,
                    color='white' if im.norm(v)>.55 else '#132d3c')
            if (p,q)==(chosen.p,chosen.q):
                ax.add_patch(Rectangle((col-.5,row-.5),1,1,fill=False,edgecolor='#e29717',lw=4))
    fig.colorbar(im,ax=ax,label='MAE · menor é melhor')
    save(fig,out/'arx/grade_atrasos.png')


def complete_series(raw,out):
    d=raw.copy();d['tempo']=pd.to_datetime(d.ts_generation,unit='ms',utc=True)
    fig,axs=plt.subplots(3,1,figsize=(17,10),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[2.3,1.1,1.1]})
    h=d.humidity_soil.copy();h[d.ts_generation.diff()>620000]=np.nan
    axs[0].plot(d.tempo,h,color='#183747',lw=1.4);axs[0].set(ylabel='Umidade do solo (%RH)',title='Linha 3 · 2024 | Umidade, irrigação e chuva · acumulados diários disponíveis')
    daily=d.set_index('tempo')[['delta_volume','precipitation_mm']].resample('D').sum(min_count=1)
    axs[1].bar(daily.index,daily.delta_volume,width=.8,color='#ce7a24');axs[1].set_ylabel('Irrigação por dia (m³)')
    axs[2].bar(daily.index,daily.precipitation_mm,width=.8,color='#2b80b0');axs[2].set_ylabel('Chuva diária (mm)\nParma Urbana · ARPAE')
    for ax in axs:
        ax.axvspan(pd.Timestamp('2024-08-01',tz='UTC'),pd.Timestamp('2024-08-19',tz='UTC'),color='#b6ccdd',alpha=.3)
        ax.axvspan(pd.Timestamp('2024-08-19',tz='UTC'),pd.Timestamp('2024-09-04',tz='UTC'),color='#e5c789',alpha=.3)
        ax.grid(axis='y',alpha=.2);ax.tick_params(labelsize=16)
    axs[-1].xaxis.set_major_locator(md.WeekdayLocator(byweekday=md.MO,interval=2));axs[-1].xaxis.set_major_formatter(md.DateFormatter('%d/%m'));axs[-1].set_xlabel('Data (UTC) · azul: ajuste/validação temporal; amarelo: avaliação exploratória')
    save(fig,out/'regimes_2h/serie_completa.png')


def diagram(out,model):
    fig,ax=plt.subplots(figsize=(15,7),layout='constrained');ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    def box(x,y,w,h,text,color='#e8eff3'):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.012',facecolor=color,edgecolor='#365668',lw=1.4));ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=16)
    def arrow(x,y,x2,y2):ax.annotate('',xy=(x2,y2),xytext=(x,y),arrowprops=dict(arrowstyle='->',lw=2,color='#365668'))
    box(.03,.69,.33,.17,f'Umidade: inicializada pelo sensor\nAtual + {model.p} atrasos ({model.p*10} min)')
    box(.03,.40,.33,.17,f'Volume de irrigação\nAtual + {model.q} atrasos ({model.q*10} min)')
    box(.03,.11,.33,.17,'Temperatura do ar\nUmidade relativa do ar')
    box(.49,.39,.19,.21,'ARX + Ridge\nPrevê a variação\nde umidade','#dbe8ed')
    box(.78,.39,.19,.21,'Soma à umidade\nanterior\n→ próxima umidade','#e9dfef')
    for y in [.775,.485,.195]:arrow(.372,y,.48,.495)
    arrow(.692,.495,.768,.495)
    ax.annotate('',xy=(.195,.875),xytext=(.875,.615),arrowprops=dict(arrowstyle='->',lw=2,color='#793b99',connectionstyle='angle,angleA=90,angleB=0,rad=15'))
    ax.text(.65,.88,'Retorna ao histórico para o próximo passo',ha='center',fontsize=14,color='#793b99')
    ax.set_title('Planta escolhida: um único ARX recursivo · passo de 10 minutos',fontsize=22,pad=15)
    save(fig,out/'arx/fluxograma_arx.png')



def comparar_duas_componentes(d,models,out):
    """Compara parâmetros congelados; não estima nem usa a escolha para alterar ARX."""
    data=json.loads((CACHE/'duas_componentes_explorado.json').read_text())
    p=data['parameters'];delay=data['atraso_passos'];dose=data['dose_referencia']
    ar=2**(-(1/6)/p['meia_vida_rapida_h']);al=2**(-(1/6)/p['meia_vida_lenta_h'])
    h,u=d.humidity_soil.to_numpy(),d.delta_volume.to_numpy();t=d.ts_generation.to_numpy()
    rain=d.precipitation_mm.to_numpy();regular=np.abs(np.diff(t)-600000)<=20000
    rows=[]
    for horizon in [12,36,144]:
        candidates=janelas(d,horizon,CUT,STAMP('2024-09-02'))
        ids=np.array([i for i in candidates if i>=36 and regular[i-36:i+horizon].all()
                      and np.isfinite(u[i-36:i]).all() and np.isfinite(rain[i-36:i+horizon]).all()
                      and (rain[i-36:i+horizon]==0).all()],int)[::6]
        if not len(ids):continue
        past=u[ids[:,None]-np.arange(36,0,-1)];used=past[:,:-delay] if delay else past
        xr=p['ganho_por_dose']*p['fracao_rapida']/dose*(used*ar**np.arange(used.shape[1]-1,-1,-1)).sum(axis=1)
        xl=h[ids]-p['H_estrela']-xr;old=np.empty((len(ids),horizon));water=u[ids[:,None]+np.arange(-36,horizon)]
        for step in range(horizon):
            gain=p['ganho_por_dose']*water[:,36+step-delay]/dose
            xr=ar*xr+p['fracao_rapida']*gain
            climate=p['efeito_T_pp_por_C']*(d.temperature_env.to_numpy()[ids+step]-data['temperatura_ref'])
            climate+=p['efeito_RH_pp_por_percentual']*(d.humidity_env.to_numpy()[ids+step]-data['umidade_ar_ref'])
            xl=al*xl+(1-p['fracao_rapida'])*gain+(1-al)*climate
            old[:,step]=p['H_estrela']+xr+xl
        truth=d.humidity_soil_fim.to_numpy()[ids[:,None]+np.arange(horizon)]
        for label,pred in [('ARX único escolhido',models[NAMES[0]].trajetorias(d,ids,horizon)),
                           ('Duas componentes (explorado)',old),('Última umidade constante',np.repeat(h[ids,None],horizon,axis=1))]:
            err=pred-truth
            rows.append(dict(modelo=label,horizonte_h=horizon/6,n=len(ids),MAE=np.abs(err).mean(),MAE_final=np.abs(err[:,-1]).mean(),vies_final=err[:,-1].mean()))
    result=pd.DataFrame(rows)
    # result.to_csv(out/'arx/comparacao_modelos.csv',index=False)
    cells=[]
    for label in result.modelo.unique():
        z=result[result.modelo.eq(label)];cells.append([label]+[f'{z[z.horizonte_h.eq(h)].MAE.iloc[0]:.2f}'.replace('.',',') for h in [2,6,24]])
    ns=result.groupby('horizonte_h').n.first()
    table(out/'arx/comparacao_modelos.png','Comparação retrospectiva de modelos · janelas sem chuva',
          ['Modelo',f'MAE · 2 h\n{ns[2]} janelas',f'MAE · 6 h\n{ns[6]} janelas',f'MAE · 24 h\n{ns[24]} janelas'],cells,
          widths=[.49,.17,.17,.17],size=(16,4.6))
    return result

def medianas_apresentacao(med, out):
    fig,ax=plt.subplots(figsize=(16,9),layout='constrained')
    bars=ax.bar([f'{int(v)} min' for v in med.janela_min],med.mediana,
                color=['#26a69a','#285e89'],width=.5)
    ax.set(title='Volume em janelas com válvula aberta · linha 3, 2024',
           ylabel='Volume mediano (m³)',ylim=(0,med.mediana.max()*1.3))
    for bar,r in zip(bars,med.itertuples()):
        ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+8,
                f'{r.mediana:g}\n{r.n} janelas',ha='center',va='bottom')
    save(fig,out/'arx_inicial/medianas_apresentacao.png')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--saida',type=Path,default=RESULTADOS);args=parser.parse_args()
    out=args.saida.resolve()
    if not out.is_relative_to(ROOT):raise ValueError('Saída deve ficar dentro da raiz do projeto')
    for folder in ['arx','arx_inicial','regimes_2h']:(out/folder).mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':17,'axes.titlesize':19,'axes.labelsize':17,'xtick.labelsize':15,'ytick.labelsize':15,'axes.spines.top':False,'axes.spines.right':False})
    raw=pd.read_csv(CACHE/'dataset_chuva.csv');d=raw[raw.ts_generation.ge(START)&raw.ts_generation.lt(END)].reset_index(drop=True)
    models,cv,scores,periods,train=fit_cv(d)
    measures,cross=metrics(d,models);events=event_indices(d)
    m=models[NAMES[0]];m.salvar(out/'arx/modelo_escolhido.json')
    (out/'arx/variantes.json').write_text(json.dumps({name:models[name].__dict__ for name in NAMES[1:]},indent=2,ensure_ascii=False))
    # cv.to_csv(out/'arx/validacao.csv',index=False)
    # measures.to_csv(out/'arx/metricas.csv',index=False)
    # cross.to_csv(out/'arx/cruzamentos.csv',index=False)
    # periods.to_csv(out/'arx/periodos.csv',index=False)
    trajectories(d,models,events,out);lags_plot(d,models,events,scores,out);complete_series(raw,out);diagram(out,m)
    fmt=lambda v:f'{v:.2f}'.replace('.',',') if pd.notna(v) else '—'
    periods_rows=[[f'Rodada {r.rodada}',r.ajuste,r.validacao,str(r.n_treino),f'{r.n2} / {r.n6}'] for r in periods.itertuples()]
    periods_rows += [['Ajuste final','01–18/08','—',str(len(train)),'—'],['Av. exploratória','—','19/08–03/09','—',f'{len(janelas(d,12,CUT,END))} / {len(janelas(d,36,CUT,END))}']]
    table(out/'arx/periodos.png','Separação temporal com janelas sobrepostas · linha 3, 2024',['Etapa','Ajuste','Validação / avaliação','Intervalos de treino','Janelas de 2h / 6h'],periods_rows,widths=[.19,.16,.23,.2,.22],size=(16,5.5))
    labels=NAMES+['Última umidade constante'];metric_rows=[]
    display={NAMES[0]:'ARX base',NAMES[1]:'Base + ambientais',NAMES[2]:'Base + ambientais + chuva',
             labels[-1]:'Umidade constante'}
    # Formata o erro absoluto na escala do sensor, sem normalização.
    percent=lambda v:fmt(v)+'%'
    strata=[(6,'Todos'),(6,'Com irrigação'),(6,'Sem irrigação'),(24,'Todos')]
    for name in labels:
        z=measures[measures.modelo.eq(name)]
        metric_rows.append([display[name]]+[
            percent(z[(z.horizonte_h==h)&z.regime.eq(reg)].MAE.iloc[0]) for h,reg in strata])
    table(out/'arx/resultados.png','Erro médio da umidade do solo',
          ['Modelo','Com e sem\nirrigação', 'Com irrigação','Sem irrigação','Com irrigação'],metric_rows,
          groups=[(0,1,'Previsão'),(1,4,'Janelas de 6 h'),
                  (4,5,'Janelas de 24 h')],
          widths=[.30,.175,.175,.175,.175],size=(16,4.8))
    table(out/'arx/entradas.png','Entradas dos modelos',
          ['Modelo','Entradas do modelo base','Entradas adicionais'],[
        ['ARX base',f'Umidade: atual + {m.p} atrasos ({m.p*10} min)\nIrrigação: atual + {m.q} atrasos ({m.q*10} min)\nTemperatura e umidade relativa do ar','Nenhuma'],
        ['Base + ambientais','Todas as entradas do modelo base','GDD, pressão, CO₂\ne condutividade inicial'],
        ['Base + ambientais\n+ chuva','Todas as entradas do modelo base','Ambientais acima + precipitação (mm)\nParma Urbana · ARPAE (~4,5 km do solo)\nAcumulados de 15 min rateados em ~10 min']],
        widths=[.23,.37,.40],size=(17,5.5))
    cr=cross[(cross.horizonte_h==6)&cross.limiar.eq(27)&cross.modelo.isin(labels)]
    crrows=[[display[r.modelo],str(r.reais),str(r.detectados),str(r.perdidos),str(r.falsos),(fmt(r.erro_tempo_min)+' min' if pd.notna(r.erro_tempo_min) else '—')] for r in cr.itertuples()]
    table(out/'arx/cruzamentos.png','Sensor × modelos · janelas de 6 h',
          ['Modelo','Reais','Detectados','Perdidos','Falsos',
           'Erro médio de horário'],crrows,
          groups=[(0,1,'Com e sem irrigação'),
                  (1,5,'Janelas com subida da umidade do solo de <27% para ≥27%'),
                  (5,6,'Quando ambos cruzam')],
          widths=[.27,.10,.13,.12,.10,.28],size=(17,5.3))
    lagrows=[];lag_labels=[]
    for pp in P_GRID:
        lag_labels.append(min((lag_name(pp,qq) for qq in Q_GRID),key=lambda k:scores.loc[k].min()))
    lag_labels=list(dict.fromkeys(lag_labels+[lag_name(1,1),lag_name(m.p,1),lag_name(6,18)]))
    for label in lag_labels:
        mm=models[label];z=measures[measures.modelo.eq(label)&measures.horizonte_h.eq(6)&measures.regime.eq('Todos')]
        lagrows.append([str(mm.p),str(mm.q),f'{mm.alpha:g}'.replace('.',','),
                        f'{scores.loc[label].min():.3f}'.replace('.',','),f'{z.MAE.iloc[0]:.3f}'.replace('.',',')])
    chosen_row=lag_labels.index(lag_name(m.p,m.q))+1
    table(out/'arx/lags.png','Seleção de atrasos · melhores por umidade e referências',
          ['Atrasos de H','Atrasos de irrigação','Regularização (α)','MAE validação','MAE avaliação · 6 h'],lagrows,
          highlight_cells=[(chosen_row,j) for j in range(5)],
          hatch_label='Escolhido pela validação · erros em p.p. · inclui referência anterior H=6 / irrigação=18',
          widths=[.18,.22,.20,.20,.20],size=(17,7))
    grid_rows=[]
    for pp in P_GRID:
        for qq in Q_GRID:
            label=lag_name(pp,qq);mm=models[label]
            z=measures[measures.modelo.eq(label)&measures.horizonte_h.eq(6)&measures.regime.eq('Todos')].iloc[0]
            grid_rows.append(dict(p=pp,q=qq,alpha=mm.alpha,MAE_validacao=scores.loc[label].min(),
                                  MAE_avaliacao_6h=z.MAE,maior_polo_final=mm.maior_polo,
                                  escolhido=(pp,qq)==(m.p,m.q)))
    grid=pd.DataFrame(grid_rows)
    # grid.to_csv(out/'arx/grade_atrasos.csv',index=False)
    # Lê as medianas e gera a tabela e o gráfico de volume.
    med_source=RESULTADOS/'arx_inicial/medianas_janelas_abertas.csv'
    med=pd.read_csv(med_source)
    # if out!=RESULTADOS.resolve():
    #     (out/'arx_inicial/medianas_janelas_abertas.csv').write_bytes(med_source.read_bytes())
    table(out/'arx_inicial/medianas.png','Volume do contador em janelas com válvula aberta',['Janela','n','Mediana (m³)','25% (m³)','75% (m³)'],[[f'{int(r.janela_min)} min',str(int(r.n)),fmt(r.mediana),fmt(r.q25),fmt(r.q75)] for r in med.itertuples()],size=(13,3.7))
    medianas_apresentacao(med,out)
    comparison=comparar_duas_componentes(d,models,out)
    report(out,m)
    print('Saída:',out,flush=True)



def report(out,model):
    text=f'''# Metodologia

Dados da linha 3 de 2024, com passo de 10 min ±20 s. As variantes usam os mesmos inícios e exigem histórico contínuo de água e umidade, sem preencher lacunas dessas entradas.

A memória do ARX e a regularização são escolhidas em quatro rodadas temporais com treino crescente. A grade combina atrasos de umidade {P_GRID}, de água {Q_GRID} e alpha {ALPHAS}. O critério é o MAE recursivo de 2 e 6 h, com pesos iguais para os horizontes disponíveis e para as rodadas. A última rodada só tem janelas de 2 h, sem irrigação. Imputação das variáveis extras, padronização e coeficientes usam apenas o treino de cada rodada.

Após a escolha, o modelo é reajustado em 01–18/08. A avaliação de 19/08–03/09 é exploratória: esse período já havia sido inspecionado. As janelas se sobrepõem; não são amostras independentes. A configuração salva usa {model.p} atrasos de umidade, {model.q} de água e alpha={model.alpha:g}.

As previsões recebem umidade real apenas na inicialização. Depois usam a própria saída, com água e clima históricos. A condutividade fica congelada no início de cada janela. A chuva de Parma Urbana/ARPAE é observada a cada 15 min e rateada nos intervalos do medidor; não é uma medição no talhão.

Os erros são diferenças absolutas na escala de umidade, não percentuais relativos. Sem cruzamentos reais de 24%, não se valida o acionamento nesse limiar. A estabilidade autorregressiva não comprova resposta física correta nem economia de irrigação.

A comparação com o modelo de duas componentes é retrospectiva, com calibrações de períodos diferentes, e não participa da escolha do ARX.
'''
    destination=Path(__file__).resolve().parent/'RELATORIO.md'
    destination.write_text(text,encoding='utf-8')

if __name__=='__main__':main()
