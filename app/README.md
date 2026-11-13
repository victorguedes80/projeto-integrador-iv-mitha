# MITHA — entrega do design para o Flutter (Passo 9)

Ponto de partida do app gerado a partir do arquivo **Mitha Mobile App** no Figma:
tema com as variáveis (claro e escuro), os estilos de texto, os tokens de espaçamento,
os 16 ícones em SVG e os widgets equivalentes aos componentes. A tela **Painel**
já vem montada como exemplo; as outras abas estão como "em construção".

> Este código não foi compilado aqui (o SDK do Flutter não estava disponível no
> ambiente de geração). Rode `flutter analyze` ao integrar e ajuste o que aparecer.
> O código usa `Color.withValues` e `CardThemeData`, que pedem **Flutter 3.32 ou mais recente**.

## Como integrar

1. Crie o projeto: `flutter create mitha_app` (ou use o existente).
2. Copie `lib/` e `assets/` para dentro do projeto.
3. Adicione as dependências (o `pub add` escolhe as versões atuais):
   ```bash
   flutter pub add flutter_svg fl_chart
   # quando for ligar à API e às notificações:
   flutter pub add http mqtt_client firebase_core firebase_messaging
   ```
4. Registre os ícones no `pubspec.yaml`:
   ```yaml
   flutter:
     uses-material-design: true
     assets:
       - assets/icons/
   ```
5. `flutter run`.

## Mapeamento Figma → Flutter

| Figma | Flutter |
|---|---|
| Coleção **Cores** (modos Claro/Escuro) | `MithaColors.claro` / `MithaColors.escuro` (`ThemeExtension`) + `ColorScheme` |
| Estilos de texto `Valor/Grande`, `Título/Tela`, `Título/Card`, `Corpo`, `Legenda` | `headlineMedium`, `titleLarge`, `titleMedium`, `bodyMedium`, `bodySmall` |
| Coleção **Dimensões** (`espacamento/*`, `raio/*`) | `MithaSpacing`, `MithaRadius` |
| Camada "Fundo (16%)" | `MithaColors.tint(cor)` |
| `icon/*` | `MithaIcon(MithaIcons.x, color:)` + `assets/icons/*.svg` |
| Card/Sensor (Normal, Atenção, Erro, Sem dados) | `SensorCard(estado: SensorState.x)` |
| Card/StatusSistema (5 estados) | `StatusCard(estado: SystemState.x)` |
| Item/Irrigacao (Modelo, Adiada, Regra local, Sem efeito) | `IrrigationItem(tipo: IrrigationType.x)` |
| Item/Alerta (Severidade × Lido) | `AlertItem(severidade:, lido:)` |
| Tag (5 tons) | `MithaTag(texto, tone: TagTone.x)` |
| Badge/Conexao | `ConnectionBadge(online:)` |
| Chip/Periodo | `ChoiceChip` (estilo em `chipTheme`) |
| Switch | `Switch` (estilo em `switchTheme`) |
| Seletor/Sensor | `DropdownMenu` |
| NavBar / NavItem | `NavigationBar` (estilo em `navigationBarTheme`) |
| AppBar (Principal / Com voltar) | `AppBar` (estilo em `appBarTheme`) |
| Notificação/Push | `firebase_messaging` (payload descrito abaixo) |
| Auto Layout vertical/horizontal | `Column` / `Row` com `SizedBox(MithaSpacing.x)` |
| Gráfico do Histórico | `fl_chart` `LineChart` + faixas de irrigação (`RangeAnnotations`) |

Os valores de enum (`em_espera`, `regra_local`, `critico`…) batem com os campos da API
via `fromApi()`.

## Dados de cada tela

As mesmas informações estão nas **anotações do Dev Mode** de cada tela na página `Telas`.

| Tela | Endpoints |
|---|---|
| 00_Login | `POST /auth/login` → token; depois `POST /dispositivos/fcm-token` |
| 01_Painel | `GET /status`, `GET /leituras/ultima`, `GET /dispositivo`; atualização por MQTT (WebSocket) ou polling de 30 s |
| 02_Histórico | `GET /historico?sensor=&periodo=dia\|semana\|safra`, `GET /irrigacoes?inicio=&fim=` |
| 03_Irrigações | `GET /irrigacoes?periodo=semana` |
| 04_Alertas | `GET /alertas`, `POST /alertas/{id}/lido`, `POST /alertas/lidos` |
| 05_Configurações | `GET /dispositivo`, `GET\|PUT /cultura/fase`, `GET\|PUT /preferencias/notificacoes` |
| 06_Detalhe do evento | `GET /alertas/{id}`, `GET /historico?inicio=&fim=`, `GET /leituras?em=` |
| 07_Notificações | FCM `data`: `{tipo, alerta_id, rota}` — toque abre a rota |

## Ícones

`assets/icons/`: gota, chuva, termometro, umidade_ar, irrigacao, wifi_off, alerta, ok,
info, relogio, engrenagem, voltar, painel, historico, sino, seta. Traço de 2 px em grade de 24 px;
a cor vem do `colorFilter` do `MithaIcon`, então o mesmo arquivo serve para qualquer cor.

## Dev Mode

No Figma, ative **Dev Mode** (Shift + D) e selecione qualquer elemento para ver medidas,
espaçamentos, a variável de cor ligada e o estilo de texto. As anotações de API aparecem
em cada tela.
