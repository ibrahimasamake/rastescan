/// Theme, formatting and widgets shared by every screen.
import 'package:flutter/material.dart';

import 'api.dart';

const navy = Color(0xFF060E1D);
const navy2 = Color(0xFF0D1C36);
const saffron = Color(0xFFF29A2E);
const pageBg = Color(0xFFF4F6FA);

Color urgencyColor(String u) => switch (u) {
      'CRITICAL' => const Color(0xFFE5382B),
      'HIGH' => const Color(0xFFF2761E),
      'MEDIUM' => const Color(0xFFE9B500),
      _ => const Color(0xFF3F8CE8),
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
  final base = ColorScheme.fromSeed(seedColor: const Color(0xFF13315C), primary: const Color(0xFF13315C), secondary: saffron, surface: Colors.white);
  return ThemeData(
    useMaterial3: true,
    colorScheme: base,
    scaffoldBackgroundColor: pageBg,
    appBarTheme: const AppBarTheme(backgroundColor: navy, foregroundColor: Colors.white, elevation: 0, centerTitle: false),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: navy,
      indicatorColor: Colors.white,
      labelTextStyle: WidgetStateProperty.resolveWith((s) => TextStyle(
          fontSize: 12, fontWeight: FontWeight.w600, color: s.contains(WidgetState.selected) ? Colors.white : Colors.white70)),
      iconTheme: WidgetStateProperty.resolveWith((s) => IconThemeData(color: s.contains(WidgetState.selected) ? navy : Colors.white70)),
    ),
    textTheme: const TextTheme(
      headlineMedium: TextStyle(fontWeight: FontWeight.w800, letterSpacing: -1),
      titleLarge: TextStyle(fontWeight: FontWeight.w800, letterSpacing: -.5),
      titleMedium: TextStyle(fontWeight: FontWeight.w700, letterSpacing: -.2),
    ),
  );
}

class Pill extends StatelessWidget {
  const Pill(this.text, {super.key, this.color = navy, this.fg = Colors.white, this.icon});
  final String text;
  final Color color;
  final Color fg;
  final IconData? icon;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(99)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (icon != null) ...[Icon(icon, size: 12, color: fg), const SizedBox(width: 4)],
          Text(text, style: TextStyle(color: fg, fontSize: 11.5, fontWeight: FontWeight.w700)),
        ]),
      );
}

class UrgencyPill extends StatelessWidget {
  const UrgencyPill(this.urgency, {super.key});
  final String urgency;
  @override
  Widget build(BuildContext context) =>
      Pill(urgencyLabel(urgency), color: urgencyColor(urgency), fg: urgency == 'MEDIUM' ? const Color(0xFF1A1F26) : Colors.white);
}

/// Pill button used for the main actions.
class BigButton extends StatelessWidget {
  const BigButton(this.label, {super.key, required this.onTap, this.icon, this.light = false});
  final String label;
  final VoidCallback? onTap;
  final IconData? icon;
  final bool light;
  @override
  Widget build(BuildContext context) => SizedBox(
        height: 56,
        child: FilledButton.icon(
          onPressed: onTap,
          icon: icon == null ? const SizedBox.shrink() : Icon(icon, size: 22),
          label: Text(label, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          style: FilledButton.styleFrom(
            backgroundColor: light ? Colors.white.withValues(alpha: .12) : saffron,
            foregroundColor: light ? Colors.white : navy,
            side: light ? const BorderSide(color: Colors.white38) : null,
            shape: const StadiumBorder(),
            padding: const EdgeInsets.symmetric(horizontal: 26),
          ),
        ),
      );
}

/// A photo with the AI's damage boxes drawn on it. Boxes use the server's 0-1000 coordinates over the original photo,
/// so the photo is laid out with BoxFit.cover and the boxes are mapped through the same crop.
class BoxedPhoto extends StatefulWidget {
  const BoxedPhoto({super.key, required this.url, this.detections = const [], this.aspect = 4 / 5, this.showLabels = true, this.alignY = .62});
  final String url;
  final List<Detection> detections;
  final double aspect;
  final bool showLabels;
  final double alignY; // where the crop is anchored vertically (road damage sits low in the frame)

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
        final boxes = <Widget>[];
        if (img != null) {
          final k = (w / img.width) > (h / img.height) ? w / img.width : h / img.height;
          final dw = img.width * k, dh = img.height * k;
          final ox = (w - dw) / 2, oy = (h - dh) * widget.alignY;
          for (final d in widget.detections.where((d) => d.box.valid)) {
            final b = d.box;
            final left = (ox + b.xmin / 1000 * dw).clamp(0.0, w - 12);
            final top = (oy + b.ymin / 1000 * dh).clamp(0.0, h - 12);
            final right = (ox + b.xmax / 1000 * dw).clamp(left + 12, w);
            final bottom = (oy + b.ymax / 1000 * dh).clamp(top + 12, h);
            final col = urgencyColor(d.urgency);
            boxes.add(Positioned(
              left: left,
              top: top,
              width: right - left,
              height: bottom - top,
              child: _PopIn(
                child: Container(
                  decoration: BoxDecoration(border: Border.all(color: col, width: 2.5), borderRadius: BorderRadius.circular(6)),
                  child: widget.showLabels
                      ? Align(
                          alignment: Alignment.topLeft,
                          child: Transform.translate(
                            offset: const Offset(-2.5, -22),
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                              decoration: BoxDecoration(color: col, borderRadius: BorderRadius.circular(5)),
                              child: Text('${d.hazard} · ${d.severity.toStringAsFixed(1)}',
                                  style: TextStyle(color: d.urgency == 'MEDIUM' ? Colors.black : Colors.white, fontSize: 11, fontWeight: FontWeight.w800)),
                            ),
                          ),
                        )
                      : null,
                ),
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
            ...boxes,
          ]),
        );
      }),
    );
  }
}

class _PopIn extends StatelessWidget {
  const _PopIn({required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: 1),
        duration: const Duration(milliseconds: 650),
        curve: Curves.easeOutBack,
        builder: (_, v, c) => Opacity(opacity: v.clamp(0, 1), child: Transform.scale(scale: 1.8 - .8 * v, child: c)),
        child: child,
      );
}

class ReportCard extends StatelessWidget {
  const ReportCard(this.r, {super.key, required this.onTap});
  final Report r;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      elevation: 0,
      borderRadius: BorderRadius.circular(18),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Stack(children: [
            AspectRatio(
              aspectRatio: 4 / 5,
              child: Image.network(r.photoUrl, fit: BoxFit.cover, alignment: const Alignment(0, .24),
                  errorBuilder: (_, __, ___) => Container(color: navy2)),
            ),
            Positioned(left: 8, top: 8, child: UrgencyPill(r.urgency)),
            Positioned(
                right: 8,
                top: 8,
                child: Pill('AI ${r.severity.toStringAsFixed(1)}', color: navy.withValues(alpha: .85))),
            if (r.overdue) const Positioned(left: 8, bottom: 8, child: Pill('Past deadline', color: Color(0xFFA3161A))),
          ]),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(r.hazard, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
              const SizedBox(height: 2),
              Text('${r.ward ?? r.code} · ${ago(r.createdAt)}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.black54, fontSize: 12)),
              const SizedBox(height: 6),
              Row(children: [
                Pill(statusLabel(r.publicStatus), color: const Color(0xFFEAF0F7), fg: navy),
                const Spacer(),
                if (r.costInr > 0) Text(inr(r.costInr), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12)),
              ]),
            ]),
          ),
        ]),
      ),
    );
  }
}

/// Shows a message in a small bar at the bottom.
void toast(BuildContext context, String msg) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(msg), behavior: SnackBarBehavior.floating));
}

/// Loads data once and shows spinner / error / content.
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
    if (busy) return const Center(child: CircularProgressIndicator());
    final off = error is ApiError && (error as ApiError).offline;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(off ? Icons.wifi_off : Icons.error_outline, size: 44, color: Colors.black38),
          const SizedBox(height: 10),
          Text(off ? 'No connection. Check your internet and try again.' : '$error', textAlign: TextAlign.center),
          const SizedBox(height: 14),
          FilledButton(onPressed: _run, child: const Text('Try again')),
        ]),
      ),
    );
  }
}
