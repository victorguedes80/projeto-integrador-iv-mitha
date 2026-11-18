#pragma once

// ============================================================
// MODELO DE CREDENCIAIS — NÃO coloque senhas reais aqui.
//
// Como usar:
//   1. Copie este arquivo e renomeie a cópia para "secrets.h"
//      (na mesma pasta do geralbroker.ino).
//   2. Preencha os valores reais no secrets.h.
//   3. O secrets.h está no .gitignore e NÃO vai para o GitHub.
// ============================================================

// Wi-Fi (rede 2,4 GHz)
#define WIFI_SSID   "NOME_DA_REDE"
#define WIFI_PASS   "SENHA_DA_REDE"

// Broker MQTT (HiveMQ na Azure, TLS na porta 8883)
#define MQTT_HOST_S "mitha-broker.chilecentral.cloudapp.azure.com"
#define MQTT_USER_S "mitha-esp32"
#define MQTT_PASS_S "SENHA_DO_USUARIO_MQTT"
