import 'package:flutter/material.dart';

import 'screens/painel_screen.dart';
import 'theme/mitha_theme.dart';
import 'widgets/mitha_icon.dart';

void main() => runApp(const MithaApp());

class MithaApp extends StatelessWidget {
  const MithaApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'MITHA',
        debugShowCheckedModeBanner: false,
        theme: buildMithaTheme(Brightness.light), // modo Claro do Figma
        darkTheme: buildMithaTheme(Brightness.dark), // modo Escuro do Figma
        themeMode: ThemeMode.system,
        home: const AppShell(),
      );
}

/// Componente Figma: NavBar — 4 abas (Painel, Histórico, Irrigações, Alertas).
class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _aba = 0;

  void _ir(int i) => setState(() => _aba = i);

  @override
  Widget build(BuildContext context) {
    final telas = <Widget>[
      PainelScreen(onAbrirHistorico: () => _ir(1), onAbrirIrrigacoes: () => _ir(2)),
      const _EmConstrucao('Histórico'), // Figma: 02_Histórico
      const _EmConstrucao('Irrigações'), // Figma: 03_Irrigações
      const _EmConstrucao('Alertas'), // Figma: 04_Alertas
    ];
    NavigationDestination dest(MithaIcons i, String l) => NavigationDestination(
          icon: MithaIcon(i, color: Theme.of(context).colorScheme.onSurfaceVariant),
          selectedIcon: MithaIcon(i, color: Theme.of(context).colorScheme.primary),
          label: l,
        );
    return Scaffold(
      body: IndexedStack(index: _aba, children: telas),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _aba,
        onDestinationSelected: _ir,
        destinations: [
          dest(MithaIcons.painel, 'Painel'),
          dest(MithaIcons.historico, 'Histórico'),
          dest(MithaIcons.irrigacao, 'Irrigações'),
          dest(MithaIcons.sino, 'Alertas'),
        ],
      ),
    );
  }
}

class _EmConstrucao extends StatelessWidget {
  const _EmConstrucao(this.titulo);
  final String titulo;

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(titulo)),
        body: const Center(child: Text('Implementar a partir do Figma')),
      );
}
