
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <time.h>

// ===============================
// WIFI
// ===============================

const char* ssid = "SUA_REDE"; //2.5ghz
const char* password = "SUA_SENHA";

// ===============================
// MQTT
// ===============================

// IP do computador onde roda o Mosquitto
const char* MQTT_HOST = "SEU_IP";
const int MQTT_PORT = 1883;

const char* MQTT_CLIENT_ID = "esp32-irrigacao-01";
const char* MQTT_TOPIC = "irrigacao/esp32-01/dados";

WiFiClient mqttWifi;
PubSubClient mqtt(mqttWifi);

const unsigned long MQTT_RETRY = 5UL * 1000;

unsigned long ultimaTentativaMQTT = 0;
bool primeiraTentativaMQTT = true;

// ===============================
// OPEN-METEO
// ===============================

const char* url =
  "https://api.open-meteo.com/v1/forecast"
  "?latitude=-3.73&longitude=-38.53"
  "&current=temperature_2m,relative_humidity_2m"
  "&timezone=America%2FFortaleza";

// ===============================
// PINOS
// ===============================

#define SOLO_AO 36
#define SOLO_DO 27

#define RAIN_AO 39
#define RAIN_DO 26

// ===============================
// INTERVALOS
// ===============================

const unsigned long SENSOR_AMOSTRAGEM =
  1UL * 60 * 1000;       // 1 minuto

const unsigned long ESTACAO_AMOSTRAGEM =
  15UL * 60 * 1000;      // 15 minutos

const unsigned long RETRY =
  10UL * 1000;           // 10 segundos

unsigned long ultimaLeitura = 0;
unsigned long ultimaConsulta = 0;
unsigned long ultimaTentativa = 0;

int tentativas = 0;

bool pendente = true;
bool inicializado = false;

// ===============================
// CALIBRACAO PROVISORIA
// ===============================

// Sensor de umidade do solo
const int SOLO_SECO = 4095;
const int SOLO_MOLHADO = 1600;

// Sensor de chuva
const int CHUVA_SECO = 4095;
const int CHUVA_MOLHADO = 1700;

// ===============================
// ESTRUTURAS DOS DADOS
// ===============================

struct LeituraSensor {
  uint32_t ts = 0;
  int adc = 0;
  int digital = 0;
  float percentual = 0;
};

struct LeituraEstacao {
  uint32_t ts = 0;
  uint32_t tsConsulta = 0;
  float temperatura = 0;
  float umidadeRelativa = 0;
  bool disponivel = false;
};

LeituraSensor solo;
LeituraSensor chuva;
LeituraEstacao estacao;

// Indica que ha dados locais para publicar
bool publicacaoPendente = false;

// ===============================
// TIMESTAMP UNIX
// ===============================

uint32_t obterUnix() {
  time_t agora = time(nullptr);

  // NTP ainda nao sincronizado
  if (agora < 1700000000) {
    return 0;
  }

  return (uint32_t)agora;
}

// Converte horario local da Open-Meteo para timestamp Unix UTC.

uint32_t converterHorarioMeteo(const char* horario) {
  int ano, mes, dia, hora, minuto;

  if (sscanf(
        horario,
        "%d-%d-%dT%d:%d",
        &ano, &mes, &dia,
        &hora, &minuto
      ) != 5) {
    return 0;
  }

  if (ano < 2020 ||
      mes < 1 || mes > 12 ||
      dia < 1 || dia > 31 ||
      hora < 0 || hora > 23 ||
      minuto < 0 || minuto > 59) {
    return 0;
  }

  struct tm data = {};

  data.tm_year = ano - 1900;
  data.tm_mon = mes - 1;
  data.tm_mday = dia;
  data.tm_hour = hora;
  data.tm_min = minuto;
  data.tm_sec = 0;
  data.tm_isdst = 0;

  // timegm interpreta a data como UTC.
  // Como UTC-3, +3 horas.
  time_t resultado = mktime(&data);

  if (resultado < 0 ||
      resultado > 0xFFFFFFFFLL) {
    return 0;
  }

  return (uint32_t)resultado;
}

// ===============================
// CONVERSOES DOS SENSORES
// ===============================

float calcularUmidadeSolo(int adc) {
  float umidade = 100.0 *
    (SOLO_SECO - adc) /
    (SOLO_SECO - SOLO_MOLHADO);

  return constrain(umidade, 0.0, 100.0);
}

float calcularMolhamento(int adc) {
  float molhamento = 100.0 *
    (CHUVA_SECO - adc) /
    (CHUVA_SECO - CHUVA_MOLHADO);

  return constrain(molhamento, 0.0, 100.0);
}

// ===============================
// CONEXAO MQTT
// ===============================

void verificarMQTT() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  if (mqtt.connected()) {
    mqtt.loop();
    return;
  }

  unsigned long agora = millis();

  if (!primeiraTentativaMQTT &&
      agora - ultimaTentativaMQTT < MQTT_RETRY) {
    return;
  }

  primeiraTentativaMQTT = false;
  ultimaTentativaMQTT = agora;

  Serial.println("Conectando ao MQTT...");

  if (mqtt.connect(MQTT_CLIENT_ID)) {
    Serial.println("MQTT conectado");
  } else {
    Serial.printf(
      "Falha MQTT, estado: %d\n",
      mqtt.state()
    );
  }
}

// ===============================
// PUBLICACAO MQTT
// ===============================

bool publicarMQTT() {
  if (!mqtt.connected()) {
    return false;
  }

  JsonDocument doc;

  // SOLO
  doc["solo"]["ts"] = solo.ts;
  doc["solo"]["adc"] = solo.adc;
  doc["solo"]["do"] = solo.digital;
  doc["solo"]["pct"] =
    roundf(solo.percentual * 10.0f) / 10.0f;

  // CHUVA
  doc["chuva"]["ts"] = chuva.ts;
  doc["chuva"]["adc"] = chuva.adc;
  doc["chuva"]["do"] = chuva.digital;
  doc["chuva"]["pct"] =
    roundf(chuva.percentual * 10.0f) / 10.0f;

  // ESTACAO
  if (estacao.disponivel) {
    doc["estacao"]["ts"] = estacao.ts;

    doc["estacao"]["ts_consulta"] =
      estacao.tsConsulta;

    doc["estacao"]["temp"] =
      roundf(estacao.temperatura * 10.0f) / 10.0f;

    doc["estacao"]["ur"] =
      roundf(estacao.umidadeRelativa * 10.0f) / 10.0f;
  } else {
    doc["estacao"] = nullptr;
  }

  char mensagem[512];

  size_t tamanho = serializeJson(
    doc,
    mensagem,
    sizeof(mensagem)
  );

  if (tamanho == 0 ||
      tamanho >= sizeof(mensagem)) {
    Serial.println("Erro: JSON muito grande");
    return false;
  }

  bool sucesso = mqtt.publish(
    MQTT_TOPIC,
    (const uint8_t*)mensagem,
    tamanho,
    false
  );

  if (sucesso) {
    Serial.println("\n--- MQTT publicado ---");
    Serial.println(mensagem);
  } else {
    Serial.println("Falha ao publicar MQTT");
  }

  return sucesso;
}

// ===============================
// LEITURA DOS SENSORES
// ===============================

void lerSensores() {
  // Solo
  solo.ts = obterUnix();
  solo.adc = analogRead(SOLO_AO);
  solo.digital = digitalRead(SOLO_DO);

  solo.percentual =
    calcularUmidadeSolo(solo.adc);

  // Chuva
  chuva.ts = obterUnix();
  chuva.adc = analogRead(RAIN_AO);
  chuva.digital = digitalRead(RAIN_DO);

  chuva.percentual =
    calcularMolhamento(chuva.adc);

  Serial.println("\n--- Sensores locais ---");

  Serial.printf(
    "Solo | TS: %lu | AO: %d | DO: %d | Umidade estimada: %.1f %%\n",
    (unsigned long)solo.ts,
    solo.adc,
    solo.digital,
    solo.percentual
  );

  Serial.printf(
    "Chuva | TS: %lu | AO: %d | DO: %d | Molhamento: %.1f %%\n",
    (unsigned long)chuva.ts,
    chuva.adc,
    chuva.digital,
    chuva.percentual
  );

  // Solicita publicacao do conjunto completo
  publicacaoPendente = true;
}

// ===============================
// CONSULTA METEOROLOGICA
// ===============================

bool consultarMeteo() {
  WiFiClientSecure client;

  // Apenas para prototipo
  client.setInsecure();

  HTTPClient http;

  http.setTimeout(10000);
  http.useHTTP10(true);

  if (!http.begin(client, url)) {
    return false;
  }

  // Instante de inicio da consulta
  uint32_t tsConsulta = obterUnix();

  int status = http.GET();

  Serial.printf("HTTP: %d\n", status);

  if (status != 200) {
    http.end();
    return false;
  }

  JsonDocument doc;

  DeserializationError erro =
    deserializeJson(doc, http.getStream());

  http.end();

  if (erro) {
    Serial.printf(
      "Erro JSON: %s\n",
      erro.c_str()
    );

    return false;
  }

  JsonVariant tempJson =
    doc["current"]["temperature_2m"];

  JsonVariant umidJson =
    doc["current"]["relative_humidity_2m"];

  if (!tempJson.is<float>() &&
      !tempJson.is<int>()) {
    return false;
  }

  if (!umidJson.is<float>() &&
      !umidJson.is<int>()) {
    return false;
  }

  const char* horarioAPI =
    doc["current"]["time"] | "";

  uint32_t tsDados =
    converterHorarioMeteo(horarioAPI);

  if (tsDados == 0 || tsConsulta == 0) {
    Serial.println("Timestamp meteorologico invalido");
    return false;
  }

  // Atualiza somente com resposta valida
  estacao.ts = tsDados;
  estacao.tsConsulta = tsConsulta;

  estacao.temperatura =
    tempJson.as<float>();

  estacao.umidadeRelativa =
    umidJson.as<float>();

  estacao.disponivel = true;

  Serial.println("\n--- Open-Meteo ---");

  Serial.printf(
    "Timestamp consulta: %lu\n",
    (unsigned long)estacao.tsConsulta
  );

  Serial.printf(
    "Timestamp dados API: %lu\n",
    (unsigned long)estacao.ts
  );

  Serial.printf(
    "Temperatura: %.1f C\n",
    estacao.temperatura
  );

  Serial.printf(
    "Umidade relativa: %.1f %%\n",
    estacao.umidadeRelativa
  );

  return true;
}

// ===============================
// SETUP
// ===============================

void setup() {
  Serial.begin(115200);

  pinMode(SOLO_DO, INPUT);
  pinMode(RAIN_DO, INPUT);

  analogReadResolution(12);

  // Configura MQTT
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  mqtt.setSocketTimeout(2);

  // Wi-Fi
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Conectando Wi-Fi");

  unsigned long inicio = millis();

  while (
    WiFi.status() != WL_CONNECTED &&
    millis() - inicio < 15000
  ) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWi-Fi conectado");

    // Fortaleza UTC-3
    configTime(
      -3 * 3600,
      0,
      "pool.ntp.org",
      "time.google.com"
    );

    struct tm horario;

    if (getLocalTime(&horario, 10000)) {
      Serial.println(
        &horario,
        "Horario: %Y-%m-%d %H:%M:%S"
      );
    } else {
      Serial.println("Falha ao sincronizar NTP");
    }

    // Primeira tentativa MQTT
    verificarMQTT();

  } else {
    Serial.println("\nFalha na conexao Wi-Fi");
  }

  // Inicia a consulta meteorologica
  // imediatamente no primeiro loop
  tentativas = 0;
  pendente = true;

  ultimaTentativa = millis() - RETRY;
}

// ===============================
// LOOP
// ===============================

void loop() {
  // Mantem o MQTT conectado
  verificarMQTT();

  unsigned long agora = millis();

  // --------------------------------
  // CONSULTA METEOROLOGICA
  // --------------------------------

  if (pendente &&
      agora - ultimaTentativa >= RETRY) {

    ultimaTentativa = agora;
    tentativas++;

    Serial.printf(
      "\nTentativa API %d/3\n",
      tentativas
    );

    bool sucesso = false;

    if (WiFi.status() == WL_CONNECTED) {
      sucesso = consultarMeteo();
    } else {
      Serial.println("Wi-Fi desconectado");
    }

    if (sucesso || tentativas >= 3) {
      pendente = false;

      // Primeira sequencia:
      // API primeiro, sensores depois
      if (!inicializado) {
        inicializado = true;

        lerSensores();

        // Inicia os dois intervalos
        // somente apos a coleta inicial
        unsigned long inicioColetas = millis();

        ultimaLeitura = inicioColetas;
        ultimaConsulta = inicioColetas;
      }
    }
  }

  // Aguarda a primeira consulta
  // ser concluida ou esgotar tentativas
  if (!inicializado) {
    return;
  }

  agora = millis();

  // --------------------------------
  // SENSORES LOCAIS - 1 MINUTO
  // --------------------------------

  if (agora - ultimaLeitura >=
      SENSOR_AMOSTRAGEM) {

    ultimaLeitura = agora;

    lerSensores();
  }



  // --------------------------------
  // OPEN-METEO - 15 MINUTOS
  // --------------------------------

  if (!pendente &&
      agora - ultimaConsulta >=
      ESTACAO_AMOSTRAGEM) {

    ultimaConsulta = agora;

    tentativas = 0;
    pendente = true;

    // Permite primeira tentativa imediata
    ultimaTentativa = agora - RETRY;
  }

  // --------------------------------
  // PUBLICACAO MQTT
  // --------------------------------

  // Mantem uma publicacao pendente
  // caso o broker esteja desconectado
  if (publicacaoPendente &&
      mqtt.connected()) {

    if (publicarMQTT()) {
      publicacaoPendente = false;
    }
  }
}
