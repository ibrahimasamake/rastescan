// Officer side of the API: sign in, the ranked queue, and the actions on a report.
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';

class Queue {
  Queue(this.tickets, this.review, this.counts, this.overdue);
  final List<Report> tickets;
  final List<Report> review;
  final Map<String, int> counts;
  final int overdue;
}

class OfficerApi {
  OfficerApi._();
  static final OfficerApi instance = OfficerApi._();
  final http.Client _c = http.Client();
  String? token;
  String? name;
  String? role;

  Future<bool> restore() async {
    final p = await SharedPreferences.getInstance();
    token = p.getString('officer_token');
    name = p.getString('officer_name');
    role = p.getString('officer_role');
    if (token == null) return false;
    try {
      final me = await _req('GET', '/api/v2/auth/me');
      if (me['signed_in'] == true) return true;
    } on ApiError catch (e) {
      if (e.offline) return true; // keep the session, the network is just down
    }
    await signOut();
    return false;
  }

  Future<void> login(String email, String password) async {
    final r = await _req('POST', '/api/v2/auth/login', body: {'email': email.trim(), 'password': password});
    token = r['token'] as String?;
    name = '${r['name']}';
    role = '${r['role']}';
    final p = await SharedPreferences.getInstance();
    await p.setString('officer_token', token!);
    await p.setString('officer_name', name!);
    await p.setString('officer_role', role!);
  }

  Future<void> signOut() async {
    token = null;
    final p = await SharedPreferences.getInstance();
    await p.remove('officer_token');
  }

  Future<dynamic> _req(String method, String path, {Object? body, Map<String, String>? query}) async {
    final uri = Uri.parse(apiBase + path).replace(queryParameters: query);
    final h = {'X-Requested-With': 'RasteScan', if (token != null) 'Authorization': 'Bearer $token', if (body != null) 'Content-Type': 'application/json'};
    try {
      final req = http.Request(method, uri)..headers.addAll(h);
      if (body != null) req.body = jsonEncode(body);
      final res = await http.Response.fromStream(await _c.send(req).timeout(const Duration(seconds: 30)));
      return _decode(res);
    } on ApiError {
      rethrow;
    } catch (_) {
      throw ApiError('offline');
    }
  }

  dynamic _decode(http.Response res) {
    if (res.statusCode >= 200 && res.statusCode < 300) return jsonDecode(utf8.decode(res.bodyBytes));
    var msg = 'error ${res.statusCode}';
    try {
      final b = jsonDecode(utf8.decode(res.bodyBytes));
      if (b is Map && b['detail'] is String) msg = b['detail'];
    } catch (_) {}
    throw ApiError(msg, res.statusCode);
  }

  Report _r(dynamic j) => Report(Map<String, dynamic>.from(j as Map));

  Future<Queue> queue() async {
    final j = await _req('GET', '/api/v2/officer/queue');
    List<Report> l(dynamic v) => ((v as List?) ?? []).map(_r).toList();
    final counts = <String, int>{};
    ((j['counts'] as Map?) ?? {}).forEach((k, v) => counts['$k'] = (v as num).toInt());
    return Queue(l(j['tickets']), l(j['review']), counts, (j['overdue'] as num?)?.toInt() ?? 0);
  }

  Future<Report> report(String code) async => _r(await _req('GET', '/api/v2/officer/reports/$code'));
  Future<List<String>> assignees() async => ((await _req('GET', '/api/v2/officer/assignees')) as List).map((e) => '$e').toList();
  Future<Report> assign(String code, String who) async => _r(await _req('POST', '/api/v2/officer/reports/$code/assign', body: {'assignee': who}));
  Future<Report> setStatus(String code, String status, {String? reason}) async =>
      _r(await _req('POST', '/api/v2/officer/reports/$code/status', body: {'status': status, if (reason != null && reason.isNotEmpty) 'reason': reason}));
  Future<Report> comment(String code, String text) async => _r(await _req('POST', '/api/v2/officer/reports/$code/comment', body: {'body': text}));
  Future<Report> review(String code, String hazard, double severity) async =>
      _r(await _req('POST', '/api/v2/officer/reports/$code/review', body: {'hazard_type': hazard, 'severity_score': severity}));

  Future<Report> repairPhoto(String code, List<int> bytes) async {
    final req = http.MultipartRequest('POST', Uri.parse('$apiBase/api/v2/officer/reports/$code/repair-photo'))
      ..headers.addAll({'X-Requested-With': 'RasteScan', 'Authorization': 'Bearer $token'})
      ..files.add(http.MultipartFile.fromBytes('photo', bytes, filename: 'repair.jpg'));
    try {
      final res = await http.Response.fromStream(await _c.send(req).timeout(const Duration(seconds: 90)));
      return _r(_decode(res));
    } on ApiError {
      rethrow;
    } catch (_) {
      throw ApiError('offline');
    }
  }
}
