import 'package:flutter/material.dart';

import '../api.dart';
import '../ui.dart';
import 'detail.dart';

/// The reports sent from this phone.
class MinePage extends StatefulWidget {
  const MinePage({super.key, required this.onReport});
  final VoidCallback onReport;
  @override
  State<MinePage> createState() => MinePageState();
}

class MinePageState extends State<MinePage> {
  late Future<List<Report>> future = Api.instance.mine();

  void reload() => setState(() => future = Api.instance.mine());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My reports')),
      body: FutureBuilder<List<Report>>(
        future: future,
        builder: (_, s) {
          if (s.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (s.hasError) {
            return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [const Text('Could not load your reports.'), const SizedBox(height: 10), FilledButton(onPressed: reload, child: const Text('Try again'))]));
          }
          final list = s.data ?? [];
          if (list.isEmpty) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.add_road, size: 56, color: Colors.black26),
                  const SizedBox(height: 12),
                  const Text('You have not reported anything yet.', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 16),
                  BigButton('Report a road problem', icon: Icons.photo_camera, onTap: widget.onReport),
                ]),
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: () async => reload(),
            child: ListView.separated(
              padding: const EdgeInsets.all(14),
              itemCount: list.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (_, i) {
                final r = list[i];
                return Material(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(18),
                  clipBehavior: Clip.antiAlias,
                  child: InkWell(
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailPage(code: r.code))),
                    child: Row(children: [
                      SizedBox(width: 96, height: 120, child: Image.network(r.photoUrl, fit: BoxFit.cover, alignment: const Alignment(0, .24), errorBuilder: (_, __, ___) => Container(color: navy2))),
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Row(children: [Expanded(child: Text(r.aiPending ? 'Waiting for AI…' : r.hazard, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16))), if (!r.aiPending) UrgencyPill(r.urgency)]),
                            const SizedBox(height: 4),
                            Text('${r.code} · ${ago(r.createdAt)}', style: const TextStyle(color: Colors.black54, fontSize: 12.5)),
                            const SizedBox(height: 8),
                            Pill(statusLabel(r.publicStatus), color: const Color(0xFFEAF0F7), fg: navy),
                          ]),
                        ),
                      ),
                    ]),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
