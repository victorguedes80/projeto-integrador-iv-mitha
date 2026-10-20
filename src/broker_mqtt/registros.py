
import json
from pathlib import Path
import paho.mqtt.client as mqtt

PORTA = 1883
BROKER = "10.43.101.163"
TOPICO = "irrigacao/esp32-01/dados"

# Caminho do arquivo de registros
RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / "data" / "esp" / "dados.jsonl"

ARQUIVO.parent.mkdir(parents=True, exist_ok=True)

def ao_conectar(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Conectado ao broker!")
        client.subscribe(TOPICO)
    else:
        print("Erro de conexão:", reason_code)

def ao_receber(client, userdata, msg):
    try:
        dados = json.loads(msg.payload.decode("utf-8"))

        with ARQUIVO.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(dados, ensure_ascii=False) + "\n")

        print("Registro salvo:", dados)

    except (ValueError, UnicodeDecodeError) as erro:
        print("JSON inválido:", erro)
    except OSError as erro:
        print("Erro ao salvar registro:", erro)

cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
cliente.on_connect = ao_conectar
cliente.on_message = ao_receber

cliente.connect(BROKER, PORTA, 60)
cliente.loop_forever()
