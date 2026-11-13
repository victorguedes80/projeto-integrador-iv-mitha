import 'package:flutter/material.dart';

import '../theme/mitha_colors.dart';
import '../theme/mitha_tokens.dart';

/// Componente Figma: Tag (variante Tom).
enum TagTone { primaria, agua, alerta, erro, neutra }

class MithaTag extends StatelessWidget {
  const MithaTag(this.label, {super.key, this.tone = TagTone.neutra});

  final String label;
  final TagTone tone;

  @override
  Widget build(BuildContext context) {
    final c = MithaColors.of(context);
    final base = switch (tone) {
      TagTone.primaria => c.primaria,
      TagTone.agua => c.agua,
      TagTone.alerta => c.alerta,
      TagTone.erro => c.erro,
      TagTone.neutra => c.textoSec,
    };
    // Alerta e Neutra usam texto padrão para manter contraste (igual ao Figma).
    final textColor = (tone == TagTone.alerta || tone == TagTone.neutra) ? c.texto : base;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: MithaSpacing.sm, vertical: 3),
      decoration: BoxDecoration(
        color: MithaColors.tint(base),
        borderRadius: BorderRadius.circular(MithaRadius.full),
      ),
      child: Text(label, style: Theme.of(context).textTheme.bodySmall!.copyWith(color: textColor)),
    );
  }
}

/// Componente Figma: Badge/Conexao (Online / Offline).
class ConnectionBadge extends StatelessWidget {
  const ConnectionBadge({super.key, required this.online, this.label});

  final bool online;
  final String? label;

  @override
  Widget build(BuildContext context) {
    final c = MithaColors.of(context);
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(color: online ? c.primaria : c.erro, shape: BoxShape.circle),
      ),
      const SizedBox(width: MithaSpacing.sm),
      Text(label ?? (online ? 'ESP32 online' : 'ESP32 offline'), style: Theme.of(context).textTheme.bodySmall),
    ]);
  }
}
