import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import urllib.request
import json
from datetime import datetime

=
# BUSCANDO OS DADOS REAIS DE FORTALEZA (OPEN-METEO)

print("Buscando dados de Fortaleza no Open-Meteo...")

# Coordenadas de Fortaleza
LATITUDE = -3.73
LONGITUDE = -38.53

# hourly: variáveis horárias
# past_days=7: pega os últimos 7 dias para ter uma amostra representativa
# timezone: America/Fortaleza para alinhar a hora local
url = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LATITUDE}&longitude={LONGITUDE}"
    "&hourly=temperature_2m,relative_humidity_2m"
    "&past_days=7"
    "&timezone=America%2FFortaleza"
)

try:
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
    
    # Extrai os arrays horários
    horas_str = data['hourly']['time']
    temps = data['hourly']['temperature_2m']
    umids = data['hourly']['relative_humidity_2m']
    
    # Cria DataFrame
    df_fortaleza = pd.DataFrame({
        'timestamp': pd.to_datetime(horas_str),
        'temp': temps,
        'umid': umids
    })
    
    # Extrai a hora do dia (0 a 23)
    df_fortaleza['hora'] = df_fortaleza['timestamp'].dt.hour
    
    # Calcula a média por hora do dia (ciclo diário)
    ciclo_fortaleza = df_fortaleza.groupby('hora').agg({
        'temp': 'mean',
        'umid': 'mean'
    }).reset_index()
    
    print(f"Dados de Fortaleza carregados: {len(df_fortaleza)} registros horários.")

except Exception as e:
    print(f"Erro ao buscar dados do Open-Meteo: {e}")
    print("Usando dados simulados como fallback...")
    # Fallback caso a internet falhe
    horas = np.arange(24)
    ciclo_fortaleza = pd.DataFrame({
        'hora': horas,
        'temp': [25.5, 25.2, 25.0, 24.8, 24.7, 24.9, 26.0, 27.5, 29.0, 30.2, 30.8, 31.2, 31.5, 31.2, 30.8, 30.0, 29.0, 28.0, 27.2, 26.8, 26.5, 26.2, 26.0, 25.8],
        'umid': [85, 87, 88, 89, 90, 88, 82, 75, 68, 62, 58, 56, 55, 56, 58, 62, 68, 75, 80, 83, 85, 86, 86, 85]
    })


# EXTRAIR CICLO DIÁRIO DA ITÁLIA

#Aqui carrega os dados de 2024, mas se quiser os de 2025, é só altera para 'dataset_m2_2025.csv'.
print("Carregando dados da Itália...")
df_italia = pd.read_csv('dataset_m2_2024.csv', parse_dates=['timestamp_10min'])

# O dataset está em UTC. Convertemos para o fuso horário da Itália (Europe/Rome) para alinhar o ciclo diário com o horário local.
df_italia['timestamp_local'] = df_italia['timestamp_10min'].dt.tz_convert('Europe/Rome')
df_italia['hora'] = df_italia['timestamp_local'].dt.hour

# Calcula a media por hora do dia
ciclo_italia = df_italia.groupby('hora').agg({
    'env_temperature': 'mean',
    'env_humidity': 'mean'
}).reset_index()


# GRÁFICOS

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# Gráfico 1: Temperatura
ax1.plot(ciclo_italia['hora'], ciclo_italia['env_temperature'], 
         marker='o', label='Itália (Parma)', color='blue', linewidth=2)
ax1.plot(ciclo_fortaleza['hora'], ciclo_fortaleza['temp'], 
         marker='s', label='Fortaleza (Open-Meteo)', color='red', linewidth=2)
ax1.set_title('Ciclo Diário - Temperatura do Ar')
ax1.set_xlabel('Hora do dia (horário local)')
ax1.set_ylabel('Temperatura (°C)')
ax1.set_xticks(range(0, 24, 2))
ax1.grid(True, alpha=0.3)
ax1.legend()

# Gráfico 2: Umidade
ax2.plot(ciclo_italia['hora'], ciclo_italia['env_humidity'], 
         marker='o', label='Itália (Parma)', color='blue', linewidth=2)
ax2.plot(ciclo_fortaleza['hora'], ciclo_fortaleza['umid'], 
         marker='s', label='Fortaleza (Open-Meteo)', color='red', linewidth=2)
ax2.set_title('Ciclo Diário - Umidade do Ar')
ax2.set_xlabel('Hora do dia (horário local)')
ax2.set_ylabel('Umidade Relativa (%)')
ax2.set_xticks(range(0, 24, 2))
ax2.grid(True, alpha=0.3)
ax2.legend()

plt.tight_layout()
plt.savefig('comparacao_ciclo_diario_fortaleza.png', dpi=300)
print("Gráfico salvo como 'comparacao_ciclo_diario_fortaleza.png'")
plt.show()