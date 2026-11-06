// Design system. Identity from the road itself: asphalt, lane-paint yellow, highway-sign lettering.
// The one memorable thing is the AI's corner-tick frame on a photo and the dashed lane line. Everything else stays quiet.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';

const navy = Color(0xFF14161A); // asphalt
const navy2 = Color(0xFF1D2025); // wet asphalt
const saffron = Color(0xFFFFC400); // lane paint
const pageBg = Color(0xFFECEBE6); // concrete
const paper = Color(0xFFF8F7F3); // chalk
const muted = Color(0xFF6B6F76);
const hair = Color(0xFFD9D7CF);
const ok = Color(0xFF1E8A4C);
const bad = Color(0xFFD7332A);

/// Highway-sign lettering for headlines and big numbers.
TextStyle display(double size, {Color color = navy, FontWeight w = FontWeight.w800, double h = 1.0, double ls = -.2}) =>
    TextStyle(fontFamily: 'Display', fontSize: size, fontWeight: w, height: h, letterSpacing: ls, color: color);

Color urgencyColor(String u) => switch (u) {
      'CRITICAL' => const Color(0xFFFF4B3E),
      'HIGH' => const Color(0xFFFF8A1F),
      'MEDIUM' => const Color(0xFFFFC400),
      _ => const Color(0xFF4DA3FF),
    };

String urgencyLabel(String u) => switch (u) {
      'CRITICAL' => 'Critical',
      'HIGH' => 'High',
      'MEDIUM' => 'Medium',
      'LOW' => 'Low',
      _ => u,
    };

String statusLabel(String s) => switch (s) {
      'reported' => 'Reported',
      'ai_verified' => 'AI verified',
      'assigned' => 'Assigned',
      'repair_done' => 'Repair done',
      'resolved' => 'Resolved',
      'dismissed' => 'Dismissed',
      _ => s,
    };

String inr(num v) {
  final s = v.round().toString();
  if (s.length <= 3) return '₹$s';
  final last3 = s.substring(s.length - 3);
  var rest = s.substring(0, s.length - 3);
  final parts = <String>[];
  while (rest.length > 2) {
    parts.insert(0, rest.substring(rest.length - 2));
    rest = rest.substring(0, rest.length - 2);
  }
  if (rest.isNotEmpty) parts.insert(0, rest);
  return '₹${parts.join(',')},$last3';
}

String ago(DateTime t) {
  final d = DateTime.now().difference(t);
  if (d.inMinutes < 1) return 'just now';
  if (d.inMinutes < 60) return '${d.inMinutes} min ago';
  if (d.inHours < 24) return '${d.inHours} h ago';
  return '${d.inDays} d ago';
}

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: saffron, brightness: Brightness.light).copyWith(primary: navy, secondary: saffron, surface: paper, onPrimary: Colors.white);
  return ThemeData(
    useMaterial3: true,
    fontFamily: 'Inter',
    colorScheme: scheme,
    scaffoldBackgroundColor: pageBg,
    splashFactory: InkSparkle.splashFactory,
    appBarTheme: AppBarTheme(
      backgroundColor: navy,
      foregroundColor: Colors.white,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: display(28, color: Colors.white),
      systemOverlayStyle: SystemUiOverlayStyle.light,
    ),
    chipTheme: ChipThemeData(shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
    dividerColor: hair,
  );
}

/// A dashed road line. Used as a divider, a progress bar and the timeline spine.
class LaneLine extends StatelessWidget {
  const LaneLine({super.key, this.color = saffron, this.progress = 1, this.dash = 14, this.gap = 9, this.thickness = 3, this.vertical = false});
  final Color color;
  final double progress; // 0..1 of the line drawn
  final double dash, gap, thickness;
  final bool vertical;
  @override
  Widget build(BuildContext context) => CustomPaint(
        painter: _LanePainter(color, progress, dash, gap, thickness, vertical),
        size: vertical ? Size(thickness, double.infinity) : Size(double.infinity, thickness),
      );
}

class _LanePainter extends CustomPainter {
  _LanePainter(this.color, this.progress, this.dash, this.gap, this.t, this.vertical);
  final Color color;
  final double progress, dash, gap, t;
  final bool vertical;
  @override
  void paint(Canvas c, Size s) {
    final len = (vertical ? s.height : s.width) * progress.clamp(0, 1);
    final p = Paint()..color = color..strokeWidth = t..strokeCap = StrokeCap.butt;
    for (double x = 0; x < len; x += dash + gap) {
      final e = (x + dash).clamp(0, len).toDouble();
      if (vertical) {
        c.drawLine(Offset(t / 2, x), Offset(t / 2, e), p);
      } else {
        c.drawLine(Offset(x, t / 2), Offset(e, t / 2), p);
      }
    }
  }

  @override
  bool shouldRepaint(_LanePainter o) => o.progress != progress || o.color != color;
}

/// Small rectangular tag, like a sign plate.
class Pill extends StatelessWidget {
  const Pill(this.text, {super.key, this.color = navy, this.fg = Colors.white, this.icon});
  final String text;
  final Color color;
  final Color fg;
  final IconData? icon;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(6)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (icon != null) ...[Icon(icon, size: 12, color: fg), const SizedBox(width: 4)],
          Text(text, style: TextStyle(color: fg, fontSize: 11.5, fontWeight: FontWeight.w700, letterSpacing: .1)),
        ]),
      );
}

class UrgencyPill extends StatelessWidget {
  const UrgencyPill(this.urgency, {super.key});
  final String urgency;
  @override
  Widget build(BuildContext context) =>
      Pill(urgencyLabel(urgency), color: urgencyColor(urgency), fg: (urgency == 'MEDIUM' || urgency == 'LOW') ? navy : Colors.white);
}

/// Primary action. Lane-paint yellow with black lettering: readable on asphalt and on concrete.
class BigButton extends StatelessWidget {
  const BigButton(this.label, {super.key, required this.onTap, this.icon, this.light = false});
  final String label;
  final VoidCallback? onTap;
  final IconData? icon;
  final bool light;
  @override
  Widget build(BuildContext context) => SizedBox(
        height: 58,
        child: FilledButton.icon(
          onPressed: onTap == null
              ? null
              : () {
                  HapticFeedback.lightImpact();
                  onTap!();
                },
          icon: icon == null ? const SizedBox.shrink() : Icon(icon, size: 22),
          label: Flexible(child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w800, letterSpacing: -.1))),
          style: FilledButton.styleFrom(
            backgroundColor: light ? Colors.white.withValues(alpha: .10) : saffron,
            foregroundColor: light ? Colors.white : navy,
            disabledBackgroundColor: hair,
            side: light ? const BorderSide(color: Colors.white30) : null,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            padding: const EdgeInsets.symmetric(horizontal: 14),
          ),
        ),
      );
}

/// A photo with the AI's damage frames drawn on it. Boxes use the server's 0-1000 coordinates over the original photo,
/// so the photo is laid out with BoxFit.cover and the frames are mapped through the same crop.
class BoxedPhoto extends StatefulWidget {
  const BoxedPhoto({super.key, required this.url, this.detections = const [], this.aspect = 4 / 5, this.showLabels = true, this.alignY = .62});
  final String url;
  final List<Detection> detections;
  final double aspect;
  final bool showLabels;
  final double alignY;

  @override
  State<BoxedPhoto> createState() => _BoxedPhotoState();
}

class _BoxedPhotoState extends State<BoxedPhoto> {
  Size? _size;
  ImageStream? _stream;
  late final ImageStreamListener _listener = ImageStreamListener((info, _) {
    if (mounted) setState(() => _size = Size(info.image.width.toDouble(), info.image.height.toDouble()));
  });

  @override
  void initState() {
    super.initState();
    _resolve();
  }

  @override
  void didUpdateWidget(BoxedPhoto old) {
    super.didUpdateWidget(old);
    if (old.url != widget.url) {
      _size = null;
      _resolve();
    }
  }

  void _resolve() {
    _stream?.removeListener(_listener);
    _stream = NetworkImage(widget.url).resolve(const ImageConfiguration())..addListener(_listener);
  }

  @override
  void dispose() {
    _stream?.removeListener(_listener);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: widget.aspect,
      child: LayoutBuilder(builder: (context, c) {
        final w = c.maxWidth, h = c.maxHeight;
        final img = _size;
        final frames = <Widget>[];
        if (img != null) {
          final k = (w / img.width) > (h / img.height) ? w / img.width : h / img.height;
          final dw = img.width * k, dh = img.height * k;
          final ox = (w - dw) / 2, oy = (h - dh) * widget.alignY;
          for (final d in widget.detections.where((d) => d.box.valid)) {
            final b = d.box;
            final left = (ox + b.xmin / 1000 * dw).clamp(4.0, w - 24);
            final top = (oy + b.ymin / 1000 * dh).clamp(26.0, h - 24);
            final right = (ox + b.xmax / 1000 * dw).clamp(left + 24, w - 4);
            final bottom = (oy + b.ymax / 1000 * dh).clamp(top + 24, h - 4);
            final col = urgencyColor(d.urgency);
            frames.add(Positioned(
              left: left,
              top: top,
              width: right - left,
              height: bottom - top,
              child: _Lock(
                child: Stack(clipBehavior: Clip.none, children: [
                  Positioned.fill(child: CustomPaint(painter: _TickFrame(col))),
                  if (widget.showLabels)
                    Positioned(
                      left: 0,
                      top: -24,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3.5),
                        decoration: BoxDecoration(color: col, borderRadius: BorderRadius.circular(5)),
                        child: Text('${d.hazard}  ${d.severity.toStringAsFixed(1)}',
                            style: TextStyle(color: (d.urgency == 'MEDIUM' || d.urgency == 'LOW') ? navy : Colors.white, fontSize: 11, fontWeight: FontWeight.w800)),
                      ),
                    ),
                ]),
              ),
            ));
          }
        }
        return ClipRect(
          child: Stack(fit: StackFit.expand, children: [
            Container(color: navy2),
            Image.network(widget.url,
                fit: BoxFit.cover,
                alignment: Alignment(0, widget.alignY * 2 - 1),
                errorBuilder: (_, __, ___) => const Center(child: Icon(Icons.broken_image, color: Colors.white38))),
            ...frames,
          ]),
        );
      }),
    );
  }
}

/// Corner ticks and a faint outline: the frame the AI "locks" onto the damage.
class _TickFrame extends CustomPainter {
  _TickFrame(this.color);
  final Color color;
  @override
  void paint(Canvas c, Size s) {
    final faint = Paint()..color = color.withValues(alpha: .35)..style = PaintingStyle.stroke..strokeWidth = 1.2;
    c.drawRect(Offset.zero & s, faint);
    final p = Paint()..color = color..style = PaintingStyle.stroke..strokeWidth = 3.2..strokeCap = StrokeCap.square;
    final l = (s.shortestSide * .28).clamp(10.0, 26.0);
    for (final sx in [0, 1]) {
      for (final sy in [0, 1]) {
        final x = sx == 0 ? 0.0 : s.width, y = sy == 0 ? 0.0 : s.height;
        final dx = sx == 0 ? l : -l, dy = sy == 0 ? l : -l;
        c.drawPath(Path()..moveTo(x, y + dy)..lineTo(x, y)..lineTo(x + dx, y), p);
      }
    }
  }

  @override
  bool shouldRepaint(_TickFrame o) => o.color != color;
}

/// The frame snaps in from a larger size, like a target locking on.
class _Lock extends StatelessWidget {
  const _Lock({required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: 1),
        duration: const Duration(milliseconds: 520),
        curve: Curves.easeOutCubic,
        builder: (_, v, c) => Opacity(opacity: v.clamp(0, 1), child: Transform.scale(scale: 1.35 - .35 * v, child: c)),
        child: child,
      );
}

/// Image-first report card: the photo carries the card, the lettering sits on it.
class ReportCard extends StatelessWidget {
  const ReportCard(this.r, {super.key, required this.onTap});
  final Report r;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    final col = urgencyColor(r.urgency);
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: ClipRRect(
        borderRadius: BorderRadius.circular(22),
        child: Stack(fit: StackFit.expand, children: [
          Image.network(r.photoUrl, fit: BoxFit.cover, alignment: const Alignment(0, .24), errorBuilder: (_, __, ___) => Container(color: navy2)),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, stops: [0, .45, 1], colors: [Color(0x66000000), Color(0x00000000), Color(0xE6101215)]),
            ),
          ),
          Positioned(left: 0, top: 0, bottom: 0, child: Container(width: 5, color: col)),
          Positioned(left: 14, top: 12, child: Text('AI ${r.severity.toStringAsFixed(1)}', style: display(26, color: Colors.white, h: 1))),
          if (r.overdue) const Positioned(right: 10, top: 10, child: Pill('Overdue', color: bad)),
          Positioned(
            left: 14,
            right: 12,
            bottom: 12,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
              Text(r.hazard, maxLines: 1, overflow: TextOverflow.ellipsis, style: display(23, color: Colors.white, h: 1.05)),
              const SizedBox(height: 3),
              Text('${r.ward ?? r.code} · ${ago(r.createdAt)}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white70, fontSize: 12)),
              const SizedBox(height: 8),
              Row(children: [
                Text(statusLabel(r.publicStatus), style: TextStyle(color: col, fontWeight: FontWeight.w800, fontSize: 12)),
                const Spacer(),
                if (r.costInr > 0) Text(inr(r.costInr), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 12.5)),
              ]),
            ]),
          ),
        ]),
      ),
    );
  }
}

/// A grey block that shimmers while data loads.
class Skeleton extends StatefulWidget {
  const Skeleton({super.key, this.height = 100, this.width, this.radius = 18});
  final double height;
  final double? width;
  final double radius;
  @override
  State<Skeleton> createState() => _SkeletonState();
}

class _SkeletonState extends State<Skeleton> with SingleTickerProviderStateMixin {
  late final c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1300))..repeat();
  @override
  void dispose() {
    c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: c,
        builder: (_, __) => Container(
          height: widget.height,
          width: widget.width,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(widget.radius),
            gradient: LinearGradient(
              begin: Alignment(-1.5 + 3 * c.value, 0),
              end: Alignment(-.5 + 3 * c.value, 0),
              colors: const [Color(0xFFDDDBD3), Color(0xFFEFEDE7), Color(0xFFDDDBD3)],
            ),
          ),
        ),
      );
}

/// Shows a message in a small bar at the bottom.
void toast(BuildContext context, String msg) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(msg, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
      behavior: SnackBarBehavior.floating,
      backgroundColor: navy,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ));
}

/// Loads data once and shows a skeleton / error / content.
class Loader<T> extends StatefulWidget {
  const Loader({super.key, required this.load, required this.builder});
  final Future<T> Function() load;
  final Widget Function(BuildContext, T, Future<void> Function() reload) builder;
  @override
  State<Loader<T>> createState() => _LoaderState<T>();
}

class _LoaderState<T> extends State<Loader<T>> {
  T? data;
  Object? error;
  bool busy = true;

  Future<void> _run() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final d = await widget.load();
      if (mounted) setState(() => data = d);
    } catch (e) {
      if (mounted) setState(() => error = e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _run();
  }

  @override
  Widget build(BuildContext context) {
    if (data != null) return widget.builder(context, data as T, _run);
    if (busy) {
      return ListView(padding: const EdgeInsets.all(16), children: const [Skeleton(height: 380, radius: 22), SizedBox(height: 14), Skeleton(height: 34, width: 220, radius: 8), SizedBox(height: 10), Skeleton(height: 18, radius: 6), SizedBox(height: 18), Skeleton(height: 120)]);
    }
    final off = error is ApiError && (error as ApiError).offline;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(off ? Icons.wifi_off : Icons.error_outline, size: 44, color: muted),
          const SizedBox(height: 10),
          Text(off ? 'No connection. Check your internet and try again.' : '$error', textAlign: TextAlign.center),
          const SizedBox(height: 14),
          BigButton('Try again', icon: Icons.refresh, onTap: _run),
        ]),
      ),
    );
  }
}

/// Floating bottom bar with the report button raised in the middle.
class FloatNav extends StatelessWidget {
  const FloatNav({super.key, required this.index, required this.onTap, required this.onReport});
  final int index;
  final void Function(int) onTap;
  final VoidCallback onReport;

  @override
  Widget build(BuildContext context) {
    Widget item(int i, IconData icon, IconData on, String label) {
      final sel = index == i;
      return Expanded(
        child: InkResponse(
          onTap: () {
            HapticFeedback.selectionClick();
            onTap(i);
          },
          child: SizedBox(
            height: 62,
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              AnimatedContainer(duration: const Duration(milliseconds: 220), width: sel ? 22 : 0, height: 3, margin: const EdgeInsets.only(bottom: 5), decoration: BoxDecoration(color: saffron, borderRadius: BorderRadius.circular(2))),
              Icon(sel ? on : icon, size: 24, color: sel ? Colors.white : Colors.white54),
              const SizedBox(height: 2),
              Text(label, style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: sel ? Colors.white : Colors.white54)),
            ]),
          ),
        ),
      );
    }

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
        child: Container(
          height: 66,
          decoration: BoxDecoration(
            color: navy.withValues(alpha: .96),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: Colors.white12),
            boxShadow: const [BoxShadow(color: Color(0x55000000), blurRadius: 24, offset: Offset(0, 10))],
          ),
          child: Row(children: [
            item(0, Icons.home_outlined, Icons.home_rounded, 'Home'),
            item(1, Icons.grid_view_outlined, Icons.grid_view_rounded, 'Reports'),
            Expanded(
              child: Center(
                child: GestureDetector(
                  onTap: () {
                    HapticFeedback.mediumImpact();
                    onReport();
                  },
                  child: Container(
                    width: 54,
                    height: 54,
                    decoration: BoxDecoration(color: saffron, borderRadius: BorderRadius.circular(18), boxShadow: const [BoxShadow(color: Color(0x66FFC400), blurRadius: 18, offset: Offset(0, 6))]),
                    child: const Icon(Icons.photo_camera_rounded, color: navy, size: 27),
                  ),
                ),
              ),
            ),
            item(3, Icons.map_outlined, Icons.map_rounded, 'Map'),
            item(4, Icons.person_outline, Icons.person_rounded, 'Mine'),
          ]),
        ),
      ),
    );
  }
}
