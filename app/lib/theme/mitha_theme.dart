import 'package:flutter/material.dart';

import 'mitha_colors.dart';
import 'mitha_tokens.dart';

/// Monta o ThemeData a partir das variáveis e estilos de texto do Figma.
///
/// Estilos de texto (Roboto) → TextTheme:
///   Valor/Grande 32/40 Bold   → headlineMedium
///   Título/Tela  22/28 Medium → titleLarge
///   Título/Card  16/24 Medium → titleMedium
///   Corpo        14/20 Regular→ bodyMedium
///   Legenda      12/16 Regular→ bodySmall
ThemeData buildMithaTheme(Brightness brightness) {
  final c = brightness == Brightness.light ? MithaColors.claro : MithaColors.escuro;

  final scheme = ColorScheme(
    brightness: brightness,
    primary: c.primaria,
    onPrimary: c.cartao,
    secondary: c.agua,
    onSecondary: c.cartao,
    tertiary: c.destaque,
    onTertiary: c.cartao,
    error: c.erro,
    onError: c.cartao,
    surface: c.superficie,
    onSurface: c.texto,
    onSurfaceVariant: c.textoSec,
    surfaceContainer: c.cartao,
    surfaceContainerLow: c.cartao,
    outline: c.textoSec.withValues(alpha: 0.45),
    outlineVariant: c.textoSec.withValues(alpha: 0.2),
  );

  TextStyle s(double size, double lineHeight, FontWeight w, Color color) => TextStyle(
        fontFamily: 'Roboto',
        fontSize: size,
        height: lineHeight / size,
        fontWeight: w,
        color: color,
      );

  final textTheme = TextTheme(
    headlineMedium: s(32, 40, FontWeight.w700, c.texto), // Valor/Grande
    titleLarge: s(22, 28, FontWeight.w500, c.texto), // Título/Tela
    titleMedium: s(16, 24, FontWeight.w500, c.texto), // Título/Card
    bodyMedium: s(14, 20, FontWeight.w400, c.texto), // Corpo
    bodySmall: s(12, 16, FontWeight.w400, c.textoSec), // Legenda
    labelMedium: s(12, 16, FontWeight.w500, c.texto), // rótulos da NavBar
  );

  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    scaffoldBackgroundColor: c.superficie,
    textTheme: textTheme,
    extensions: [c],
    appBarTheme: AppBarTheme(
      backgroundColor: c.superficie,
      foregroundColor: c.texto,
      elevation: 0,
      scrolledUnderElevation: 0,
      titleTextStyle: textTheme.titleLarge,
    ),
    cardTheme: CardThemeData(
      color: c.cartao,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(MithaRadius.lg),
        side: BorderSide(color: c.textoSec.withValues(alpha: 0.2)),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: c.cartao,
      indicatorColor: MithaColors.tint(c.primaria),
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => textTheme.labelMedium!.copyWith(
          color: states.contains(WidgetState.selected) ? c.texto : c.textoSec,
        ),
      ),
    ),
    chipTheme: ChipThemeData(
      selectedColor: c.primaria,
      backgroundColor: Colors.transparent,
      side: BorderSide(color: c.textoSec.withValues(alpha: 0.5)),
      shape: const StadiumBorder(),
      labelStyle: textTheme.bodyMedium,
      showCheckmark: false,
      padding: const EdgeInsets.symmetric(horizontal: MithaSpacing.sm, vertical: MithaSpacing.xs),
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStatePropertyAll(c.cartao),
      trackColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected) ? c.primaria : c.textoSec.withValues(alpha: 0.35),
      ),
      trackOutlineColor: const WidgetStatePropertyAll(Colors.transparent),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: c.primaria,
        foregroundColor: c.cartao,
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(MithaRadius.sm)),
        textStyle: textTheme.titleMedium,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: c.primaria,
        minimumSize: const Size.fromHeight(48),
        side: BorderSide(color: c.primaria, width: 1.5),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(MithaRadius.sm)),
        textStyle: textTheme.titleMedium,
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: c.cartao,
      hintStyle: textTheme.bodyMedium!.copyWith(color: c.textoSec),
      contentPadding: const EdgeInsets.symmetric(horizontal: MithaSpacing.md, vertical: MithaSpacing.lg),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(MithaRadius.sm),
        borderSide: BorderSide(color: c.textoSec.withValues(alpha: 0.45)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(MithaRadius.sm),
        borderSide: BorderSide(color: c.textoSec.withValues(alpha: 0.45)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(MithaRadius.sm),
        borderSide: BorderSide(color: c.primaria, width: 2),
      ),
    ),
  );
}
