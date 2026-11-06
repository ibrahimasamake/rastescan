/// RasteScan API client and models (citizen side).
import 'dart:convert';
import 'dart:math';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// The server the app talks to. Override at build time: --dart-define=API_BASE=https://...
const String apiBase = String.fromEnvironment('API_BASE', defaultValue: 'https://dev.samibrahima.tech');

String absUrl(String? url) {
  if (url == null || url.isEmpty) return '';
  return url.startsWith('http') ? url : apiBase + url;
}

class ApiError implements Exception {
  ApiError(this.message, [this.status = 0]);
  final String message;
  final int status;
  bool get offline => status == 0;
  @override
  String toString() => message;
}

double _d(dynamic v) => v is num ? v.toDouble() : (double.tryParse('$v') ?? 0);
int _i(dynamic v) => v is num ? v.toInt() : (int.tryParse('$v') ?? 0);

class BBox {
  BBox(this.ymin, this.xmin, this.ymax, this.xmax);
  final double ymin, xmin, ymax, xmax;
  bool get valid => xmax > xmin && ymax > ymin;
  factory BBox.from(dynamic j) => j is Map
      ? BBox(_d(j['ymin']), _d(j['xmin']), _d(j['ymax']), _d(j['xmax']))
      : BBox(0, 0, 0, 0);
}

class Detection {
  Detection(this.hazard, this.severity, this.urgency, this.box, this.recommendation, this.hours, this.widthCm, this.depth);
  final String hazard;
  final double severity;
  final String urgency;
  final BBox box;
  final String recommendation;
  final double hours;
  final double widthCm;
  final String depth;
  factory Detection.from(Map j) => Detection(
        '${j['hazard_type']}',
        _d(j['severity_score']),
        '${j['urgency_level']}',
        BBox.from(j['bounding_box']),
        '${j['repair_recommendation'] ?? ''}',
        _d(j['estimated_repair_time_hours']),
        _d((j['estimated_dimensions'] ?? {})['width_cm']),
        '${(j['estimated_dimensions'] ?? {})['depth_category'] ?? ''}',
      );
}

class Report {
  Report(this.json);
  final Map<String, dynamic> json;

  String get code => '${json['code']}';
  String get hazard => '${json['hazard_type']}';
  double get severity => _d(json['severity']);
  String get urgency => '${json['urgency']}';
  String get status => '${json['status']}';
  String get publicStatus => '${json['public_status']}';
  String get photoUrl => absUrl(json['photo_url'] as String?);
  String? get afterPhotoUrl => json['after_photo_url'] == null ? null : absUrl('${json['after_photo_url']}');
  double? get lat => json['lat'] == null ? null : _d(json['lat']);
  double? get lng => json['lng'] == null ? null : _d(json['lng']);
  String? get ward => json['ward'] is Map ? '${json['ward']['name']}' : null;
  String? get assignee => json['assignee'] as String?;
  int get reportedCount => _i(json['reported_count']);
  int get costInr => _i(json['repair_cost_inr'] ?? (json['repair_estimate'] ?? {})['total_inr']);
  bool get overdue => json['overdue'] == true;
  bool get aiPending => json['ai_pending'] == true;
  bool get isDemo => json['is_demo'] == true;
  DateTime get createdAt => DateTime.tryParse('${json['created_at']}')?.toLocal() ?? DateTime.now();
  String? get recommendation => (json['result'] is Map ? json['result']['repair_recommendation'] : json['repair_recommendation']) as String?;
  double get confidence => _d(json['confidence']);

  /// Every defect found in the photo, worst first.
  List<Detection> get detections {
    final r = json['result'];
    if (r is! Map) return [];
    final list = r['detections'];
    if (list is List && list.isNotEmpty) return list.whereType<Map>().map(Detection.from).toList();
    return r['hazard_type'] == 'None' ? [] : [Detection.from(r)];
  }

  List<Map<String, dynamic>> get timeline =>
      ((json['timeline'] as List?) ?? []).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();

  Map<String, dynamic>? get estimate => json['repair_estimate'] is Map ? Map<String, dynamic>.from(json['repair_estimate']) : null;
}

class Page {
  Page(this.items, this.total);
  final List<Report> items;
  final int total;
}

class Stats {
  Stats(this.today, this.open, this.overdue, this.resolvedMonth);
  final int today, open, overdue, resolvedMonth;
  factory Stats.from(Map j) =>
      Stats(_i(j['reported_today']), _i(j['open_now']), _i(j['overdue_now']), _i(j['resolved_this_month']));
}

class Impact {
  Impact(this.j);
  final Map<String, dynamic> j;
  int get tickets => _i(j['tickets']);
  int get open => _i(j['open']);
  int get fixed => _i(j['fixed']);
  int get backlogInr => _i(j['open_backlog_inr']);
  int get repairedInr => _i(j['repaired_value_inr']);
  double? get onTime => j['pct_on_time'] == null ? null : _d(j['pct_on_time']);
  double? get avgHours => j['avg_hours_to_fix'] == null ? null : _d(j['avg_hours_to_fix']);
  List<List<dynamic>> get byHazard => ((j['by_hazard'] as List?) ?? []).map((e) => List<dynamic>.from(e as List)).toList();
  List<Map> get hotspots => ((j['hotspots'] as List?) ?? []).whereType<Map>().toList();
  List<Map> get trend => ((j['trend'] as List?) ?? []).whereType<Map>().toList();
}

class Activity {
  Activity(this.j);
  final Map j;
  String get code => '${j['code']}';
  String get event => '${j['event']}';
  String get hazard => '${j['hazard_type']}';
  String? get ward => j['ward'] is Map ? '${j['ward']['name']}' : null;
  DateTime get at => DateTime.tryParse('${j['at']}')?.toLocal() ?? DateTime.now();
}

class Api {
  Api._();
  static final Api instance = Api._();
  final http.Client _c = http.Client();
  String? _device;

  Future<String> deviceId() async {
    if (_device != null) return _device!;
    final p = await SharedPreferences.getInstance();
    var id = p.getString('device_id');
    if (id == null) {
      final r = Random.secure();
      id = List.generate(32, (_) => r.nextInt(16).toRadixString(16)).join();
      await p.setString('device_id', id);
    }
    return _device = id;
  }

  Future<dynamic> _get(String path, [Map<String, String>? q]) async {
    final uri = Uri.parse(apiBase + path).replace(queryParameters: q);
    try {
      final res = await _c.get(uri).timeout(const Duration(seconds: 25));
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

  Future<Stats> stats() async => Stats.from(await _get('/api/public/stats'));
  Future<Impact> impact({int days = 14}) async => Impact(Map<String, dynamic>.from(await _get('/api/public/impact', {'days': '$days'})));
  Future<List<Activity>> activity({int limit = 10}) async =>
      ((await _get('/api/public/activity', {'limit': '$limit'})) as List).whereType<Map>().map(Activity.new).toList();
  Future<List<Report>> recentlyResolved() async =>
      ((await _get('/api/public/recently-resolved')) as List).whereType<Map>().map((e) => Report(Map<String, dynamic>.from(e))).toList();

  Future<Page> reports({String status = 'open', String sort = 'urgency', int page = 1, int perPage = 24}) async {
    final j = await _get('/api/public/reports', {'status': status, 'sort': sort, 'page': '$page', 'per_page': '$perPage'});
    return Page(((j['items'] as List?) ?? []).whereType<Map>().map((e) => Report(Map<String, dynamic>.from(e))).toList(), _i(j['total']));
  }

  Future<Report> report(String code) async => Report(Map<String, dynamic>.from(await _get('/api/public/reports/$code')));

  Future<List<Report>> mine() async {
    final id = await deviceId();
    final j = await _get('/api/reports', {'device_id': id});
    return (j as List).whereType<Map>().map((e) => Report(Map<String, dynamic>.from(e))).toList();
  }

  Future<int> vote(String code) async {
    final id = await deviceId();
    try {
      final res = await _c
          .post(Uri.parse('$apiBase/api/public/reports/$code/vote'),
              headers: {'Content-Type': 'application/json'}, body: jsonEncode({'device_id': id}))
          .timeout(const Duration(seconds: 20));
      return _i(_decode(res)['reported_count']);
    } on ApiError {
      rethrow;
    } catch (_) {
      throw ApiError('offline');
    }
  }

  /// Sends the photo. The server blurs faces and plates, runs the AI and answers with the finished report.
  Future<Report> submit(List<int> photo, {double? lat, double? lng, String? note}) async {
    final id = await deviceId();
    final req = http.MultipartRequest('POST', Uri.parse('$apiBase/api/reports'))
      ..fields['device_id'] = id
      ..files.add(http.MultipartFile.fromBytes('photo', photo, filename: 'photo.jpg'));
    if (lat != null && lng != null) {
      req.fields['lat'] = '$lat';
      req.fields['lng'] = '$lng';
    }
    if (note != null && note.isNotEmpty) req.fields['note'] = note;
    try {
      final res = await http.Response.fromStream(await _c.send(req).timeout(const Duration(seconds: 90)));
      return Report(Map<String, dynamic>.from(_decode(res)));
    } on ApiError {
      rethrow;
    } catch (_) {
      throw ApiError('offline');
    }
  }
}
