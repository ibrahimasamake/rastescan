import 'package:flutter_test/flutter_test.dart';
import 'package:rastescan/ui.dart';

void main() {
  test('inr formats Indian digit grouping', () {
    expect(inr(4200), '₹4,200');
    expect(inr(1234567), '₹12,34,567');
    expect(inr(90), '₹90');
  });
  test('urgency labels', () {
    expect(urgencyLabel('CRITICAL'), 'Critical');
  });
}
