import 'package:flutter/material.dart';

import '../theme/mitha_colors.dart';
import '../theme/mitha_tokens.dart';
import 'mitha_icon.dart';

/// Componente Figma: Card/Sensor (variante Estado).
enum SensorState { normal, atencao, erro, semDados }

class SensorCard extends StatelessWidget {
  const SensorCard({
    super.key,
    required this.nome,
    required this.valor,
    required this.unidade,
    required this.icone,
    this.estado = SensorState.normal,
    this.status = 'Há 1 min',
    this.onTap,
  });

  final String nome;
  final String valor;
  final String unidade;
  final MithaIcons icone;
  final SensorState estado;
  final String status;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = MithaColors.of(context);
    final t = Theme.of(context).textTheme;
    final semDados = estado == SensorState.semDados;
    final (Color? borda, MithaIcons? iconeStatus) = switch (estado) {
      SensorState.atencao => (c.alerta, MithaIcons.alerta),
      SensorState.erro => (c.erro, MithaIcons.wifiOff),
      _ => (null, null),
    };

    return MithaCard(
      borderColor: borda,
      onTap: onTap,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          MithaIcon(icone, size: 20, color: semDados ? c.textoSec : c.primaria),
          const SizedBox(width: MithaSpacing.sm),
          Expanded(child: Text(nome, style: t.bodyMedium!.copyWith(color: c.textoSec))),
        ]),
        const SizedBox(height: MithaSpacing.sm),
        Row(crossAxisAlignment: CrossAxisAlignment.baseline, textBaseline: TextBaseline.alphabetic, children: [
          Text(semDados ? '--' : valor, style: t.headlineMedium!.copyWith(color: semDados ? c.textoSec : c.texto)),
          const SizedBox(width: MithaSpacing.xs),
          Text(unidade, style: t.titleMedium!.copyWith(color: c.textoSec)),
        ]),
        const SizedBox(height: MithaSpacing.sm),
        Row(children: [
          if (iconeStatus != null) ...[
            MithaIcon(iconeStatus, size: 16, color: borda),
            const SizedBox(width: MithaSpacing.xs),
          ],
          Flexible(
            child: Text(
              semDados ? 'Aguardando leitura' : status,
              style: t.bodySmall!.copyWith(color: iconeStatus != null ? c.texto : c.textoSec),
            ),
          ),
        ]),
      ]),
    );
  }
}
