import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../api.dart';
import '../ui.dart';
import 'detail.dart';

/// Live map of open reports. "Tour" flies from one report to the next by itself and shows its photo card.
class MapPage extends StatefulWidget {
  const MapPage({super.key});
  @override
  State<MapPage> createState() => _MapPageState();
}

class _MapPageState extends State<MapPage> {
  final controller = MapController();
  List<Report> items = [];
  Report? focus;
  bool touring = false;
  Timer? timer;
  int at = 0;
  bool loading = true;
  Object? error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final p = await Api.instance.reports(status: 'open', sort: 'urgency', perPage: 200);
      if (mounted) setState(() => items = p.items.where((r) => r.lat != null && r.lng != null).toList());
    } catch (e) {
      if (mounted) setState(() => error = e);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void _show(Report r, {double zoom = 13}) {
    setState(() => focus = r);
    controller.move(LatLng(r.lat!, r.lng! - 0.0), zoom);
  }

  void _tour() {
    if (touring) {
      timer?.cancel();
      setState(() => touring = false);
      return;
    }
    if (items.isEmpty) return;
    setState(() => touring = true);
    void next() {
      if (!mounted || items.isEmpty) return;
      _show(items[at % items.length], zoom: 14.5);
      at++;
    }

    next();
    timer = Timer.periodic(const Duration(seconds: 6), (_) => next());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(children: [
        FlutterMap(
          mapController: controller,
          options: MapOptions(
            initialCenter: const LatLng(20.5, 78.9),
            initialZoom: 4.6,
            interactionOptions: const InteractionOptions(flags: InteractiveFlag.all & ~InteractiveFlag.rotate),
            onTap: (_, __) => setState(() => focus = null),
          ),
          children: [
            TileLayer(urlTemplate: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', subdomains: const ['a', 'b', 'c', 'd'], userAgentPackageName: 'tech.rastescan.app'),
            MarkerLayer(markers: [
              for (final r in items)
                Marker(
                  point: LatLng(r.lat!, r.lng!),
                  width: focus?.code == r.code ? 46 : 30,
                  height: focus?.code == r.code ? 46 : 30,
                  child: GestureDetector(
                    onTap: () {
                      timer?.cancel();
                      setState(() => touring = false);
                      _show(r, zoom: 14);
                    },
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 250),
                      decoration: BoxDecoration(
                        color: urgencyColor(r.urgency),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: focus?.code == r.code ? 4 : 2.5),
                        boxShadow: const [BoxShadow(color: Colors.black38, blurRadius: 6)],
                      ),
                    ),
                  ),
                ),
            ]),
            const RichAttributionWidget(attributions: [TextSourceAttribution('© OpenStreetMap contributors © CARTO')]),
          ],
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(color: navy.withValues(alpha: .92), borderRadius: BorderRadius.circular(12)),
                child: Text(loading ? 'Loading…' : '${items.length} open reports', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
              ),
              const Spacer(),
              FilledButton.icon(
                onPressed: _tour,
                icon: Icon(touring ? Icons.stop : Icons.play_arrow),
                label: Text(touring ? 'Stop tour' : 'Play tour'),
                style: FilledButton.styleFrom(backgroundColor: saffron, foregroundColor: navy, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)), padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12)),
              ),
            ]),
          ),
        ),
        if (error != null)
          Center(child: Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(mainAxisSize: MainAxisSize.min, children: [const Text('Could not load the map.'), const SizedBox(height: 8), FilledButton(onPressed: _load, child: const Text('Retry'))])))),
        AnimatedPositioned(
          duration: const Duration(milliseconds: 380),
          curve: Curves.easeOutCubic,
          left: 12,
          right: 12,
          bottom: focus == null ? -280 : 96,
          child: focus == null ? const SizedBox(height: 1) : _Card(r: focus!),
        ),
      ]),
    );
  }
}

class _Card extends StatelessWidget {
  const _Card({required this.r});
  final Report r;
  @override
  Widget build(BuildContext context) => Material(
        elevation: 10,
        borderRadius: BorderRadius.circular(22),
        clipBehavior: Clip.antiAlias,
        color: navy,
        child: InkWell(
          onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailPage(code: r.code))),
          child: Row(children: [
            SizedBox(width: 130, height: 162, child: BoxedPhoto(url: r.photoUrl, detections: r.detections.take(1).toList(), aspect: 130 / 162, showLabels: false)),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  UrgencyPill(r.urgency),
                  const SizedBox(height: 8),
                  Text(r.hazard, style: display(30, color: Colors.white, h: 1)),
                  Text(r.ward ?? r.code, style: const TextStyle(color: Color(0xFFB9BDC4))),
                  const SizedBox(height: 6),
                  Text('AI ${r.severity.toStringAsFixed(1)} · ${ago(r.createdAt)}', style: const TextStyle(fontSize: 12.5, color: Colors.white)),
                  if (r.costInr > 0) Text('Repair ${inr(r.costInr)}', style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: Colors.white)),
                  const SizedBox(height: 6),
                  const Text('Open report', style: TextStyle(color: saffron, fontWeight: FontWeight.w800, fontSize: 12.5)),
                ]),
              ),
            ),
          ]),
        ),
      );
}
