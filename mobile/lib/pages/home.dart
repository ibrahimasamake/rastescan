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
  late Future<List<Report>> worst = _worst();
  late Future<List<Activity>> activity = api.activity();
  late Future<List<Report>> resolved = api.recentlyResolved();

  // The list rows do not carry the AI's boxes, so fetch each report's detail: the hero and cards then show the frame on the damage.
  Future<List<Report>> _worst() async {
    final page = await api.reports(sort: 'urgency', perPage: 8);
    final full = await Future.wait(page.items.where((r) => r.photoUrl.isNotEmpty).map((r) => api.report(r.code).catchError((_) => r)));
    return full;
  }

  Future<void> refresh() async {
    setState(() {
      stats = api.stats();
      worst = _worst();
      activity = api.activity();
      resolved = api.recentlyResolved();
    });
    await worst.catchError((_) => <Report>[]);
  }

  void open(String code) => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailPage(code: code)));

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: refresh,
      color: navy,
      child: ListView(padding: const EdgeInsets.only(bottom: 110), children: [
        _Hero(worst: worst, stats: stats, onReport: widget.onReport, onMap: () => widget.onTab(3), onOpen: open),
        const SizedBox(height: 30),
        _Section('Worst right now', action: 'All reports', onTap: () => widget.onTab(1)),
        SizedBox(
          height: 300,
          child: FutureBuilder<List<Report>>(
            future: worst,
            builder: (_, s) {
              if (!s.hasData) return ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 18), children: const [Skeleton(height: 300, width: 200, radius: 22), SizedBox(width: 12), Skeleton(height: 300, width: 200, radius: 22)]);
              return ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 18),
                itemCount: s.data!.length,
                separatorBuilder: (_, __) => const SizedBox(width: 12),
                itemBuilder: (_, i) => SizedBox(width: 205, child: ReportCard(s.data![i], onTap: () => open(s.data![i].code))),
              );
            },
          ),
        ),
        const SizedBox(height: 34),
        _Section('Public money, public roads', action: 'Impact', onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ImpactPage()))),
        const _ImpactStrip(),
        const SizedBox(height: 34),
        const _Section('Happening now'),
        _Feed(activity: activity, onOpen: open),
        const SizedBox(height: 34),
        const _Section('Fixed and proven'),
        SizedBox(
          height: 270,
          child: FutureBuilder<List<Report>>(
            future: resolved,
            builder: (_, s) {
              if (!s.hasData) return const SizedBox.shrink();
              if (s.data!.isEmpty) return const Padding(padding: EdgeInsets.symmetric(horizontal: 18), child: Text('Nothing fixed yet. The first repair will show its before and after photos here.', style: TextStyle(color: muted, height: 1.4)));
              return ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 18),
                itemCount: s.data!.length,
                separatorBuilder: (_, __) => const SizedBox(width: 12),
                itemBuilder: (_, i) => SizedBox(width: 190, child: ReportCard(s.data![i], onTap: () => open(s.data![i].code))),
              );
            },
          ),
        ),
        const SizedBox(height: 34),
        const _Section('How a report moves'),
        const _Route(),
      ]),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section(this.title, {this.action, this.onTap});
  final String title;
  final String? action;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(18, 0, 10, 12),
        child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Expanded(child: Text(title, style: display(30, h: 1.05))),
          if (action != null)
            TextButton(onPressed: onTap, style: TextButton.styleFrom(foregroundColor: navy, textStyle: const TextStyle(fontWeight: FontWeight.w800, decoration: TextDecoration.underline, decorationColor: saffron, decorationThickness: 3)), child: Text(action!)),
        ]),
      );
}

class _ImpactStrip extends StatelessWidget {
  const _ImpactStrip();
  @override
  Widget build(BuildContext context) => FutureBuilder<Impact>(
        future: Api.instance.impact(),
        builder: (_, s) {
          final i = s.data;
          Widget cell(String v, String l, Color c) => Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(v, style: display(34, color: c, h: 1)),
                  const SizedBox(height: 3),
                  Text(l, style: const TextStyle(color: muted, fontSize: 12, height: 1.25)),
                ]),
              );
          return Container(
            margin: const EdgeInsets.symmetric(horizontal: 18),
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
            decoration: BoxDecoration(color: paper, borderRadius: BorderRadius.circular(22), border: Border.all(color: hair)),
            child: i == null
                ? const Skeleton(height: 60, radius: 10)
                : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    cell(inr(i.repairedInr), 'repairs done', ok),
                    const SizedBox(width: 10),
                    cell(inr(i.backlogInr), 'still waiting', bad),
                    const SizedBox(width: 10),
                    cell(i.onTime == null ? '–' : '${i.onTime!.round()}%', 'fixed on time', navy),
                  ]),
          );
        },
      );
}

class _Feed extends StatelessWidget {
  const _Feed({required this.activity, required this.onOpen});
  final Future<List<Activity>> activity;
  final void Function(String) onOpen;

  String _text(Activity a) => switch (a.event) {
        'reported' => 'New ${a.hazard.toLowerCase()} reported',
        'ai_assessed' => 'AI rated a ${a.hazard.toLowerCase()}',
        'assigned' => 'Crew assigned',
        'repair_photo' => 'Repair photo added',
        'duplicate_added' => 'Another citizen confirmed it',
        _ => 'Status updated',
      };

  @override
  Widget build(BuildContext context) => FutureBuilder<List<Activity>>(
        future: activity,
        builder: (_, s) {
          if (!s.hasData) return const Padding(padding: EdgeInsets.symmetric(horizontal: 18), child: Skeleton(height: 120));
          final list = s.data!.take(5).toList();
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18),
            child: IntrinsicHeight(
              child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const SizedBox(width: 6, child: Padding(padding: EdgeInsets.symmetric(vertical: 6), child: LaneLine(vertical: true, dash: 10, gap: 8, thickness: 3))),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(children: [
                    for (final a in list)
                      InkWell(
                        onTap: () => onOpen(a.code),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 9),
                          child: Row(children: [
                            Expanded(child: Text(_text(a), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15))),
                            Text(ago(a.at), style: const TextStyle(color: muted, fontSize: 12)),
                          ]),
                        ),
                      ),
                  ]),
                ),
              ]),
            ),
          );
        },
      );
}

class _Route extends StatelessWidget {
  const _Route();
  @override
  Widget build(BuildContext context) {
    Widget row(IconData i, String t, String d) => Padding(
          padding: const EdgeInsets.only(bottom: 22),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(width: 44, height: 44, decoration: BoxDecoration(color: navy, borderRadius: BorderRadius.circular(14)), child: Icon(i, color: saffron, size: 22)),
            const SizedBox(width: 14),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(t, style: display(23, h: 1.1)),
              const SizedBox(height: 2),
              Text(d, style: const TextStyle(color: muted, height: 1.4)),
            ])),
          ]),
        );
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18),
      child: Column(children: [
        row(Icons.photo_camera_rounded, 'Photograph it', 'Stand safely. The app adds your location. No account needed.'),
        row(Icons.center_focus_strong_rounded, 'The AI inspects it', 'Faces and plates are blurred, the damage is measured and scored.'),
        row(Icons.engineering_rounded, 'A crew fixes it', 'It joins a ranked repair list. An after photo proves the fix.'),
      ]),
    );
  }
}

/// Full-bleed opening: the worst live reports cross-fade under a slow push-in, with the AI's frame on each.
class _Hero extends StatefulWidget {
  const _Hero({required this.worst, required this.stats, required this.onReport, required this.onMap, required this.onOpen});
  final Future<List<Report>> worst;
  final Future<Stats> stats;
  final VoidCallback onReport, onMap;
  final void Function(String) onOpen;
  @override
  State<_Hero> createState() => _HeroState();
}

class _HeroState extends State<_Hero> with SingleTickerProviderStateMixin {
  static const sceneSeconds = 6;
  late final AnimationController clock = AnimationController(vsync: this, duration: const Duration(seconds: sceneSeconds))..forward();
  Timer? timer;
  int i = 0;
  List<Report> items = [];

  @override
  void initState() {
    super.initState();
    widget.worst.then((v) {
      if (mounted) setState(() => items = v);
    }).catchError((_) {});
    timer = Timer.periodic(const Duration(seconds: sceneSeconds), (_) {
      if (!mounted || items.isEmpty) return;
      setState(() => i = (i + 1) % items.length);
      clock.forward(from: 0);
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    clock.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.of(context).padding.top;
    final r = items.isEmpty ? null : items[i % items.length];
    final photoH = 330.0 + top;
    return Container(
      color: navy,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(
          height: photoH,
          child: Stack(fit: StackFit.expand, children: [
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 1100),
              child: r == null
                  ? Container(key: const ValueKey('none'), color: navy2)
                  : AnimatedBuilder(
                      key: ValueKey(r.code),
                      animation: clock,
                      builder: (_, __) => Transform.scale(
                        scale: 1.02 + .1 * clock.value,
                        child: BoxedPhoto(url: r.photoUrl, detections: r.detections.take(1).toList(), aspect: MediaQuery.of(context).size.width / photoH),
                      ),
                    ),
            ),
            const IgnorePointer(
              child: DecoratedBox(decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, stops: [0, .22, .6, 1], colors: [Color(0x99000000), Color(0x00000000), Color(0x55141619), navy]))),
            ),
            Positioned(
              top: top + 12,
              left: 18,
              right: 18,
              child: Row(children: [
                Container(width: 30, height: 30, decoration: BoxDecoration(color: saffron, borderRadius: BorderRadius.circular(9)), child: const Icon(Icons.center_focus_strong_rounded, size: 19, color: navy)),
                const SizedBox(width: 9),
                Text('RasteScan', style: display(26, color: Colors.white)),
                const Spacer(),
                if (r != null)
                  GestureDetector(
                    onTap: () => widget.onOpen(r.code),
                    child: Container(
                      constraints: const BoxConstraints(maxWidth: 180),
                      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
                      decoration: BoxDecoration(color: const Color(0x99141619), borderRadius: BorderRadius.circular(10), border: Border.all(color: Colors.white24)),
                      child: Text('${r.hazard} · ${r.ward ?? r.code}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white, fontSize: 11.5, fontWeight: FontWeight.w700)),
                    ),
                  ),
              ]),
            ),
          ]),
        ),
        // the dashed lane line is the scene timer
        AnimatedBuilder(animation: clock, builder: (_, __) => Padding(padding: const EdgeInsets.symmetric(horizontal: 18), child: SizedBox(height: 4, child: LaneLine(progress: clock.value, thickness: 4)))),
        const SizedBox(height: 18),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 18),
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: 1),
            duration: const Duration(milliseconds: 800),
            curve: Curves.easeOutCubic,
            builder: (_, v, child) => Opacity(opacity: v, child: Transform.translate(offset: Offset(0, 22 * (1 - v)), child: child)),
            child: Text('Is there a pothole, open manhole or broken road near you?', style: display(46, color: Colors.white, h: .98, ls: -.6)),
          ),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(18, 14, 40, 0),
          child: Text('Send one photo. An AI inspector scores the danger, the ward office gets a ranked repair list, and you can watch it get fixed.', style: TextStyle(color: Color(0xFFB9BDC4), height: 1.5, fontSize: 15.5)),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(18, 20, 18, 0),
          child: Row(children: [
            Expanded(flex: 6, child: BigButton('Report a problem', icon: Icons.photo_camera_rounded, onTap: widget.onReport)),
            const SizedBox(width: 10),
            Expanded(flex: 3, child: BigButton('Map', icon: Icons.map_outlined, light: true, onTap: widget.onMap)),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(18, 26, 18, 30),
          child: FutureBuilder<Stats>(
            future: widget.stats,
            builder: (_, s) {
              final d = s.data;
              Widget cell(int? v, String l, {bool warn = false}) => Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      TweenAnimationBuilder<double>(
                        tween: Tween(begin: 0, end: (v ?? 0).toDouble()),
                        duration: const Duration(milliseconds: 1500),
                        curve: Curves.easeOutCubic,
                        builder: (_, x, __) => Text(d == null ? '–' : '${x.round()}', style: display(38, color: warn ? const Color(0xFFFF8F80) : Colors.white, h: 1)),
                      ),
                      const SizedBox(height: 2),
                      Text(l, style: const TextStyle(color: Color(0xFF9BA0A8), fontSize: 11.5)),
                    ]),
                  );
              return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                cell(d?.today, 'today'),
                cell(d?.open, 'open'),
                cell(d?.overdue, 'overdue', warn: true),
                cell(d?.resolvedMonth, 'fixed in a month'),
              ]);
            },
          ),
        ),
      ]),
    );
  }
}
