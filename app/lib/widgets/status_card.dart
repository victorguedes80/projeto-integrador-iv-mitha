import 'package:flutter/material.dart';

import '../theme/mitha_colors.dart';
import '../theme/mitha_tokens.dart';
import 'mitha_icon.dart';

/// Componente Figma: Card/StatusSistema (variante Estado).
/// Mapeia o campo `estado` de `GET /status`.
enum SystemState {
  emEspera('em_espera'),
  irrigando('irrigando'),
  adiada('adiada'),
  modoLocal('modo_local'),
  offline('offline');

  const SystemState(this.api);
  final String api;

  static SystemState fromApi(String v) => values.firstWhere((e) => e.api == v, orElse: () => offline);
}

class StatusCard extends StatelessWidget {
  const StatusCard({super.key, required this.estado, required this.titulo, required this.descricao, this.onTap});

  final SystemState estado;
  final String titulo;
  final String descricao;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = MithaColors.of(context);
    final t = Theme.of(context).textTheme;
    final (MithaIcons icone, Color cor, bool destacar) = switch (estado) {
      SystemState.emEspera => (MithaIcons.ok, c.primaria, false),
      SystemState.irrigando => (MithaIcons.irrigacao, c.agua, false),
      SystemState.adiada => (MithaIcons.chuva, c.alerta, false),
      SystemState.modoLocal => (MithaIcons.alerta, c.alerta, true),
      SystemState.offline => (MithaIcons.wifiOff, c.erro, true),
    };

    return MithaCard(
      borderColor: destacar ? cor : null,
      onTap: onTap,
      child: Row(children: [
        IconBubble(icone, color: cor, size: 44, iconSize: 24),
        const SizedBox(width: MithaSpacing.md),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(titulo, style: t.titleMedium),
            const SizedBox(height: MithaSpacing.xs),
            Text(descricao, style: t.bodyMedium!.copyWith(color: c.textoSec)),
          ]),
        ),
      ]),
    );
  }
}
