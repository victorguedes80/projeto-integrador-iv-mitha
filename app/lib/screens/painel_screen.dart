import 'package:flutter/material.dart';

import '../theme/mitha_tokens.dart';
import '../widgets/mitha_icon.dart';
import '../widgets/mitha_tag.dart';
import '../widgets/sensor_card.dart';
import '../widgets/status_card.dart';

/// Tela Figma: 01_Painel.
/// Dados (ver anotação no Figma): GET /status, GET /leituras/ultima, GET /dispositivo.
/// Os valores abaixo são de exemplo; troque pelos dados da API.
class PainelScreen extends StatelessWidget {
  const PainelScreen({super.key, this.onAbrirConfiguracoes, this.onAbrirHistorico, this.onAbrirIrrigacoes});

  final VoidCallback? onAbrirConfiguracoes;
  final VoidCallback? onAbrirHistorico;
  final VoidCallback? onAbrirIrrigacoes;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    Widget sensor(String n, String v, String u, MithaIcons i) => Expanded(
          child: SensorCard(nome: n, valor: v, unidade: u, icone: i, onTap: onAbrirHistorico),
        );

    return Scaffold(
      appBar: AppBar(
        title: const Text('MITHA'),
        actions: [
          IconButton(
            tooltip: 'Configurações',
            onPressed: onAbrirConfiguracoes,
            icon: const MithaIcon(MithaIcons.engrenagem),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(MithaSpacing.tela),
        children: [
          StatusCard(
            estado: SystemState.emEspera,
            titulo: 'Em espera',
            descricao: 'Solo adequado · próxima verificação em 4 min',
            onTap: onAbrirIrrigacoes,
          ),
          const SizedBox(height: MithaSpacing.lg),
          Text('Sensores agora', style: t.titleMedium),
          const SizedBox(height: MithaSpacing.lg),
          Row(children: [
            sensor('Umidade do solo', '42', '%', MithaIcons.gota),
            const SizedBox(width: MithaSpacing.md),
            sensor('Chuva', 'Não', '', MithaIcons.chuva),
          ]),
          const SizedBox(height: MithaSpacing.md),
          Row(children: [
            sensor('Temperatura do ar', '31', '°C', MithaIcons.termometro),
            const SizedBox(width: MithaSpacing.md),
            sensor('Umidade do ar', '68', '%', MithaIcons.umidadeAr),
          ]),
          const SizedBox(height: MithaSpacing.lg),
          Row(children: [
            const ConnectionBadge(online: true),
            const SizedBox(width: MithaSpacing.sm),
            Text('· última leitura há 1 min', style: t.bodySmall),
          ]),
        ],
      ),
    );
  }
}
