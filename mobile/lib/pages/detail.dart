import 'package:flutter/material.dart';

import '../api.dart';
import '../ui.dart';

class DetailPage extends StatelessWidget {
  const DetailPage({super.key, required this.code, this.heroPhoto = false});
  final String code;
  final bool heroPhoto;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: pageBg,
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
        toast(context, 'Added. $n citizens have confirmed this.');
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
    final top = MediaQuery.of(context).padding.top;
    final col = urgencyColor(r.urgency);
    return RefreshIndicator(
      onRefresh: widget.reload,
      color: navy,
      child: ListView(padding: EdgeInsets.zero, children: [
        Stack(children: [
          BoxedPhoto(url: r.photoUrl, detections: r.detections, aspect: 4 / 4.6),
          const Positioned.fill(child: IgnorePointer(child: DecoratedBox(decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, stops: [0, .2, .7, 1], colors: [Color(0x99000000), Color(0x00000000), Color(0x00000000), Color(0xCC14161A)]))))),
          Positioned(
            top: top + 8,
            left: 10,
            child: Material(color: const Color(0x99141619), shape: const CircleBorder(), child: IconButton(onPressed: () => Navigator.of(context).pop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white))),
          ),
          Positioned(top: top + 18, right: 16, child: Text(r.code, style: display(22, color: Colors.white))),
        ]),
        Container(
          color: navy,
          padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Expanded(child: Text(r.hazard, style: display(50, color: Colors.white, h: 1))),
              Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                Text(r.severity.toStringAsFixed(1), style: display(50, color: col, h: 1)),
                const Text('AI severity / 10', style: TextStyle(color: Color(0xFF9BA0A8), fontSize: 11)),
              ]),
            ]),
            const SizedBox(height: 6),
            Text('${r.ward ?? 'Location pending'} · reported ${ago(r.createdAt)}${r.isDemo ? ' · demo data' : ''}', style: const TextStyle(color: Color(0xFFB9BDC4))),
            if (r.place != null) Text(r.place!, style: const TextStyle(color: Color(0xFFB9BDC4))),
            const SizedBox(height: 14),
            Wrap(spacing: 8, runSpacing: 8, children: [
              UrgencyPill(r.urgency),
              Pill(statusLabel(r.publicStatus), color: Colors.white12),
              if (r.overdue) const Pill('Overdue', color: bad),
              if (r.assignee != null) Pill(r.assignee!, color: Colors.white12, icon: Icons.engineering),
            ]),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(18, 24, 18, 110),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _LocationFacts(r),
            const SizedBox(height: 24),
            if (r.afterPhotoUrl != null) ...[
              Text('After the repair', style: display(28)),
              const SizedBox(height: 10),
              ClipRRect(borderRadius: BorderRadius.circular(20), child: BoxedPhoto(url: r.afterPhotoUrl!)),
              if (r.isDemo) const Padding(padding: EdgeInsets.only(top: 8), child: Text('Demo data: this after photo is simulated, not a real repair.', style: TextStyle(color: muted, fontSize: 12.5))),
              const SizedBox(height: 24),
            ],
            if (r.recommendation != null && r.recommendation!.isNotEmpty) ...[
              Text('Recommended repair', style: display(28)),
              const SizedBox(height: 6),
              Text(r.recommendation!, style: const TextStyle(height: 1.5, fontSize: 15.5)),
              const SizedBox(height: 24),
            ],
            if (est != null && (est['total_inr'] ?? 0) > 0) ...[
              Text('Estimated cost', style: display(28)),
              const SizedBox(height: 4),
              Text(inr(est['total_inr'] as num), style: display(56, h: 1)),
              Text('Materials ${inr((est['materials_inr'] ?? 0) as num)} + labour ${inr((est['labour_inr'] ?? 0) as num)} (${est['crew_hours']} crew-hours)', style: const TextStyle(color: muted, fontSize: 13)),
              const SizedBox(height: 10),
              for (final l in lines)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 5),
                  child: Row(children: [Expanded(child: Text('${l['item']}')), Text(inr((l['cost_inr'] ?? 0) as num), style: const TextStyle(fontWeight: FontWeight.w700))]),
                ),
              const SizedBox(height: 6),
              const Text('Indicative, from the size and depth the AI measured.', style: TextStyle(color: muted, fontSize: 12)),
              const SizedBox(height: 24),
            ],
            Text('Progress', style: display(28)),
            const SizedBox(height: 12),
            IntrinsicHeight(
              child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const SizedBox(width: 6, child: Padding(padding: EdgeInsets.symmetric(vertical: 4), child: LaneLine(vertical: true, dash: 10, gap: 8, thickness: 3))),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(children: [
                    for (final e in r.timeline.reversed.take(12))
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 7),
                        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Expanded(child: Text(_event(e), style: const TextStyle(fontWeight: FontWeight.w600, height: 1.3))),
                          Text(ago(DateTime.tryParse('${e['at']}')?.toLocal() ?? DateTime.now()), style: const TextStyle(color: muted, fontSize: 12)),
                        ]),
                      ),
                    if (r.timeline.isEmpty) const Align(alignment: Alignment.centerLeft, child: Text('No updates yet.', style: TextStyle(color: muted))),
                  ]),
                ),
              ]),
            ),
            const SizedBox(height: 26),
            SizedBox(width: double.infinity, child: BigButton(voting ? 'Adding…' : (count > 1 ? 'I see this too ($count)' : 'I see this too'), icon: Icons.people_outline, onTap: voting ? null : _vote)),
          ]),
        ),
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

/// Where the damage is, and the dates that matter: what an official asks first.
class _LocationFacts extends StatefulWidget {
  const _LocationFacts(this.r);
  final Report r;
  @override
  State<_LocationFacts> createState() => _LocationFactsState();
}

class _LocationFactsState extends State<_LocationFacts> {
  // Kept here so a rebuild does not ask again.
  late final Future<Address?> _address = Api.instance.address(widget.r.code);

  @override
  Widget build(BuildContext context) {
    final r = widget.r;
    final lat = r.lat, lng = r.lng;
    Widget row(String k, String? v, {bool strong = false}) => v == null || v.isEmpty
        ? const SizedBox.shrink()
        : Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SizedBox(width: 108, child: Text(k, style: const TextStyle(color: muted, fontSize: 13.5))),
              Expanded(child: strong ? Text(v, style: display(28, h: 1)) : Text(v, style: const TextStyle(fontWeight: FontWeight.w600, height: 1.3))),
            ]),
          );
    String day(String key) {
      final t = DateTime.tryParse('${r.json[key]}')?.toLocal();
      if (t == null) return '';
      return '${t.day.toString().padLeft(2, '0')}/${t.month.toString().padLeft(2, '0')}/${t.year}';
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Location and details', style: display(28)),
      const SizedBox(height: 6),
      FutureBuilder<Address?>(
        future: _address,
        builder: (_, s) {
          final a = s.data;
          return Column(children: [
            if (s.connectionState != ConnectionState.done) const Padding(padding: EdgeInsets.symmetric(vertical: 6), child: Skeleton(height: 28, radius: 6)),
            row('PIN code', a?.pin, strong: true),
            row('State', a?.state),
            row('District', a?.district),
            row('City', a?.city),
            row('Area', a?.area),
            row('Road', a?.road),
          ]);
        },
      ),
      row('Ward', r.ward),
      if (lat != null && lng != null) row('Coordinates', '${lat.toStringAsFixed(5)}, ${lng.toStringAsFixed(5)}'),
      row('Report no.', r.code),
      row('Reported on', day('created_at')),
      row('Repair due', day('due_at')),
      row('Crew', r.assignee ?? 'Not assigned yet'),
      row('Citizens', '${r.reportedCount}'),
    ]);
  }
}
