import 'package:flutter/material.dart';

import '../api.dart';
import '../ui.dart';
import 'detail.dart';
import 'officer.dart';

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
    final top = MediaQuery.of(context).padding.top;
    return Column(children: [
      Container(
        color: navy,
        width: double.infinity,
        padding: EdgeInsets.fromLTRB(18, top + 14, 10, 16),
        child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('My reports', style: display(40, color: Colors.white)),
              const Text('Sent from this phone', style: TextStyle(color: Color(0xFF9BA0A8))),
            ]),
          ),
          TextButton.icon(
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const OfficerGate())),
            icon: const Icon(Icons.badge_outlined, color: Color(0xFFB9BDC4), size: 18),
            label: const Text('Officer', style: TextStyle(color: Color(0xFFB9BDC4), fontWeight: FontWeight.w700)),
          ),
        ]),
      ),
      Expanded(
        child: FutureBuilder<List<Report>>(
          future: future,
          builder: (_, s) {
            if (s.connectionState != ConnectionState.done) {
              return ListView(padding: const EdgeInsets.all(16), children: const [Skeleton(height: 120), SizedBox(height: 12), Skeleton(height: 120)]);
            }
            if (s.hasError) {
              return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [const Text('Could not load your reports.', style: TextStyle(color: muted)), const SizedBox(height: 12), BigButton('Try again', icon: Icons.refresh, onTap: reload)]));
            }
            final list = s.data ?? [];
            if (list.isEmpty) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    const SizedBox(width: 160, child: LaneLine(thickness: 4)),
                    const SizedBox(height: 22),
                    Text('Nothing reported yet', style: display(34), textAlign: TextAlign.center),
                    const SizedBox(height: 6),
                    const Text('Your reports appear here, with the AI result and every repair step.', textAlign: TextAlign.center, style: TextStyle(color: muted, height: 1.4)),
                    const SizedBox(height: 22),
                    BigButton('Report a road problem', icon: Icons.photo_camera_rounded, onTap: widget.onReport),
                  ]),
                ),
              );
            }
            return RefreshIndicator(
              onRefresh: () async => reload(),
              color: navy,
              child: ListView.separated(
                padding: const EdgeInsets.fromLTRB(14, 14, 14, 110),
                itemCount: list.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (_, i) {
                  final r = list[i];
                  return GestureDetector(
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailPage(code: r.code))),
                    child: Container(
                      height: 128,
                      decoration: BoxDecoration(color: paper, borderRadius: BorderRadius.circular(22), border: Border.all(color: hair)),
                      clipBehavior: Clip.antiAlias,
                      child: Row(children: [
                        Stack(children: [
                          SizedBox(width: 112, height: 128, child: Image.network(r.photoUrl, fit: BoxFit.cover, alignment: const Alignment(0, .24), errorBuilder: (_, __, ___) => Container(color: navy2))),
                          Positioned(left: 0, top: 0, bottom: 0, child: Container(width: 5, color: r.aiPending ? muted : urgencyColor(r.urgency))),
                        ]),
                        Expanded(
                          child: Padding(
                            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                              Text(r.aiPending ? 'Waiting for the AI' : r.hazard, style: display(27, h: 1.05)),
                              const SizedBox(height: 2),
                              Text('${r.code} · ${ago(r.createdAt)}', style: const TextStyle(color: muted, fontSize: 12.5)),
                              if (r.place != null) Text(r.place!, style: const TextStyle(color: muted, fontSize: 12.5)),
                              const SizedBox(height: 10),
                              Row(children: [
                                Text(statusLabel(r.publicStatus), style: TextStyle(fontWeight: FontWeight.w800, fontSize: 13, color: r.publicStatus == 'resolved' ? ok : navy)),
                                const Spacer(),
                                if (!r.aiPending) Text(r.severity.toStringAsFixed(1), style: display(26, color: urgencyColor(r.urgency), h: 1)),
                              ]),
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
      ),
    ]);
  }
}
