import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../api.dart';
import '../officer_api.dart';
import '../ui.dart';

/// Shows the sign-in form or the queue, depending on whether this phone holds a valid officer session.
class OfficerGate extends StatefulWidget {
  const OfficerGate({super.key});
  @override
  State<OfficerGate> createState() => _OfficerGateState();
}

class _OfficerGateState extends State<OfficerGate> {
  bool? signedIn;

  @override
  void initState() {
    super.initState();
    OfficerApi.instance.restore().then((v) {
      if (mounted) setState(() => signedIn = v);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (signedIn == null) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    return signedIn! ? QueuePage(onSignOut: () => setState(() => signedIn = false)) : _Login(onDone: () => setState(() => signedIn = true));
  }
}

class _Login extends StatefulWidget {
  const _Login({required this.onDone});
  final VoidCallback onDone;
  @override
  State<_Login> createState() => _LoginState();
}

class _LoginState extends State<_Login> {
  final email = TextEditingController();
  final pass = TextEditingController();
  bool busy = false, show = false;
  String? error;

  Future<void> _go() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await OfficerApi.instance.login(email.text, pass.text);
      widget.onDone();
    } catch (e) {
      setState(() => error = e is ApiError && e.offline ? 'No connection. Try again.' : '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    email.dispose();
    pass.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    InputDecoration deco(String l, IconData i) => InputDecoration(
        labelText: l, prefixIcon: Icon(i), filled: true, fillColor: paper, border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none));
    return Scaffold(
      appBar: AppBar(title: const Text('Officer sign in')),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        const SizedBox(height: 10),
        const Icon(Icons.badge_outlined, size: 56, color: navy),
        const SizedBox(height: 10),
        Text('Ward and city staff', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontSize: 26)),
        const SizedBox(height: 6),
        const Text('Sign in to work the ranked repair queue.', style: TextStyle(color: muted)),
        const SizedBox(height: 22),
        TextField(controller: email, keyboardType: TextInputType.emailAddress, autocorrect: false, decoration: deco('Email', Icons.mail_outline)),
        const SizedBox(height: 12),
        TextField(
          controller: pass,
          obscureText: !show,
          onSubmitted: (_) => busy ? null : _go(),
          decoration: deco('Password', Icons.lock_outline).copyWith(suffixIcon: IconButton(icon: Icon(show ? Icons.visibility_off : Icons.visibility), onPressed: () => setState(() => show = !show))),
        ),
        if (error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(error!, style: const TextStyle(color: Color(0xFFA3161A), fontWeight: FontWeight.w600))),
        const SizedBox(height: 20),
        SizedBox(width: double.infinity, child: BigButton(busy ? 'Signing in…' : 'Sign in', icon: Icons.login, onTap: busy ? null : _go)),
      ]),
    );
  }
}

class QueuePage extends StatefulWidget {
  const QueuePage({super.key, required this.onSignOut});
  final VoidCallback onSignOut;
  @override
  State<QueuePage> createState() => _QueuePageState();
}

class _QueuePageState extends State<QueuePage> with SingleTickerProviderStateMixin {
  late Future<Queue> future = OfficerApi.instance.queue();
  late final tabs = TabController(length: 2, vsync: this);

  void reload() => setState(() => future = OfficerApi.instance.queue());

  Future<void> _open(Report r) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => OfficerReportPage(code: r.code)));
    reload();
  }

  @override
  void dispose() {
    tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Queue · ${OfficerApi.instance.name ?? ''}'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await OfficerApi.instance.signOut();
              widget.onSignOut();
            },
          ),
        ],
        bottom: TabBar(controller: tabs, indicatorColor: saffron, labelColor: Colors.white, unselectedLabelColor: Colors.white60, tabs: const [Tab(text: 'Repair queue'), Tab(text: 'AI review')]),
      ),
      body: FutureBuilder<Queue>(
        future: future,
        builder: (_, s) {
          if (s.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (s.hasError) {
            final e = s.error;
            if (e is ApiError && e.status == 401) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                OfficerApi.instance.signOut();
                widget.onSignOut();
              });
            }
            return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [Text(e is ApiError && e.offline ? 'No connection.' : '$e'), const SizedBox(height: 10), FilledButton(onPressed: reload, child: const Text('Try again'))]));
          }
          final q = s.data!;
          return Column(children: [
            Container(
              color: navy,
              padding: const EdgeInsets.fromLTRB(14, 4, 14, 14),
              child: Row(children: [
                for (final u in const ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'])
                  Expanded(
                    child: Container(
                      margin: const EdgeInsets.only(right: 6),
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      decoration: BoxDecoration(color: Colors.white10, borderRadius: BorderRadius.circular(12), border: Border(left: BorderSide(color: urgencyColor(u), width: 4))),
                      child: Column(children: [
                        Text('${q.counts[u] ?? 0}', style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w800)),
                        Text(urgencyLabel(u), style: const TextStyle(color: Colors.white60, fontSize: 11)),
                      ]),
                    ),
                  ),
              ]),
            ),
            Expanded(
              child: TabBarView(controller: tabs, children: [
                _list(q.tickets, 'The queue is empty. Nice work.'),
                _list(q.review, 'Nothing waiting for review.'),
              ]),
            ),
          ]);
        },
      ),
    );
  }

  Widget _list(List<Report> items, String empty) => RefreshIndicator(
        onRefresh: () async => reload(),
        child: items.isEmpty
            ? ListView(children: [const SizedBox(height: 120), Center(child: Text(empty))])
            : ListView.separated(
                padding: const EdgeInsets.all(12),
                itemCount: items.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (_, i) {
                  final r = items[i];
                  return Material(
                    color: paper,
                    borderRadius: BorderRadius.circular(16),
                    clipBehavior: Clip.antiAlias,
                    child: InkWell(
                      onTap: () => _open(r),
                      child: Row(children: [
                        SizedBox(width: 92, height: 108, child: Image.network(r.photoUrl, fit: BoxFit.cover, alignment: const Alignment(0, .24), errorBuilder: (_, __, ___) => Container(color: navy2))),
                        Expanded(
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Row(children: [Expanded(child: Text(r.hazard, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16))), UrgencyPill(r.urgency)]),
                              const SizedBox(height: 3),
                              Text('${r.code} · ${r.ward ?? 'no ward'} · ${ago(r.createdAt)}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: muted, fontSize: 12.5)),
                              const SizedBox(height: 7),
                              Wrap(spacing: 6, children: [
                                Pill('AI ${r.severity.toStringAsFixed(1)}', color: const Color(0xFFEAF0F7), fg: navy),
                                Pill(r.assignee ?? 'Unassigned', color: r.assignee == null ? const Color(0xFFFCF1CC) : const Color(0xFFE0F1E6), fg: navy),
                                if (r.overdue) const Pill('Overdue', color: Color(0xFFA3161A)),
                              ]),
                            ]),
                          ),
                        ),
                      ]),
                    ),
                  );
                },
              ),
      );
}

class OfficerReportPage extends StatefulWidget {
  const OfficerReportPage({super.key, required this.code});
  final String code;
  @override
  State<OfficerReportPage> createState() => _OfficerReportPageState();
}

class _OfficerReportPageState extends State<OfficerReportPage> {
  final o = OfficerApi.instance;
  Report? r;
  Object? error;
  bool busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final x = await o.report(widget.code);
      if (mounted) setState(() => r = x);
    } catch (e) {
      if (mounted) setState(() => error = e);
    }
  }

  Future<void> _do(Future<Report> Function() action, String ok) async {
    setState(() => busy = true);
    try {
      await action();
      await _load();
      if (mounted) toast(context, ok);
    } catch (e) {
      if (mounted) toast(context, e is ApiError && e.offline ? 'No connection.' : '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<String?> _ask(String title, {String hint = '', bool multiline = false}) {
    final c = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: TextField(controller: c, autofocus: true, maxLines: multiline ? 3 : 1, decoration: InputDecoration(hintText: hint)),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(ctx, c.text.trim()), child: const Text('OK'))],
      ),
    );
  }

  Future<void> _assign() async {
    List<String> names = [];
    try {
      names = await o.assignees();
    } catch (_) {}
    if (!mounted) return;
    final pick = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: ListView(shrinkWrap: true, children: [
          const Padding(padding: EdgeInsets.fromLTRB(20, 0, 20, 8), child: Text('Assign to', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18))),
          for (final n in names) ListTile(leading: const Icon(Icons.engineering), title: Text(n), onTap: () => Navigator.pop(ctx, n)),
          ListTile(leading: const Icon(Icons.edit), title: const Text('Another crew or person…'), onTap: () => Navigator.pop(ctx, '__other')),
        ]),
      ),
    );
    if (pick == null) return;
    final who = pick == '__other' ? await _ask('Assign to', hint: 'Crew or officer name') : pick;
    if (who == null || who.isEmpty) return;
    await _do(() => o.assign(widget.code, who), 'Assigned to $who');
  }

  Future<void> _photo() async {
    final src = await showModalBottomSheet<ImageSource>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(leading: const Icon(Icons.photo_camera), title: const Text('Take after-repair photo'), onTap: () => Navigator.pop(ctx, ImageSource.camera)),
          ListTile(leading: const Icon(Icons.photo_library), title: const Text('Choose from gallery'), onTap: () => Navigator.pop(ctx, ImageSource.gallery)),
        ]),
      ),
    );
    if (src == null) return;
    final x = await ImagePicker().pickImage(source: src, maxWidth: 1800, imageQuality: 85);
    if (x == null) return;
    final bytes = await x.readAsBytes();
    await _do(() => o.repairPhoto(widget.code, bytes), 'Repair photo uploaded');
  }

  @override
  Widget build(BuildContext context) {
    final rep = r;
    return Scaffold(
      appBar: AppBar(title: Text(widget.code)),
      body: rep == null
          ? Center(child: error == null ? const CircularProgressIndicator() : Column(mainAxisSize: MainAxisSize.min, children: [Text('$error'), const SizedBox(height: 10), FilledButton(onPressed: _load, child: const Text('Retry'))]))
          : Stack(children: [
              ListView(padding: const EdgeInsets.all(16), children: [
                ClipRRect(borderRadius: BorderRadius.circular(20), child: BoxedPhoto(url: rep.photoUrl, detections: rep.detections)),
                const SizedBox(height: 14),
                Row(children: [Expanded(child: Text(rep.hazard, style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w800, letterSpacing: -.7))), UrgencyPill(rep.urgency)]),
                const SizedBox(height: 4),
                Text('${rep.ward ?? 'No ward'} · ${ago(rep.createdAt)} · ${rep.reportedCount} citizen${rep.reportedCount == 1 ? '' : 's'}', style: const TextStyle(color: muted)),
                const SizedBox(height: 10),
                Wrap(spacing: 8, runSpacing: 6, children: [
                  Pill('Status: ${rep.status}', color: navy),
                  Pill('AI ${rep.severity.toStringAsFixed(1)}', color: const Color(0xFFEAF0F7), fg: navy),
                  Pill(rep.assignee ?? 'Unassigned', color: const Color(0xFFEAF0F7), fg: navy, icon: Icons.engineering),
                  if (rep.costInr > 0) Pill(inr(rep.costInr), color: const Color(0xFFEAF0F7), fg: navy),
                  if (rep.overdue) const Pill('Overdue', color: Color(0xFFA3161A)),
                ]),
                if (rep.recommendation != null) ...[const SizedBox(height: 14), Text(rep.recommendation!, style: const TextStyle(height: 1.45))],
                if (rep.afterPhotoUrl != null) ...[
                  const SizedBox(height: 16),
                  const Text('After repair', style: TextStyle(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 8),
                  ClipRRect(borderRadius: BorderRadius.circular(16), child: BoxedPhoto(url: rep.afterPhotoUrl!)),
                ],
                const SizedBox(height: 18),
                const Text('Actions', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17)),
                const SizedBox(height: 8),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  _Act(Icons.engineering, 'Assign', busy ? null : _assign),
                  _Act(Icons.add_a_photo, 'Repair photo', busy ? null : _photo),
                  _Act(Icons.build_circle, 'Mark fixed', busy ? null : () => _do(() => o.setStatus(widget.code, 'fixed'), 'Marked fixed')),
                  _Act(Icons.verified, 'Verify', busy ? null : () => _do(() => o.setStatus(widget.code, 'verified'), 'Verified and closed')),
                  _Act(Icons.replay, 'Reopen', busy ? null : () => _do(() => o.setStatus(widget.code, 'new'), 'Reopened')),
                  _Act(Icons.comment, 'Comment', busy ? null : () async {
                    final t = await _ask('Add a comment', multiline: true);
                    if (t != null && t.isNotEmpty) await _do(() => o.comment(widget.code, t), 'Comment added');
                  }),
                  _Act(Icons.block, 'Dismiss', busy ? null : () async {
                    final t = await _ask('Why dismiss?', hint: 'Reason (shown publicly)');
                    if (t != null) await _do(() => o.setStatus(widget.code, 'dismissed', reason: t), 'Dismissed');
                  }, danger: true),
                ]),
                const SizedBox(height: 20),
                const Text('History', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17)),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(color: paper, borderRadius: BorderRadius.circular(16)),
                  child: Column(children: [
                    for (final h in ((rep.json['history'] as List?) ?? rep.timeline).reversed.take(15))
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 5),
                        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          const Padding(padding: EdgeInsets.only(top: 5), child: Icon(Icons.circle, size: 8, color: saffron)),
                          const SizedBox(width: 10),
                          Expanded(child: Text('${h['event']}${h['new_value'] != null ? ': ${h['new_value']}' : ''}  · ${h['actor']}', style: const TextStyle(height: 1.3))),
                          Text(ago(DateTime.tryParse('${h['at']}')?.toLocal() ?? DateTime.now()), style: const TextStyle(color: muted, fontSize: 12)),
                        ]),
                      ),
                  ]),
                ),
                const SizedBox(height: 30),
              ]),
              if (busy) const Positioned(top: 0, left: 0, right: 0, child: LinearProgressIndicator(color: saffron)),
            ]),
    );
  }
}

class _Act extends StatelessWidget {
  const _Act(this.icon, this.label, this.onTap, {this.danger = false});
  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final bool danger;
  @override
  Widget build(BuildContext context) => ActionChip(
        avatar: Icon(icon, size: 18, color: danger ? const Color(0xFFA3161A) : navy),
        label: Text(label, style: TextStyle(fontWeight: FontWeight.w700, color: danger ? const Color(0xFFA3161A) : navy)),
        onPressed: onTap,
        backgroundColor: Colors.white,
        side: BorderSide(color: danger ? const Color(0xFFA3161A) : Colors.black26),
        shape: const StadiumBorder(),
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 10),
      );
}
