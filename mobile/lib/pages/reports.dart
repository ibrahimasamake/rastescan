import 'package:flutter/material.dart';

import '../api.dart';
import '../ui.dart';
import 'detail.dart';

/// All public reports as photo cards, worst first, with filters and endless scrolling.
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
      if (scroll.position.pixels > scroll.position.maxScrollExtent - 600) _more();
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('All reports')),
      body: Column(children: [
        Container(
          color: navy,
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(children: [
              for (final f in const [('open', 'Open'), ('resolved', 'Fixed'), ('all', 'All')])
                _Chip(f.$2, status == f.$1, () {
                  status = f.$1;
                  _reset();
                }),
              const SizedBox(width: 10),
              for (final f in const [('urgency', 'Most urgent'), ('newest', 'Newest')])
                _Chip(f.$2, sort == f.$1, () {
                  sort = f.$1;
                  _reset();
                }),
            ]),
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _reset,
            child: items.isEmpty && !busy
                ? ListView(children: [
                    const SizedBox(height: 120),
                    Center(child: Text(error != null ? 'Could not load reports. Pull down to retry.' : 'No reports here yet.')),
                  ])
                : GridView.builder(
                    controller: scroll,
                    padding: const EdgeInsets.all(12),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, crossAxisSpacing: 12, mainAxisSpacing: 12, childAspectRatio: .66),
                    itemCount: items.length + (busy ? 1 : 0),
                    itemBuilder: (_, i) => i >= items.length
                        ? const Center(child: CircularProgressIndicator())
                        : ReportCard(items[i], onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailPage(code: items[i].code)))),
                  ),
          ),
        ),
      ]),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip(this.label, this.on, this.tap);
  final String label;
  final bool on;
  final VoidCallback tap;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(right: 8),
        child: ChoiceChip(
          label: Text(label),
          selected: on,
          onSelected: (_) => tap(),
          showCheckmark: false,
          labelStyle: TextStyle(color: on ? navy : Colors.white, fontWeight: FontWeight.w700),
          backgroundColor: Colors.white12,
          selectedColor: Colors.white,
          side: BorderSide.none,
          shape: const StadiumBorder(),
        ),
      );
}
