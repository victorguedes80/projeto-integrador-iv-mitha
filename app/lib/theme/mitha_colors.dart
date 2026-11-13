import 'package:flutter/material.dart';

/// Coleção "Cores" do Figma, com os modos Claro e Escuro.
/// Acesse com `MithaColors.of(context).agua`.
@immutable
class MithaColors extends ThemeExtension<MithaColors> {
  const MithaColors({
    required this.primaria,
    required this.destaque,
    required this.agua,
    required this.alerta,
    required this.erro,
    required this.superficie,
    required this.cartao,
    required this.texto,
    required this.textoSec,
  });

  final Color primaria; // verde da planta, ações, status OK
  final Color destaque; // vermelho-tomate: marca e detalhes
  final Color agua; // irrigação, umidade, chuva
  final Color alerta; // atenção: adiamento, leitura estranha
  final Color erro; // falhas: sensor offline
  final Color superficie; // fundo das telas
  final Color cartao; // fundo dos cards
  final Color texto; // texto principal
  final Color textoSec; // texto secundário

  static const claro = MithaColors(
    primaria: Color(0xFF2E7D32),
    destaque: Color(0xFFE53935),
    agua: Color(0xFF1E88E5),
    alerta: Color(0xFFF9A825),
    erro: Color(0xFFC62828),
    superficie: Color(0xFFF7F9F6),
    cartao: Color(0xFFFFFFFF),
    texto: Color(0xFF1B1F1B),
    textoSec: Color(0xFF5F6B5F),
  );

  static const escuro = MithaColors(
    primaria: Color(0xFF81C784),
    destaque: Color(0xFFEF9A9A),
    agua: Color(0xFF90CAF9),
    alerta: Color(0xFFFFD54F),
    erro: Color(0xFFEF5350),
    superficie: Color(0xFF121512),
    cartao: Color(0xFF1E231E),
    texto: Color(0xFFE6E9E6),
    textoSec: Color(0xFFA5B0A5),
  );

  static MithaColors of(BuildContext context) =>
      Theme.of(context).extension<MithaColors>()!;

  /// Fundo claro usado nos círculos de ícone, tags e aba ativa
  /// (no Figma: camada "Fundo (16%)").
  static Color tint(Color c) => c.withValues(alpha: 0.16);

  @override
  MithaColors copyWith({
    Color? primaria,
    Color? destaque,
    Color? agua,
    Color? alerta,
    Color? erro,
    Color? superficie,
    Color? cartao,
    Color? texto,
    Color? textoSec,
  }) =>
      MithaColors(
        primaria: primaria ?? this.primaria,
        destaque: destaque ?? this.destaque,
        agua: agua ?? this.agua,
        alerta: alerta ?? this.alerta,
        erro: erro ?? this.erro,
        superficie: superficie ?? this.superficie,
        cartao: cartao ?? this.cartao,
        texto: texto ?? this.texto,
        textoSec: textoSec ?? this.textoSec,
      );

  @override
  MithaColors lerp(ThemeExtension<MithaColors>? other, double t) {
    if (other is! MithaColors) return this;
    return MithaColors(
      primaria: Color.lerp(primaria, other.primaria, t)!,
      destaque: Color.lerp(destaque, other.destaque, t)!,
      agua: Color.lerp(agua, other.agua, t)!,
      alerta: Color.lerp(alerta, other.alerta, t)!,
      erro: Color.lerp(erro, other.erro, t)!,
      superficie: Color.lerp(superficie, other.superficie, t)!,
      cartao: Color.lerp(cartao, other.cartao, t)!,
      texto: Color.lerp(texto, other.texto, t)!,
      textoSec: Color.lerp(textoSec, other.textoSec, t)!,
    );
  }
}
