import json
import os
import ssl
import sys
from pathlib import Path
import paho.mqtt.client as mqtt

# Broker HiveMQ na Azure (TLS)
PORTA = 8883
TOPICO = "irrigacao/esp32-01/dados"

# Credenciais lidas de variaveis de ambiente (nao versionar senhas)
try:
    BROKER = os.environ["HIVEMQ_HOST"]
    USUARIO = os.environ["HIVEMQ_USER"]
    SENHA = os.environ["HIVEMQ_PASS"]
except KeyError as falta:
    sys.exit(f"Variavel de ambiente {falta} nao definida. Veja o README.")

# Caminho do arquivo de registros
# registros.py -> broker_mqtt -> data -> src -> raiz do repositorio
RAIZ = Path(__file__).resolve().parents[3]
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

cliente = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="mitha-registros"
)
cliente.username_pw_set(USUARIO, SENHA)
cliente.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

cliente.on_connect = ao_conectar
cliente.on_message = ao_receber

cliente.connect(BROKER, PORTA, 60)
cliente.loop_forever()
