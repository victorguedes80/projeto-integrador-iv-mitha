#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <time.h>
#include <sys/time.h>
#include <esp_sntp.h>
#include <Preferences.h>
#include "secrets.h"

// ===============================
// WIFI
// ===============================

const char* ssid = WIFI_SSID; //  rede de 2.4ghz
const char* password = WIFI_PASS;

// ===============================
// MQTT
// ===============================

// Broker HiveMQ na Azure (TLS)
const char* MQTT_HOST = MQTT_HOST_S;
const int MQTT_PORT = 8883;
const char* MQTT_USER = MQTT_USER_S;
const char* MQTT_PASS = MQTT_PASS_S;

const char* MQTT_CLIENT_ID = "esp32-irrigacao-01";
const char* MQTT_TOPIC = "irrigacao/esp32-01/dados";


WiFiClientSecure mqttWifi;
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
  "&timezone=America%2FFortaleza"
  "&timeformat=unixtime";       // horarios em Unix UTC

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
  uint32_t tsConsulta = 0;      // 0 = relogio ainda nao sincronizado
  uint32_t msConsulta = 0;      // millis() no momento da consulta
  float temperatura = 0;
  float umidadeRelativa = 0;
  bool disponivel = false;
};

LeituraSensor solo;
LeituraSensor chuva;
LeituraEstacao estacao;

// ===============================
// FILA OFFLINE
// ===============================

// Cada registro guarda uma leitura completa.
// Sem NTP, ts fica 0 e o horario e reconstruido
// depois a partir de ms (millis() da leitura).

struct Registro {
  uint32_t ms = 0;
  LeituraSensor solo;
  LeituraSensor chuva;
  LeituraEstacao estacao;
};

// 120 leituras = 2 horas sem conexao (1 por minuto)
const int FILA_MAX = 120;

// Maximo de envios por volta do loop,
// para nao travar as leituras
const int ENVIOS_POR_LOOP = 5;

Registro fila[FILA_MAX];
int filaInicio = 0;
int filaTamanho = 0;

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

// Converte um instante de millis() em timestamp Unix,
// usando o relogio atual como referencia.
// Retorna 0 se o relogio ainda nao foi sincronizado.

uint32_t reconstruirUnix(uint32_t ms) {
  uint32_t agora = obterUnix();

  if (agora == 0) {
    return 0;
  }

  // Subtracao sem sinal: funciona mesmo
  // quando millis() reinicia (a cada ~49 dias)
  uint32_t decorrido = (millis() - ms) / 1000;

  return agora - decorrido;
}

// ===============================
// NTP
// ===============================

bool ntpIniciado = false;

// Vira true quando o NTP acerta o relogio pela primeira vez
volatile bool ntpSincronizado = false;

// Chamada pelo ESP32 a cada sincronizacao NTP bem-sucedida
void aoSincronizarNTP(struct timeval* tv) {
  ntpSincronizado = true;
}

// Inicia o cliente NTP uma unica vez.
// Depois disso, o proprio ESP32 tenta sincronizar
// sozinho em segundo plano, sem precisar chamar de novo.

void iniciarNTP() {
  if (ntpIniciado) {
    return;
  }

  // Fuso de Fortaleza (UTC-3, sem horario de verao).
  // O timestamp Unix continua em UTC; o fuso so afeta
  // a exibicao do horario local no Monitor Serial.
  sntp_set_time_sync_notification_cb(aoSincronizarNTP);

  configTzTime(
    "<-03>3",
    "pool.ntp.org",
    "time.google.com",
    "a.st1.ntp.br"
  );

  ntpIniciado = true;
  Serial.println("Cliente NTP iniciado");
}

// ===============================
// HORA PELO COMPUTADOR (SEM NTP)
// ===============================

// Ordem de prioridade do relogio:
//   1. NTP (quando a rede permitir);
//   2. hora digitada no Monitor Serial;
//   3. hora da compilacao, so no 1o boot apos gravar.
// Nenhum programa extra e necessario no computador.

// Tempo medio entre compilar e o ESP comecar a rodar
// (compilacao final + upload + boot). Ajuste se necessario.
const uint32_t ATRASO_GRAVACAO_S = 20;

// Dias desde 1970-01-01 (calendario gregoriano)
int32_t diasDesdeEpoch(int ano, int mes, int dia) {
  ano -= (mes <= 2);
  int era = (ano >= 0 ? ano : ano - 399) / 400;
  int anoEra = ano - era * 400;
  int diaAno = (153 * (mes > 2 ? mes - 3 : mes + 9) + 2) / 5 + dia - 1;
  int diaEra = anoEra * 365 + anoEra / 4 - anoEra / 100 + diaAno;
  return era * 146097 + diaEra - 719468;
}

// Converte data e hora de Fortaleza (UTC-3) em Unix UTC
uint32_t fortalezaParaUnix(int ano, int mes, int dia,
                           int hora, int minuto, int segundo) {
  return (uint32_t)diasDesdeEpoch(ano, mes, dia) * 86400UL
         + hora * 3600UL + minuto * 60UL + segundo
         + 3 * 3600UL;
}

void definirRelogio(uint32_t ts, const char* origem) {
  struct timeval tv;
  tv.tv_sec = (time_t)ts;
  tv.tv_usec = 0;
  settimeofday(&tv, nullptr);

  Serial.printf(
    "Relogio acertado (%s): %lu\n",
    origem,
    (unsigned long)ts
  );
}

// Hora em que este firmware foi compilado,
// no relogio do computador (Fortaleza)
uint32_t horaDaCompilacao() {
  char nomeMes[4];
  int dia, ano, hora, minuto, segundo;

  sscanf(__DATE__, "%3s %d %d", nomeMes, &dia, &ano);
  sscanf(__TIME__, "%d:%d:%d", &hora, &minuto, &segundo);

  const char* meses = "JanFebMarAprMayJunJulAugSepOctNovDec";
  int mes = (strstr(meses, nomeMes) - meses) / 3 + 1;

  return fortalezaParaUnix(ano, mes, dia, hora, minuto, segundo)
         + ATRASO_GRAVACAO_S;
}

// True apenas no primeiro boot depois de gravar este firmware.
// Nos boots seguintes, a hora da compilacao ja esta velha.
bool primeiroBootAposGravar() {
  Preferences prefs;
  prefs.begin("mitha", false);

  String atual = String(__DATE__) + " " + __TIME__;
  bool primeiro = (prefs.getString("build", "") != atual);

  if (primeiro) {
    prefs.putString("build", atual);
  }

  prefs.end();
  return primeiro;
}

char bufferSerial[24];
int tamanhoBufferSerial = 0;

// Aceita, no Monitor Serial:
//   "2026-11-18 12:05:30" ou "2026-11-18 12:05" (Fortaleza)
//   "T1795000000" (Unix UTC)
void aplicarHoraSerial(const char* linha) {
  if (ntpSincronizado) {
    Serial.println("NTP ja sincronizado: hora digitada ignorada");
    return;
  }

  uint32_t ts = 0;
  int ano, mes, dia, hora, minuto, segundo = 0;

  if (linha[0] == 'T') {
    ts = strtoul(linha + 1, nullptr, 10);
  } else if (sscanf(linha, "%d-%d-%d %d:%d:%d",
                    &ano, &mes, &dia,
                    &hora, &minuto, &segundo) >= 5) {
    ts = fortalezaParaUnix(ano, mes, dia, hora, minuto, segundo);
  }

  // Ignora valores claramente invalidos
  if (ts < 1700000000UL) {
    Serial.println("Formato invalido. Use: AAAA-MM-DD HH:MM:SS");
    return;
  }

  definirRelogio(ts, "Monitor Serial");
}

// Le a serial sem bloquear o loop
void lerHoraSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      bufferSerial[tamanhoBufferSerial] = '\0';
      aplicarHoraSerial(bufferSerial);
      tamanhoBufferSerial = 0;
      continue;
    }

    // Linha longa demais: descarta
    if (tamanhoBufferSerial >= (int)sizeof(bufferSerial) - 1) {
      tamanhoBufferSerial = 0;
      continue;
    }

    bufferSerial[tamanhoBufferSerial++] = c;
  }
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

  if (mqtt.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASS)) {
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

bool publicarMQTT(Registro& r) {
  if (!mqtt.connected()) {
    return false;
  }

  // Completa os timestamps de leituras feitas
  // antes de o relogio sincronizar
  bool reconstruido = false;

  if (r.solo.ts == 0) {
    uint32_t ts = reconstruirUnix(r.ms);

    // Relogio ainda sem NTP: espera para enviar
    if (ts == 0) {
      return false;
    }

    r.solo.ts = ts;
    r.chuva.ts = ts;
    reconstruido = true;
  }

  if (r.estacao.disponivel &&
      r.estacao.tsConsulta == 0) {
    r.estacao.tsConsulta =
      reconstruirUnix(r.estacao.msConsulta);
  }

  JsonDocument doc;

  // SOLO
  doc["solo"]["ts"] = r.solo.ts;
  doc["solo"]["adc"] = r.solo.adc;
  doc["solo"]["do"] = r.solo.digital;
  doc["solo"]["pct"] =
    roundf(r.solo.percentual * 10.0f) / 10.0f;

  // CHUVA
  doc["chuva"]["ts"] = r.chuva.ts;
  doc["chuva"]["adc"] = r.chuva.adc;
  doc["chuva"]["do"] = r.chuva.digital;
  doc["chuva"]["pct"] =
    roundf(r.chuva.percentual * 10.0f) / 10.0f;

  // ESTACAO
  if (r.estacao.disponivel) {
    doc["estacao"]["ts"] = r.estacao.ts;

    doc["estacao"]["ts_consulta"] =
      r.estacao.tsConsulta;

    doc["estacao"]["temp"] =
      roundf(r.estacao.temperatura * 10.0f) / 10.0f;

    doc["estacao"]["ur"] =
      roundf(r.estacao.umidadeRelativa * 10.0f) / 10.0f;
  } else {
    doc["estacao"] = nullptr;
  }

  // Indica que o horario foi calculado depois
  // (leitura feita sem NTP)
  if (reconstruido) {
    doc["ts_reconstruido"] = true;
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

    // Descarta o registro para nao travar a fila
    return true;
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
// FILA: INSERIR E ENVIAR
// ===============================

void enfileirar() {
  // Fila cheia: descarta a leitura mais antiga
  if (filaTamanho == FILA_MAX) {
    filaInicio = (filaInicio + 1) % FILA_MAX;
    filaTamanho--;

    Serial.println("Fila cheia: leitura mais antiga descartada");
  }

  int fim = (filaInicio + filaTamanho) % FILA_MAX;

  fila[fim].ms = millis();
  fila[fim].solo = solo;
  fila[fim].chuva = chuva;
  fila[fim].estacao = estacao;

  filaTamanho++;

  Serial.printf(
    "Leituras na fila: %d/%d\n",
    filaTamanho,
    FILA_MAX
  );
}

// Envia as leituras na ordem em que foram feitas.
// Para no primeiro erro e tenta de novo no proximo loop.

void enviarFila() {
  int enviados = 0;

  while (filaTamanho > 0 &&
         enviados < ENVIOS_POR_LOOP &&
         mqtt.connected()) {

    if (!publicarMQTT(fila[filaInicio])) {
      break;
    }

    filaInicio = (filaInicio + 1) % FILA_MAX;
    filaTamanho--;
    enviados++;

    // Processa o MQTT entre envios seguidos
    mqtt.loop();
  }
}

// ===============================
// LEITURA DOS SENSORES
// ===============================

void lerSensores() {
  // Sem NTP, ts = 0: o horario sera
  // reconstruido antes do envio
  uint32_t ts = obterUnix();

  // Solo
  solo.ts = ts;
  solo.adc = analogRead(SOLO_AO);
  solo.digital = digitalRead(SOLO_DO);

  solo.percentual =
    calcularUmidadeSolo(solo.adc);

  // Chuva
  chuva.ts = ts;
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

  // Guarda a leitura completa para envio
  enfileirar();
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
  // (tsConsulta = 0 se ainda nao houver NTP)
  uint32_t tsConsulta = obterUnix();
  uint32_t msConsulta = millis();

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

  // Com timeformat=unixtime, a API ja envia
  // o horario como timestamp Unix (UTC)
  uint32_t tsDados =
    doc["current"]["time"] | 0UL;

  if (tsDados == 0) {
    Serial.println("Timestamp meteorologico invalido");
    return false;
  }

  // Atualiza somente com resposta valida
  estacao.ts = tsDados;
  estacao.tsConsulta = tsConsulta;
  estacao.msConsulta = msConsulta;

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

  // Configura MQTT (TLS)
  mqttWifi.setInsecure();          // prototipo: nao valida o certificado
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  mqtt.setSocketTimeout(10);       // TLS precisa de mais tempo

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

    iniciarNTP();

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

  // Sem NTP no boot: usa a hora da compilacao
  // (so no primeiro boot apos gravar) ou pede
  // para digitar a hora no Monitor Serial
  bool primeiroBoot = primeiroBootAposGravar();

  if (obterUnix() == 0) {
    if (primeiroBoot) {
      definirRelogio(horaDaCompilacao(), "hora da compilacao");
    } else {
      Serial.println(
        "Sem hora valida. Digite no Monitor Serial "
        "(horario de Fortaleza): AAAA-MM-DD HH:MM:SS"
      );
    }
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
  // Hora enviada pelo computador (USB)
  lerHoraSerial();

  // Se o ESP ligou sem Wi-Fi, inicia o NTP
  // assim que a conexao aparecer
  if (!ntpIniciado &&
      WiFi.status() == WL_CONNECTED) {
    iniciarNTP();
  }

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

  // Envia as leituras acumuladas assim que
  // houver broker conectado e relogio valido
  enviarFila();
}