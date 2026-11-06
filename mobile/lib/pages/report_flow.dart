import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';

import '../api.dart';
import '../ui.dart';
import 'detail.dart';

enum _Stage { capture, analysing, result }

/// Take a photo -> animated "AI is inspecting" scene -> result with the damage boxed.
class ReportFlow extends StatefulWidget {
  const ReportFlow({super.key});
  @override
  State<ReportFlow> createState() => _ReportFlowState();
}

class _ReportFlowState extends State<ReportFlow> {
  _Stage stage = _Stage.capture;
  Uint8List? photo;
  Position? pos;
  String locNote = 'Finding your location…';
  final note = TextEditingController();
  Report? report;
  Object? error;
  Future<Report>? job;

  @override
  void initState() {
    super.initState();
    _locate();
  }

  @override
  void dispose() {
    note.dispose();
    super.dispose();
  }

  Future<void> _locate() async {
    try {
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) perm = await Geolocator.requestPermission();
      if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) {
        if (mounted) setState(() => locNote = 'Location is off. Turn it on so the ward can find the damage.');
        return;
      }
      final p = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 15)));
      if (mounted) setState(() {
        pos = p;
        locNote = 'Location found (±${p.accuracy.round()} m)';
      });
    } catch (_) {
      if (mounted) setState(() => locNote = 'Could not get your location. You can still send the report.');
    }
  }

  Future<void> _pick(ImageSource src) async {
    final x = await ImagePicker().pickImage(source: src, maxWidth: 1800, imageQuality: 85);
    if (x == null) return;
    final bytes = await x.readAsBytes();
    if (!mounted) return;
    setState(() {
      photo = bytes;
      error = null;
    });
  }

  void _send() {
    if (photo == null) return;
    setState(() {
      stage = _Stage.analysing;
      error = null;
      job = Api.instance.submit(photo!, lat: pos?.latitude, lng: pos?.longitude, note: note.text.trim());
    });
    job!.then((r) {
      report = r;
    }).catchError((e) {
      if (!mounted) return;
      setState(() {
        error = e;
        stage = _Stage.capture;
      });
      toast(context, e is ApiError && e.offline ? 'No connection. Your photo was not sent.' : '$e');
    });
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 500),
      child: switch (stage) {
        _Stage.capture => _capture(),
        _Stage.analysing => _AnalysisScene(
            key: const ValueKey('scan'),
            photo: photo!,
            done: job!,
            onFinished: () {
              if (mounted && report != null) setState(() => stage = _Stage.result);
            }),
        _Stage.result => _ResultView(key: const ValueKey('res'), report: report!, onAgain: () {
            setState(() {
              photo = null;
              note.clear();
              stage = _Stage.capture;
            });
          }),
      },
    );
  }

  Widget _capture() {
    return Scaffold(
      key: const ValueKey('cap'),
      appBar: AppBar(title: const Text('Report a road problem')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        AspectRatio(
          aspectRatio: 4 / 5,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(22),
            child: photo != null
                ? Stack(fit: StackFit.expand, children: [
                    Image.memory(photo!, fit: BoxFit.cover),
                    Positioned(right: 10, top: 10, child: IconButton.filled(style: IconButton.styleFrom(backgroundColor: muted), onPressed: () => setState(() => photo = null), icon: const Icon(Icons.close))),
                  ])
                : InkWell(
                    onTap: () => _pick(ImageSource.camera),
                    child: Container(
                      decoration: BoxDecoration(color: Colors.white, border: Border.all(color: Colors.black26, width: 2), borderRadius: BorderRadius.circular(22)),
                      child: const Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                        Icon(Icons.photo_camera, size: 56, color: navy),
                        SizedBox(height: 10),
                        Text('Tap to take a photo', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                        SizedBox(height: 4),
                        Text('Stand safely off the road.\nShow the whole damage.', textAlign: TextAlign.center, style: TextStyle(color: muted)),
                      ]),
                    ),
                  ),
          ),
        ),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: OutlinedButton.icon(onPressed: () => _pick(ImageSource.camera), icon: const Icon(Icons.photo_camera_outlined), label: const Text('Camera'))),
          const SizedBox(width: 10),
          Expanded(child: OutlinedButton.icon(onPressed: () => _pick(ImageSource.gallery), icon: const Icon(Icons.photo_library_outlined), label: const Text('Gallery'))),
        ]),
        const SizedBox(height: 14),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: paper, borderRadius: BorderRadius.circular(14)),
          child: Row(children: [
            Icon(pos != null ? Icons.my_location : Icons.location_searching, color: pos != null ? const Color(0xFF17663A) : muted),
            const SizedBox(width: 10),
            Expanded(child: Text(locNote)),
            if (pos == null) TextButton(onPressed: _locate, child: const Text('Retry')),
          ]),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: note,
          maxLength: 300,
          maxLines: 2,
          decoration: InputDecoration(
            labelText: 'Note (optional)',
            hintText: 'For example: near the bus stop',
            filled: true,
            fillColor: paper,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
          ),
        ),
        const SizedBox(height: 4),
        const Text('Faces and number plates are blurred before the photo is stored. Your exact device is never shown publicly.', style: TextStyle(color: muted, fontSize: 12.5)),
        const SizedBox(height: 16),
        SizedBox(width: double.infinity, child: BigButton('Send report', icon: Icons.send, onTap: photo == null ? null : _send)),
        const SizedBox(height: 24),
      ]),
    );
  }
}

// ---------------------------------------------------------------- analysis scene

class _AnalysisScene extends StatefulWidget {
  const _AnalysisScene({super.key, required this.photo, required this.done, required this.onFinished});
  final Uint8List photo;
  final Future<Report> done;
  final VoidCallback onFinished;
  @override
  State<_AnalysisScene> createState() => _AnalysisSceneState();
}

class _AnalysisSceneState extends State<_AnalysisScene> with TickerProviderStateMixin {
  static const steps = [
    'Blurring faces and number plates',
    'Reading the road surface',
    'Finding the damage',
    'Measuring size and depth',
    'Scoring how urgent it is',
  ];
  static const stepAt = [0.5, 2.0, 3.8, 5.6, 7.4]; // seconds
  static const minShow = 3.4;

  late final AnimationController scan = AnimationController(vsync: this, duration: const Duration(milliseconds: 1900))..repeat(reverse: true);
  late final AnimationController creep = AnimationController(vsync: this, duration: const Duration(seconds: 14))..forward();
  late final AnimationController finish = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500));
  final started = DateTime.now();
  Timer? tick;
  int step = 0;
  bool finishing = false;

  @override
  void initState() {
    super.initState();
    tick = Timer.periodic(const Duration(milliseconds: 150), (_) {
      if (!mounted || finishing) return;
      final t = DateTime.now().difference(started).inMilliseconds / 1000;
      final n = stepAt.where((s) => t >= s).length;
      if (n != step) setState(() => step = n);
    });
    widget.done.then((_) => _ready(), onError: (_) {});
    finish.addStatusListener((s) {
      if (s == AnimationStatus.completed) widget.onFinished();
    });
  }

  Future<void> _ready() async {
    final waited = DateTime.now().difference(started).inMilliseconds / 1000;
    if (waited < minShow) await Future.delayed(Duration(milliseconds: ((minShow - waited) * 1000).round()));
    if (!mounted) return;
    setState(() {
      finishing = true;
      step = steps.length + 1;
    });
    creep.stop();
    finish.forward();
  }

  @override
  void dispose() {
    tick?.cancel();
    scan.dispose();
    creep.dispose();
    finish.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: navy,
      body: Stack(children: [
        Positioned.fill(
          child: DecoratedBox(
            decoration: const BoxDecoration(
              gradient: RadialGradient(center: Alignment(-.4, -.7), radius: 1.3, colors: [Color(0xFF17407A), navy2, Color(0xFF050F1F)], stops: [0, .5, 1]),
            ),
          ),
        ),
        SafeArea(
          child: AnimatedBuilder(
            animation: Listenable.merge([scan, creep, finish]),
            builder: (_, __) {
              final f = Curves.easeInOut.transform(finish.value);
              final pct = finishing ? (creep.value * 90 + (100 - creep.value * 90) * math.min(1, finish.value / .45)) : creep.value * 90;
              return Opacity(
                opacity: 1 - Curves.easeIn.transform(((finish.value - .7) / .3).clamp(0, 1)),
                child: Transform.scale(
                  scale: 1 + .04 * f,
                  child: Column(children: [
                    const SizedBox(height: 18),
                    Expanded(
                      flex: 5,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 28),
                        child: Center(
                          child: AspectRatio(
                            aspectRatio: 4 / 5,
                            child: Stack(fit: StackFit.expand, children: [
                              ClipRRect(
                                borderRadius: BorderRadius.circular(16),
                                child: Stack(fit: StackFit.expand, children: [
                                  Transform.scale(scale: 1 + .07 * creep.value, child: Image.memory(widget.photo, fit: BoxFit.cover)),
                                  CustomPaint(painter: _GridPainter(creep.value)),
                                  if (!finishing) _Laser(t: scan.value),
                                  _Shine(t: (DateTime.now().millisecondsSinceEpoch % 2500) / 2500),
                                  Opacity(opacity: finishing ? (1 - ((finish.value - .5) / .15).clamp(0, 1)) * (((finish.value - .45) / .1).clamp(0, 1)) * .95 : 0, child: Container(color: Colors.white)),
                                ]),
                              ),
                              const _Corners(),
                            ]),
                          ),
                        ),
                      ),
                    ),
                    Expanded(
                      flex: 5,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(28, 6, 28, 16),
                        child: Column(children: [
                          Row(children: [
                            SizedBox(width: 84, height: 84, child: CustomPaint(painter: _RingPainter(pct / 100), child: Center(child: Text('${pct.round()}%', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 18))))),
                            const SizedBox(width: 16),
                            Expanded(child: Text(finishing ? 'Inspection complete' : 'The AI is inspecting your photo', style: const TextStyle(color: Colors.white, fontSize: 21, fontWeight: FontWeight.w800, letterSpacing: -.5, height: 1.15))),
                          ]),
                          const SizedBox(height: 14),
                          for (var i = 0; i < steps.length; i++) _StepRow(steps[i], i + 1 < step || (finishing) ? 2 : (i + 1 == step ? 1 : 0)),
                          const Spacer(),
                          const Text('This usually takes a few seconds. Please keep the app open.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white54, fontSize: 12.5)),
                        ]),
                      ),
                    ),
                  ]),
                ),
              );
            },
          ),
        ),
      ]),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow(this.text, this.state); // 0 waiting, 1 running, 2 done
  final String text;
  final int state;
  @override
  Widget build(BuildContext context) => AnimatedOpacity(
        duration: const Duration(milliseconds: 400),
        opacity: state == 0 ? .35 : 1,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              width: 22,
              height: 22,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: state == 2 ? const Color(0xFF2EBD6B) : Colors.transparent,
                border: Border.all(color: state == 2 ? const Color(0xFF2EBD6B) : (state == 1 ? saffron : Colors.white30), width: 2),
              ),
              child: state == 2
                  ? const Icon(Icons.check, size: 14, color: Colors.white)
                  : state == 1
                      ? const Padding(padding: EdgeInsets.all(4), child: CircularProgressIndicator(strokeWidth: 2, color: saffron))
                      : null,
            ),
            const SizedBox(width: 12),
            Expanded(child: Text(text, style: TextStyle(color: Colors.white, fontSize: 14.5, fontWeight: state == 1 ? FontWeight.w700 : FontWeight.w500))),
          ]),
        ),
      );
}

class _Laser extends StatelessWidget {
  const _Laser({required this.t});
  final double t;
  @override
  Widget build(BuildContext context) => Align(
        alignment: Alignment(0, -1 + 2 * Curves.easeInOut.transform(t)),
        child: Container(
          height: 3,
          decoration: const BoxDecoration(color: Color(0xFF7FD4FF), boxShadow: [BoxShadow(color: Color(0xCC7FD4FF), blurRadius: 18, spreadRadius: 5)]),
        ),
      );
}

class _Shine extends StatelessWidget {
  const _Shine({required this.t});
  final double t;
  @override
  Widget build(BuildContext context) => IgnorePointer(
        child: FractionalTranslation(
          translation: Offset(-1.4 + 3.2 * Curves.easeInOut.transform(t), 0),
          child: FractionallySizedBox(
            widthFactor: .5,
            child: Transform(
              transform: Matrix4.skewX(-.35),
              child: const DecoratedBox(decoration: BoxDecoration(gradient: LinearGradient(colors: [Colors.transparent, Color(0x55FFFFFF), Colors.transparent]))),
            ),
          ),
        ),
      );
}

class _GridPainter extends CustomPainter {
  _GridPainter(this.t);
  final double t;
  @override
  void paint(Canvas c, Size s) {
    final p = Paint()..color = const Color(0x2978C8FF)..strokeWidth = 1;
    final off = (t * 400) % 40;
    for (double x = 0; x < s.width; x += 40) {
      c.drawLine(Offset(x, 0), Offset(x, s.height), p);
    }
    for (double y = off; y < s.height; y += 40) {
      c.drawLine(Offset(0, y), Offset(s.width, y), p);
    }
  }

  @override
  bool shouldRepaint(_GridPainter o) => o.t != t;
}

class _Corners extends StatelessWidget {
  const _Corners();
  @override
  Widget build(BuildContext context) => CustomPaint(painter: _CornerPainter());
}

class _CornerPainter extends CustomPainter {
  @override
  void paint(Canvas c, Size s) {
    final p = Paint()..color = const Color(0xFF7FD4FF)..style = PaintingStyle.stroke..strokeWidth = 4..strokeCap = StrokeCap.round;
    const l = 26.0, m = -6.0;
    for (final sx in [0, 1]) {
      for (final sy in [0, 1]) {
        final x = sx == 0 ? m : s.width - m, y = sy == 0 ? m : s.height - m;
        final dx = sx == 0 ? l : -l, dy = sy == 0 ? l : -l;
        c.drawPath(Path()..moveTo(x, y + dy)..lineTo(x, y)..lineTo(x + dx, y), p);
      }
    }
  }

  @override
  bool shouldRepaint(_) => false;
}

class _RingPainter extends CustomPainter {
  _RingPainter(this.v);
  final double v;
  @override
  void paint(Canvas c, Size s) {
    final r = Rect.fromLTWH(6, 6, s.width - 12, s.height - 12);
    c.drawArc(r, 0, math.pi * 2, false, Paint()..color = Colors.white12..style = PaintingStyle.stroke..strokeWidth = 7);
    c.drawArc(r, -math.pi / 2, math.pi * 2 * v.clamp(0, 1), false,
        Paint()..shader = const SweepGradient(colors: [Color(0xFF7FD4FF), saffron], transform: GradientRotation(-math.pi / 2)).createShader(r)..style = PaintingStyle.stroke..strokeWidth = 7..strokeCap = StrokeCap.round);
  }

  @override
  bool shouldRepaint(_RingPainter o) => o.v != v;
}

// ---------------------------------------------------------------- result

class _ResultView extends StatelessWidget {
  const _ResultView({super.key, required this.report, required this.onAgain});
  final Report report;
  final VoidCallback onAgain;

  Widget _in(int i, Widget child) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: 1),
        duration: Duration(milliseconds: 600 + i * 90),
        curve: Curves.easeOutCubic,
        builder: (_, v, c) => Opacity(opacity: v, child: Transform.translate(offset: Offset(0, 26 * (1 - v)), child: c)),
        child: child,
      );

  @override
  Widget build(BuildContext context) {
    final r = report;
    final dets = r.detections;
    final none = !r.aiPending && dets.isEmpty;
    return Scaffold(
      appBar: AppBar(title: Text('Report ${r.code}'), automaticallyImplyLeading: false, actions: [IconButton(onPressed: () => Navigator.of(context).pop(), icon: const Icon(Icons.close))]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        _in(
            0,
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: const Color(0xFFE0F1E6), borderRadius: BorderRadius.circular(16)),
              child: const Row(children: [
                Icon(Icons.check_circle, color: Color(0xFF17663A)),
                SizedBox(width: 10),
                Expanded(child: Text('Thank you. Your report is on the public list.', style: TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF17663A)))),
              ]),
            )),
        const SizedBox(height: 14),
        _in(
            1,
            ClipRRect(
              borderRadius: BorderRadius.circular(22),
              child: BoxedPhoto(url: r.photoUrl, detections: dets),
            )),
        const SizedBox(height: 16),
        if (r.aiPending)
          _in(2, _Card(child: const Text('The AI inspector is busy right now. Your report is saved and will be analysed in a few minutes. Check “Mine” later.')))
        else if (none)
          _in(2, _Card(child: const Text('The AI did not find road damage in this photo, so the report is not public. Try again with a closer photo of the damage.')))
        else ...[
          _in(
              2,
              _Card(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text(r.hazard, style: display(44, h: 1))),
                  UrgencyPill(r.urgency),
                ]),
                const SizedBox(height: 12),
                Text('Severity ${r.severity.toStringAsFixed(1)} / 10', style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: (r.severity / 10).clamp(0, 1)),
                  duration: const Duration(milliseconds: 1300),
                  curve: Curves.easeOutCubic,
                  builder: (_, v, __) => ClipRRect(
                    borderRadius: BorderRadius.circular(99),
                    child: LinearProgressIndicator(value: v, minHeight: 10, backgroundColor: Colors.black12, color: urgencyColor(r.urgency)),
                  ),
                ),
                if (r.recommendation != null && r.recommendation!.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Text(r.recommendation!, style: const TextStyle(height: 1.45)),
                ],
                if (r.costInr > 0) ...[
                  const SizedBox(height: 12),
                  Text('Estimated repair: ${inr(r.costInr)}', style: const TextStyle(fontWeight: FontWeight.w700)),
                ],
              ]))),
          if (dets.length > 1) ...[
            const SizedBox(height: 12),
            _in(3, _Card(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${dets.length} problems found', style: const TextStyle(fontWeight: FontWeight.w800)),
              const SizedBox(height: 6),
              for (final d in dets) Padding(padding: const EdgeInsets.symmetric(vertical: 2), child: Text('• ${d.hazard} · severity ${d.severity.toStringAsFixed(1)} · ${urgencyLabel(d.urgency)}')),
            ]))),
          ],
        ],
        const SizedBox(height: 16),
        _in(4, SizedBox(width: double.infinity, child: BigButton('Follow this report', icon: Icons.timeline, onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailPage(code: r.code)))))),
        const SizedBox(height: 10),
        _in(5, SizedBox(width: double.infinity, height: 52, child: OutlinedButton(style: OutlinedButton.styleFrom(shape: const StadiumBorder()), onPressed: onAgain, child: const Text('Report another problem', style: TextStyle(fontWeight: FontWeight.w700))))),
        const SizedBox(height: 24),
      ]),
    );
  }
}

class _Card extends StatelessWidget {
  const _Card({required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => Container(width: double.infinity, padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: paper, borderRadius: BorderRadius.circular(18)), child: child);
}
