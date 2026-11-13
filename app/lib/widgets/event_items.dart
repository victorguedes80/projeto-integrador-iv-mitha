import 'package:flutter/material.dart';

import '../theme/mitha_colors.dart';
import '../theme/mitha_tokens.dart';
import 'mitha_icon.dart';
import 'mitha_tag.dart';

/// Componente Figma: Item/Irrigacao (variante Tipo).
/// Mapeia o campo `tipo` de `GET /irrigacoes`.
enum IrrigationType {
  modelo('modelo'),
  adiada('adiada'),
  regraLocal('regra_local'),
  semEfeito('sem_efeito');

  const IrrigationType(this.api);
  final String api;
  static IrrigationType fromApi(String v) => values.firstWhere((e) => e.api == v, orElse: () => modelo);
}

class IrrigationItem extends StatelessWidget {
  const IrrigationItem({
    super.key,
    required this.tipo,
    required this.horarioEDuracao, // ex.: "06:12 · 12 min"
    required this.etiqueta, // ex.: "Modelo · 87%"
    required this.motivo,
    this.onTap,
  });

  final IrrigationType tipo;
  final String horarioEDuracao;
  final String etiqueta;
  final String motivo;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = MithaColors.of(context);
    final t = Theme.of(context).textTheme;
    final (MithaIcons icone, Color cor, TagTone tom) = switch (tipo) {
      IrrigationType.modelo => (MithaIcons.irrigacao, c.agua, TagTone.agua),
      IrrigationType.adiada => (MithaIcons.chuva, c.alerta, TagTone.alerta),
      IrrigationType.regraLocal => (MithaIcons.alerta, c.alerta, TagTone.alerta),
      IrrigationType.semEfeito => (MithaIcons.alerta, c.erro, TagTone.erro),
    };
    return MithaCard(
      onTap: onTap,
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        IconBubble(icone, color: cor),
        const SizedBox(width: MithaSpacing.md),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(horarioEDuracao, style: t.titleMedium)),
              const SizedBox(width: MithaSpacing.sm),
              MithaTag(etiqueta, tone: tom),
            ]),
            const SizedBox(height: MithaSpacing.xs),
            Text(motivo, style: t.bodyMedium!.copyWith(color: c.textoSec)),
          ]),
        ),
      ]),
    );
  }
}

/// Componente Figma: Item/Alerta (variantes Severidade × Lido).
/// Mapeia `GET /alertas`.
enum AlertSeverity {
  info('info'),
  atencao('atencao'),
  critico('critico');

  const AlertSeverity(this.api);
  final String api;
  static AlertSeverity fromApi(String v) => values.firstWhere((e) => e.api == v, orElse: () => info);
}

class AlertItem extends StatelessWidget {
  const AlertItem({
    super.key,
    required this.severidade,
    required this.titulo,
    required this.descricao,
    required this.horario,
    this.lido = false,
    this.onTap,
  });

  final AlertSeverity severidade;
  final String titulo;
  final String descricao;
  final String horario;
  final bool lido;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = MithaColors.of(context);
    final t = Theme.of(context).textTheme;
    final (MithaIcons icone, Color cor) = switch (severidade) {
      AlertSeverity.info => (MithaIcons.info, c.agua),
      AlertSeverity.atencao => (MithaIcons.alerta, c.alerta),
      AlertSeverity.critico => (MithaIcons.wifiOff, c.erro),
    };
    final card = MithaCard(
      borderColor: (!lido && severidade == AlertSeverity.critico) ? c.erro : null,
      onTap: onTap,
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        IconBubble(icone, color: cor),
        const SizedBox(width: MithaSpacing.md),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(titulo, style: t.titleMedium!.copyWith(color: lido ? c.textoSec : c.texto)),
            const SizedBox(height: MithaSpacing.xs),
            Text(descricao, style: t.bodyMedium!.copyWith(color: c.textoSec)),
            const SizedBox(height: MithaSpacing.xs),
            Text(horario, style: t.bodySmall),
          ]),
        ),
        if (!lido)
          Container(
            width: 8,
            height: 8,
            margin: const EdgeInsets.only(left: MithaSpacing.sm, top: MithaSpacing.xs),
            decoration: BoxDecoration(color: c.primaria, shape: BoxShape.circle),
          ),
      ]),
    );
    return lido ? Opacity(opacity: 0.7, child: card) : card;
  }
}
