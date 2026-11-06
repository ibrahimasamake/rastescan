import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api.dart';
import '../ui.dart';
import 'detail.dart';

/// Every public report as a photo, worst first. Filters are plain text tabs with a lane-paint underline.
class ReportsPage extends StatefulWidget {
  const ReportsPage({super.key});
  @override
  State<ReportsPage> createState() => _ReportsPageState();
}

class _ReportsPageState extends State<ReportsPage> {
  final scroll = ScrollController();
  final items = <Report>[];
  String status = 'open';
  String sort = 'urgency';
  int page = 1;
  int total = 0;
  bool busy = false;
  Object? error;

  @override
  void initState() {
    super.initState();
    scroll.addListener(() {
      if (scroll.position.pixels > scroll.position.maxScrollExtent - 700) _more();
    });
    _reset();
  }

  @override
  void dispose() {
    scroll.dispose();
    super.dispose();
  }

  Future<void> _reset() async {
    setState(() {
      items.clear();
      page = 1;
      total = 0;
      error = null;
    });
    await _more();
  }

  Future<void> _more() async {
    if (busy || (items.isNotEmpty && items.length >= total)) return;
    setState(() => busy = true);
    try {
      final p = await Api.instance.reports(status: status, sort: sort, page: page);
      if (!mounted) return;
      setState(() {
        items.addAll(p.items);
        total = p.total;
        page++;
      });
    } catch (e) {
      if (mounted) setState(() => error = e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget _tab(String label, bool on, VoidCallback tap) => Padding(
        padding: const EdgeInsets.only(right: 22),
        child: GestureDetector(
          onTap: () {
            HapticFeedback.selectionClick();
            tap();
          },
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(label, style: display(22, color: on ? Colors.white : const Color(0xFF8D929A), h: 1.1)),
            const SizedBox(height: 4),
            AnimatedContainer(duration: const Duration(milliseconds: 200), height: 3, width: on ? 26 : 0, color: saffron),
          ]),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.of(context).padding.top;
    return Column(children: [
      Container(
        color: navy,
        padding: EdgeInsets.fromLTRB(18, top + 14, 18, 14),
        width: double.infinity,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('All reports', style: display(40, color: Colors.white)),
          const SizedBox(height: 2),
          Text(total == 0 ? 'Loading the list…' : '$total on the public list', style: const TextStyle(color: Color(0xFF9BA0A8))),
          const SizedBox(height: 14),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(children: [
              _tab('Open', status == 'open', () {
                status = 'open';
                _reset();
              }),
              _tab('Fixed', status == 'resolved', () {
                status = 'resolved';
                _reset();
              }),
              _tab('All', status == 'all', () {
                status = 'all';
                _reset();
              }),
              const SizedBox(width: 10),
              Container(width: 1, height: 22, color: Colors.white24),
              const SizedBox(width: 22),
              _tab('Most urgent', sort == 'urgency', () {
                sort = 'urgency';
                _reset();
              }),
              _tab('Newest', sort == 'newest', () {
                sort = 'newest';
                _reset();
              }),
            ]),
          ),
        ]),
      ),
      Expanded(
        child: RefreshIndicator(
          onRefresh: _reset,
          color: navy,
          child: items.isEmpty && !busy
              ? ListView(children: [
                  const SizedBox(height: 120),
                  Center(child: Text(error != null ? 'Could not load reports. Pull down to retry.' : 'No reports here yet.', style: const TextStyle(color: muted))),
                ])
              : GridView.builder(
                  controller: scroll,
                  padding: const EdgeInsets.fromLTRB(14, 14, 14, 110),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, crossAxisSpacing: 12, mainAxisSpacing: 12, childAspectRatio: .72),
                  itemCount: items.isEmpty ? 6 : items.length + (busy ? 2 : 0),
                  itemBuilder: (_, i) => i >= items.length
                      ? const Skeleton(height: 300, radius: 22)
                      : ReportCard(items[i], onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailPage(code: items[i].code, heroPhoto: true)))),
                ),
        ),
      ),
    ]);
  }
}
