import 'package:flutter/material.dart';

import '../api.dart';
import '../ui.dart';

class DetailPage extends StatelessWidget {
  const DetailPage({super.key, required this.code});
  final String code;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Report $code')),
      body: Loader<Report>(load: () => Api.instance.report(code), builder: (c, r, reload) => _Body(r: r, reload: reload)),
    );
  }
}

class _Body extends StatefulWidget {
  const _Body({required this.r, required this.reload});
  final Report r;
  final Future<void> Function() reload;
  @override
  State<_Body> createState() => _BodyState();
}

class _BodyState extends State<_Body> {
  bool voting = false;
  late int count = widget.r.reportedCount;

  Future<void> _vote() async {
    setState(() => voting = true);
    try {
      final n = await Api.instance.vote(widget.r.code);
      if (mounted) {
        setState(() => count = n);
        toast(context, 'Thanks, your confirmation was added.');
      }
    } catch (e) {
      if (mounted) toast(context, e is ApiError && e.offline ? 'No connection.' : '$e');
    } finally {
      if (mounted) setState(() => voting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.r;
    final est = r.estimate;
    final lines = ((est?['lines'] as List?) ?? []).whereType<Map>().toList();
    return RefreshIndicator(
      onRefresh: widget.reload,
      child: ListView(padding: const EdgeInsets.all(16), children: [
        ClipRRect(borderRadius: BorderRadius.circular(22), child: BoxedPhoto(url: r.photoUrl, detections: r.detections)),
        const SizedBox(height: 14),
        Row(children: [
          Expanded(child: Text(r.hazard, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w800, letterSpacing: -.8))),
          UrgencyPill(r.urgency),
        ]),
        const SizedBox(height: 4),
        Text('${r.ward ?? 'Location pending'} · reported ${ago(r.createdAt)}${r.isDemo ? ' · demo' : ''}', style: const TextStyle(color: Colors.black54)),
        const SizedBox(height: 12),
        Wrap(spacing: 8, runSpacing: 6, children: [
          Pill(statusLabel(r.publicStatus), color: navy),
          Pill('AI severity ${r.severity.toStringAsFixed(1)}', color: const Color(0xFFEAF0F7), fg: navy),
          if (r.overdue) const Pill('Past deadline', color: Color(0xFFA3161A)),
          if (r.assignee != null) Pill('Crew: ${r.assignee}', color: const Color(0xFFEAF0F7), fg: navy, icon: Icons.engineering),
        ]),
        if (r.afterPhotoUrl != null) ...[
          const SizedBox(height: 18),
          const Text('After the repair', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17)),
          const SizedBox(height: 8),
          ClipRRect(borderRadius: BorderRadius.circular(18), child: BoxedPhoto(url: r.afterPhotoUrl!, aspect: 4 / 5)),
        ],
        if (r.recommendation != null && r.recommendation!.isNotEmpty) ...[
          const SizedBox(height: 18),
          _Section('What the AI recommends', Text(r.recommendation!, style: const TextStyle(height: 1.45))),
        ],
        if (est != null && (est['total_inr'] ?? 0) > 0) ...[
          const SizedBox(height: 14),
          _Section(
              'Estimated repair cost',
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(inr(est['total_inr'] as num), style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: -1)),
                Text('Materials ${inr((est['materials_inr'] ?? 0) as num)} · labour ${inr((est['labour_inr'] ?? 0) as num)} · ${(est['crew_hours'] ?? 0)} crew-hours', style: const TextStyle(color: Colors.black54, fontSize: 12.5)),
                const SizedBox(height: 8),
                for (final l in lines) Padding(padding: const EdgeInsets.symmetric(vertical: 2), child: Row(children: [Expanded(child: Text('${l['item']}')), Text(inr((l['cost_inr'] ?? 0) as num))])),
                const SizedBox(height: 6),
                const Text('Indicative estimate from the measured size and depth.', style: TextStyle(color: Colors.black45, fontSize: 12)),
              ])),
        ],
        const SizedBox(height: 14),
        _Section(
            'Progress',
            Column(children: [
              for (final e in r.timeline.reversed.take(12))
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 5),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Padding(padding: EdgeInsets.only(top: 5), child: Icon(Icons.circle, size: 9, color: saffron)),
                    const SizedBox(width: 10),
                    Expanded(child: Text(_event(e), style: const TextStyle(height: 1.3))),
                    Text(ago(DateTime.tryParse('${e['at']}')?.toLocal() ?? DateTime.now()), style: const TextStyle(color: Colors.black45, fontSize: 12)),
                  ]),
                ),
              if (r.timeline.isEmpty) const Text('No updates yet.'),
            ])),
        const SizedBox(height: 18),
        SizedBox(
            width: double.infinity,
            child: BigButton(voting ? 'Adding…' : 'I see this too${count > 1 ? '  ($count)' : ''}', icon: Icons.people_outline, onTap: voting ? null : _vote)),
        const SizedBox(height: 24),
      ]),
    );
  }

  String _event(Map e) {
    final ev = '${e['event']}';
    final nv = e['new_value'];
    return switch (ev) {
      'reported' => 'Reported',
      'ai_assessed' => 'AI assessed the damage',
      'assigned' => 'Assigned${nv != null ? ' to $nv' : ''}',
      'status' => 'Status: ${nv ?? ''}',
      'repair_photo' => 'Repair photo added',
      'duplicate_added' => 'Another citizen confirmed it',
      _ => ev.replaceAll('_', ' '),
    };
  }
}

class _Section extends StatelessWidget {
  const _Section(this.title, this.child);
  final String title;
  final Widget child;
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15.5)),
          const SizedBox(height: 10),
          child,
        ]),
      );
}
