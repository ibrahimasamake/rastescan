import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../ui.dart';
import 'detail.dart';
import 'impact.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.onReport, required this.onTab});
  final VoidCallback onReport;
  final void Function(int) onTab;
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final api = Api.instance;
  late Future<Stats> stats = api.stats();
  late Future<List<Report>> worst = api.reports(sort: 'urgency', perPage: 8).then((p) => p.items.where((r) => r.photoUrl.isNotEmpty).toList());
  late Future<List<Activity>> activity = api.activity();
  late Future<List<Report>> resolved = api.recentlyResolved();

  Future<void> refresh() async {
    setState(() {
      stats = api.stats();
      worst = api.reports(sort: 'urgency', perPage: 8).then((p) => p.items.where((r) => r.photoUrl.isNotEmpty).toList());
      activity = api.activity();
      resolved = api.recentlyResolved();
    });
    await Future.wait([stats, worst]).catchError((_) => <Object>[]);
  }

  void open(Report r) => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailPage(code: r.code)));

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: refresh,
      child: ListView(padding: EdgeInsets.zero, children: [
        _Hero(worst: worst, stats: stats, onReport: widget.onReport, onMap: () => widget.onTab(3)),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 28, 16, 0),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _Head('Live activity', null, null),
            FutureBuilder<List<Activity>>(
              future: activity,
              builder: (_, s) {
                if (!s.hasData) return const SizedBox(height: 60, child: Center(child: CircularProgressIndicator()));
                return Card(
                  elevation: 0,
                  color: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
                  child: Column(children: [
                    for (final a in s.data!.take(6))
                      ListTile(
                        dense: true,
                        leading: Icon(_icon(a.event), size: 20, color: navy),
                        title: Text(_text(a), style: const TextStyle(fontWeight: FontWeight.w600)),
                        subtitle: Text('${a.code} · ${a.ward ?? ''} ${ago(a.at)}'),
                        onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailPage(code: a.code))),
                      ),
                  ]),
                );
              },
            ),
            const SizedBox(height: 28),
            _Head('Impact', 'See all', () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ImpactPage()))),
            _ImpactTeaser(onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ImpactPage()))),
            const SizedBox(height: 28),
            _Head('Recently fixed', null, null),
          ]),
        ),
        SizedBox(
          height: 300,
          child: FutureBuilder<List<Report>>(
            future: resolved,
            builder: (_, s) {
              if (!s.hasData) return const Center(child: CircularProgressIndicator());
              if (s.data!.isEmpty) return const Center(child: Text('Nothing fixed yet. Be the first to report.'));
              return ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: s.data!.length,
                separatorBuilder: (_, __) => const SizedBox(width: 12),
                itemBuilder: (_, i) => SizedBox(width: 180, child: ReportCard(s.data![i], onTap: () => open(s.data![i]))),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 28, 16, 36),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _Head('How it works', null, null),
            const _Step(1, 'Take a photo', 'Stand safely and photograph the damage. The app adds your location.'),
            const _Step(2, 'AI inspects it', 'It blurs faces and plates, finds the damage, measures it and scores how dangerous it is.'),
            const _Step(3, 'The ward fixes it', 'It joins a ranked repair list. You follow it until the after-photo proves the fix.'),
          ]),
        ),
      ]),
    );
  }

  IconData _icon(String e) => switch (e) {
        'reported' => Icons.add_a_photo_outlined,
        'ai_assessed' => Icons.auto_awesome,
        'assigned' => Icons.assignment_ind_outlined,
        'repair_photo' => Icons.build_circle_outlined,
        'duplicate_added' => Icons.people_outline,
        _ => Icons.sync,
      };

  String _text(Activity a) => switch (a.event) {
        'reported' => 'New report: ${a.hazard}',
        'ai_assessed' => 'AI rated ${a.hazard}',
        'assigned' => 'Assigned to a crew',
        'repair_photo' => 'Repair photo added',
        'duplicate_added' => 'Another citizen confirmed it',
        _ => 'Status updated',
      };
}

class _Head extends StatelessWidget {
  const _Head(this.title, this.action, this.onTap);
  final String title;
  final String? action;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(children: [
          Expanded(child: Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontSize: 22))),
          if (action != null) TextButton(onPressed: onTap, child: Text(action!)),
        ]),
      );
}

class _Step extends StatelessWidget {
  const _Step(this.n, this.title, this.text);
  final int n;
  final String title, text;
  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            width: 38,
            height: 38,
            alignment: Alignment.center,
            decoration: const BoxDecoration(shape: BoxShape.circle, gradient: LinearGradient(colors: [Color(0xFFFF9A4D), Color(0xFFFF6B5A)])),
            child: Text('$n', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 17)),
          ),
          const SizedBox(width: 14),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
            const SizedBox(height: 3),
            Text(text, style: const TextStyle(color: Colors.black54, height: 1.4)),
          ])),
        ]),
      );
}

class _ImpactTeaser extends StatelessWidget {
  const _ImpactTeaser({required this.onTap});
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => FutureBuilder<Impact>(
        future: Api.instance.impact(),
        builder: (_, s) {
          final i = s.data;
          Widget cell(String v, String l) => Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(v, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800, letterSpacing: -.8)),
                  Text(l, style: const TextStyle(color: Colors.black54, fontSize: 12)),
                ]),
              );
          return InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(18),
            child: Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
              child: i == null
                  ? const SizedBox(height: 50, child: Center(child: CircularProgressIndicator()))
                  : Row(children: [
                      cell(inr(i.repairedInr), 'repaired value'),
                      cell(inr(i.backlogInr), 'open backlog'),
                      cell(i.onTime == null ? '–' : '${i.onTime!.round()}%', 'on time'),
                    ]),
            ),
          );
        },
      );
}

/// Full-bleed cinematic banner: the worst live reports cross-fade with a slow push-in, the AI box is drawn on each.
class _Hero extends StatefulWidget {
  const _Hero({required this.worst, required this.stats, required this.onReport, required this.onMap});
  final Future<List<Report>> worst;
  final Future<Stats> stats;
  final VoidCallback onReport, onMap;
  @override
  State<_Hero> createState() => _HeroState();
}

class _HeroState extends State<_Hero> with SingleTickerProviderStateMixin {
  late final AnimationController push = AnimationController(vsync: this, duration: const Duration(seconds: 6))..forward();
  Timer? timer;
  int i = 0;
  List<Report> items = [];

  @override
  void initState() {
    super.initState();
    widget.worst.then((v) {
      if (!mounted) return;
      setState(() => items = v);
    }).catchError((_) {});
    timer = Timer.periodic(const Duration(seconds: 6), (_) {
      if (!mounted || items.isEmpty) return;
      setState(() => i = (i + 1) % items.length);
      push.forward(from: 0);
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    push.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.of(context).padding.top;
    final r = items.isEmpty ? null : items[i % items.length];
    return Container(
      color: navy,
      child: Stack(children: [
        // photo band
        SizedBox(
          height: 420 + top,
          width: double.infinity,
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 1200),
            child: r == null
                ? Container(key: const ValueKey('none'), color: navy2)
                : AnimatedBuilder(
                    key: ValueKey(r.code),
                    animation: push,
                    builder: (_, __) => Transform.scale(
                      scale: 1.02 + .12 * push.value,
                      child: BoxedPhoto(url: r.photoUrl, detections: r.detections.take(1).toList(), aspect: MediaQuery.of(context).size.width / (420 + top), showLabels: true),
                    ),
                  ),
          ),
        ),
        Positioned(
          left: 0,
          right: 0,
          top: 0,
          height: 420 + top,
          child: IgnorePointer(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, stops: const [0, .25, .6, 1], colors: [
                  navy.withValues(alpha: .6),
                  navy.withValues(alpha: 0),
                  navy.withValues(alpha: .55),
                  navy,
                ]),
              ),
            ),
          ),
        ),
        Padding(
          padding: EdgeInsets.fromLTRB(20, top + 14, 20, 24),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Icon(Icons.route, color: saffron),
              const SizedBox(width: 8),
              const Text('RasteScan', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 18, letterSpacing: -.3)),
              const Spacer(),
              if (r != null)
                Container(
                  constraints: const BoxConstraints(maxWidth: 190),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(color: navy.withValues(alpha: .55), borderRadius: BorderRadius.circular(14), border: Border.all(color: Colors.white24)),
                  child: Text('${r.hazard} · ${r.ward ?? r.code}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
                ),
            ]),
            const SizedBox(height: 230),
            Container(
              padding: const EdgeInsets.fromLTRB(10, 6, 14, 6),
              decoration: BoxDecoration(color: Colors.white12, borderRadius: BorderRadius.circular(99), border: Border.all(color: Colors.white24)),
              child: const Row(mainAxisSize: MainAxisSize.min, children: [
                _LiveDot(),
                SizedBox(width: 8),
                Text('The real problem on our roads', style: TextStyle(color: Colors.white, fontSize: 12.5, fontWeight: FontWeight.w600)),
              ]),
            ),
            const SizedBox(height: 14),
            const _Headline(),
            const SizedBox(height: 12),
            const Text('Send a photo. Our AI inspector checks how dangerous it is and the ward office sees it in a ranked list. Everyone can follow the repair until it is fixed.',
                style: TextStyle(color: Colors.white70, height: 1.5, fontSize: 15)),
            const SizedBox(height: 20),
            SizedBox(width: double.infinity, child: BigButton('Report a road problem', icon: Icons.photo_camera, onTap: widget.onReport)),
            const SizedBox(height: 10),
            SizedBox(width: double.infinity, child: BigButton('Watch the live map', icon: Icons.map_outlined, light: true, onTap: widget.onMap)),
            const SizedBox(height: 6),
            const Padding(padding: EdgeInsets.only(top: 6), child: Text('Takes under 30 seconds. No account needed.', style: TextStyle(color: Colors.white54, fontSize: 12.5))),
            const SizedBox(height: 22),
            FutureBuilder<Stats>(
              future: widget.stats,
              builder: (_, s) {
                final d = s.data;
                Widget cell(int? v, String l, {bool warn = false}) => Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        TweenAnimationBuilder<double>(
                          tween: Tween(begin: 0, end: (v ?? 0).toDouble()),
                          duration: const Duration(milliseconds: 1600),
                          curve: Curves.easeOutCubic,
                          builder: (_, x, __) => Text(d == null ? '–' : '${x.round()}',
                              style: TextStyle(color: warn ? const Color(0xFFFF9D8C) : Colors.white, fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: -1)),
                        ),
                        Text(l, style: const TextStyle(color: Colors.white60, fontSize: 11.5)),
                      ]),
                    );
                return Container(
                  padding: const EdgeInsets.only(top: 16),
                  decoration: const BoxDecoration(border: Border(top: BorderSide(color: Colors.white24))),
                  child: Row(children: [
                    cell(d?.today, 'Reported today'),
                    cell(d?.open, 'Open now'),
                    cell(d?.overdue, 'Past deadline', warn: true),
                    cell(d?.resolvedMonth, 'Fixed (month)'),
                  ]),
                );
              },
            ),
          ]),
        ),
      ]),
    );
  }
}

class _Headline extends StatelessWidget {
  const _Headline();
  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: 1),
        duration: const Duration(milliseconds: 900),
        curve: Curves.easeOutCubic,
        builder: (_, v, child) => Opacity(opacity: v, child: Transform.translate(offset: Offset(0, 24 * (1 - v)), child: child)),
        child: RichText(
          text: TextSpan(
            style: const TextStyle(color: Colors.white, fontSize: 38, fontWeight: FontWeight.w800, letterSpacing: -1.8, height: 1.04),
            children: [
              const TextSpan(text: 'Is there a pothole, open manhole or broken road '),
              const TextSpan(text: 'near you?', style: TextStyle(color: Color(0xFFFFB45E))),
            ],
          ),
        ),
      );
}

class _LiveDot extends StatefulWidget {
  const _LiveDot();
  @override
  State<_LiveDot> createState() => _LiveDotState();
}

class _LiveDotState extends State<_LiveDot> with SingleTickerProviderStateMixin {
  late final c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))..repeat();
  @override
  void dispose() {
    c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: c,
        builder: (_, __) => Container(
          width: 9,
          height: 9,
          decoration: BoxDecoration(shape: BoxShape.circle, color: const Color(0xFFFF4D3D), boxShadow: [
            BoxShadow(color: const Color(0xFFFF4D3D).withValues(alpha: 1 - c.value), blurRadius: 0, spreadRadius: 9 * c.value),
          ]),
        ),
      );
}
