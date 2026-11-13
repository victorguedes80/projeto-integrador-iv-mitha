import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../theme/mitha_colors.dart';
import '../theme/mitha_tokens.dart';

/// Ícones exportados do Figma (componentes icon/*) em assets/icons.
enum MithaIcons {
  gota, chuva, termometro, umidadeAr, irrigacao, wifiOff, alerta, ok, info,
  relogio, engrenagem, voltar, painel, historico, sino, seta;

  String get asset => 'assets/icons/${switch (this) {
        MithaIcons.umidadeAr => 'umidade_ar',
        MithaIcons.wifiOff => 'wifi_off',
        _ => name,
      }}.svg';
}

/// Equivale a uma instância de icon/* com a cor sobrescrita.
class MithaIcon extends StatelessWidget {
  const MithaIcon(this.icon, {super.key, this.color, this.size = 24});

  final MithaIcons icon;
  final Color? color;
  final double size;

  @override
  Widget build(BuildContext context) => SvgPicture.asset(
        icon.asset,
        width: size,
        height: size,
        colorFilter: ColorFilter.mode(color ?? MithaColors.of(context).texto, BlendMode.srcIn),
      );
}

/// Círculo com fundo a 16% da cor e o ícone na cor cheia
/// (no Figma: "Ícone de status" / "Ícone de tipo").
class IconBubble extends StatelessWidget {
  const IconBubble(this.icon, {super.key, required this.color, this.size = 40, this.iconSize = 20});

  final MithaIcons icon;
  final Color color;
  final double size;
  final double iconSize;

  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(color: MithaColors.tint(color), shape: BoxShape.circle),
        child: MithaIcon(icon, color: color, size: iconSize),
      );
}

/// Fundo de card padrão: cor `cartao`, raio 16, borda suave.
/// [borderColor] substitui a borda (estados de atenção/erro, largura 2).
class MithaCard extends StatelessWidget {
  const MithaCard({super.key, required this.child, this.borderColor, this.padding, this.onTap});

  final Widget child;
  final Color? borderColor;
  final EdgeInsetsGeometry? padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = MithaColors.of(context);
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(MithaRadius.lg),
      side: borderColor != null
          ? BorderSide(color: borderColor!, width: 2)
          : BorderSide(color: c.textoSec.withValues(alpha: 0.2)),
    );
    return Material(
      color: c.cartao,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(padding: padding ?? const EdgeInsets.all(MithaSpacing.lg), child: child),
      ),
    );
  }
}
