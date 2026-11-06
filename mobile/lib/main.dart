import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'pages/home.dart';
import 'pages/map.dart';
import 'pages/mine.dart';
import 'pages/reports.dart';
import 'pages/report_flow.dart';
import 'ui.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(statusBarColor: Colors.transparent, statusBarIconBrightness: Brightness.light));
  runApp(const RasteScanApp());
}

class RasteScanApp extends StatelessWidget {
  const RasteScanApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'RasteScan',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        home: const Shell(),
      );
}

class Shell extends StatefulWidget {
  const Shell({super.key});
  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int tab = 0;
  final _mineKey = GlobalKey<MinePageState>();

  void go(int i) => setState(() => tab = i);

  Future<void> openReport() async {
    await Navigator.of(context).push(PageRouteBuilder(
      pageBuilder: (_, __, ___) => const ReportFlow(),
      transitionsBuilder: (_, a, __, child) => FadeTransition(opacity: a, child: child),
      transitionDuration: const Duration(milliseconds: 350),
    ));
    if (!mounted) return;
    setState(() => tab = 4);
    _mineKey.currentState?.reload();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      HomePage(onReport: openReport, onTab: go),
      const ReportsPage(),
      const SizedBox.shrink(),
      const MapPage(),
      MinePage(key: _mineKey, onReport: openReport),
    ];
    return Scaffold(
      extendBody: true,
      body: IndexedStack(index: tab == 2 ? 0 : tab, children: pages),
      bottomNavigationBar: FloatNav(index: tab, onTap: go, onReport: openReport),
    );
  }
}
