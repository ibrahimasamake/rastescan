import 'package:flutter/material.dart';

import '../api.dart';
import '../ui.dart';

class ImpactPage extends StatelessWidget {
  const ImpactPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Impact')),
      body: Loader<Impact>(
        load: () => Api.instance.impact(days: 14),
        builder: (_, i, reload) {
          Widget tile(String v, String l, {Color? c}) => Expanded(
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(v, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, letterSpacing: -.8, color: c)),
                    const SizedBox(height: 2),
                    Text(l, style: const TextStyle(color: Colors.black54, fontSize: 12.5)),
                  ]),
                ),
              );
          final maxHaz = i.byHazard.isEmpty ? 1 : i.byHazard.map((e) => (e[1] as num).toInt()).reduce((a, b) => a > b ? a : b);
          final maxTrend = i.trend.isEmpty ? 1 : i.trend.map((e) => ((e['reported'] ?? 0) as num).toInt()).fold<int>(1, (a, b) => a > b ? a : b);
          return RefreshIndicator(
            onRefresh: reload,
            child: ListView(padding: const EdgeInsets.all(16), children: [
              Row(children: [tile(inr(i.repairedInr), 'value of repairs done', c: const Color(0xFF17663A)), const SizedBox(width: 12), tile(inr(i.backlogInr), 'open repair backlog', c: const Color(0xFFA3161A))]),
              const SizedBox(height: 12),
              Row(children: [tile('${i.fixed}/${i.tickets}', 'tickets fixed'), const SizedBox(width: 12), tile(i.onTime == null ? '–' : '${i.onTime!.round()}%', 'fixed on time')]),
              const SizedBox(height: 18),
              const Text('Last 14 days', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
              const SizedBox(height: 10),
              Container(
                height: 140,
                padding: const EdgeInsets.fromLTRB(12, 16, 12, 10),
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
                child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  for (final t in i.trend)
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 2),
                        child: TweenAnimationBuilder<double>(
                          tween: Tween(begin: 0, end: (((t['reported'] ?? 0) as num) / maxTrend).toDouble()),
                          duration: const Duration(milliseconds: 900),
                          curve: Curves.easeOutCubic,
                          builder: (_, v, __) => FractionallySizedBox(heightFactor: v.clamp(.03, 1), child: Container(decoration: BoxDecoration(color: navy, borderRadius: BorderRadius.circular(5)))),
                        ),
                      ),
                    ),
                ]),
              ),
              const SizedBox(height: 18),
              const Text('What is being reported', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
                child: Column(children: [
                  for (final h in i.byHazard)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(children: [
                        SizedBox(width: 110, child: Text('${h[0]}', style: const TextStyle(fontWeight: FontWeight.w600))),
                        Expanded(
                          child: ClipRRect(borderRadius: BorderRadius.circular(99), child: LinearProgressIndicator(value: (h[1] as num) / maxHaz, minHeight: 10, backgroundColor: Colors.black12, color: saffron)),
                        ),
                        SizedBox(width: 40, child: Text('${h[1]}', textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w700))),
                      ]),
                    ),
                ]),
              ),
              const SizedBox(height: 18),
              const Text('Hotspots', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
              const SizedBox(height: 10),
              for (final h in i.hotspots.take(6))
                Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
                  child: Row(children: [
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('${h['name']}', style: const TextStyle(fontWeight: FontWeight.w800)),
                      Text('${h['open']} open · ${h['critical']} critical', style: const TextStyle(color: Colors.black54, fontSize: 12.5)),
                    ])),
                    Text(inr((h['cost_inr'] ?? 0) as num), style: const TextStyle(fontWeight: FontWeight.w800)),
                  ]),
                ),
              const SizedBox(height: 20),
            ]),
          );
        },
      ),
    );
  }
}
