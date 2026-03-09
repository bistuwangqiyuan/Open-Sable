import unittest
from datetime import datetime, timezone, timedelta
timestamp = 1717854000
iso_date = '2024-06-10T12:00:00Z'
aware_datetime = datetime(2024, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
naive_datetime = datetime(2024, 6, 10, 12, 0, 0)

class DatetimeTests(unittest.TestCase):
    def setUp(self):
        self.aware_datetime = aware_datetime
        self.naive_datetime = naive_datetime
        self.test_timezones = {
            'UTC': timezone.utc,
            'EST': timezone(timedelta(hours=-5)),
            'CET': timezone(timedelta(hours=1)),
            'JST': timezone(timedelta(hours=9))
        }

    # ---------- PARSE METHODS ----------
    def test_parse_iso_success(self):
        parsed = parse_datetime(iso_date)
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 6)
        self.assertEqual(parsed.day, 10)
        self.assertEqual(parsed.tzinfo.utcoffset(), timedelta(0))

    def test_parse_iso_with_timezone(self):
        iso_with_tz = '2024-06-10T12:00:00+02:00'
        parsed = parse_datetime(iso_with_tz)
        self.assertEqual(parsed.tzinfo.utcoffset(), timedelta(hours=2))

    def test_parse_rfc3339_success(self):
        rfc_date = 'Mon, 10 Jun 2024 12:00:00 GMT'
        parsed = parse_datetime(rfc_date)
        self.assertEqual(parsed.year, 2024)

    def test_parse_invalid_format_fails(self):
        with self.assertRaises(ValueError):
            parse_datetime('invalid-date')

    def test_parse_missing_seconds_warns(self):
        with self.assertWarns(UserWarning):
            parse_datetime('2024-06-10T12:00')

    # ---------- FORMAT METHODS ----------
    def test_format_iso_roundtrip(self):
        formatted = format_datetime(self.aware_datetime, 'iso')
        self.assertEqual(formatted, iso_date)

    def test_format_rfc3339_roundtrip(self):
        formatted = format_datetime(self.aware_datetime, 'rfc3339')
        parsed = parse_datetime(formatted)
        self.assertEqual(parsed, self.aware_datetime)

    def test_format_custom_template(self):
        formatted = format_datetime(self.aware_datetime, '%Y-%m-%d %H:%M')
        self.assertEqual(formatted, '2024-06-10 12:00')

    def test_format_localized_date(self):
        localized = format_datetime(self.aware_datetime, 'localized', locale='de')
        self.assertIn('Deutsch', localized)

    # ---------- COMPARISON METHODS ----------
    def test_date_eq_operator(self):
        other = datetime(2024, 6, 10, tzinfo=timezone.utc)
        self.assertTrue(self.aware_datetime == other)

    def test_date_ne_operator(self):
        other = datetime(2024, 6, 11, tzinfo=timezone.utc)
        self.assertTrue(self.aware_datetime != other)

    def test_lt_operator(self):
        future = datetime(2025, 1, 1, tzinfo=timezone.utc)
        self.assertTrue(self.aware_datetime < future)

    def test_gt_operator(self):
        past = datetime(2023, 1, 1, tzinfo=timezone.utc)
        self.assertTrue(self.aware_datetime > past)

    # ---------- TIMEZONE METHODS ----------
    def test_convert_timezone(self):
        cet_time = convert_timezone(self.aware_datetime, 'CET')
        expected = datetime(2024, 6, 10, 13, 0, 0, tzinfo=self.test_timezones['CET'])
        self.assertEqual(cet_time, expected)

    def test_naive_to_utc(self):
        converted = naive_to_utc(self.naive_datetime)
        self.assertEqual(converted.tzinfo.utcoffset(), timedelta(0))

    # ---------- DATE ARITHMETIC ----------
    def test_add_days(self):
        result = add_days(self.aware_datetime, 5)
        expected = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(result, expected)

    def test_subtract_days(self):
        result = subtract_days(self.aware_datetime, 5)
        expected = datetime(2024, 6, 5, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(result, expected)

    def test_add_hours_across_day_boundary(self):
        result = add_hours(self.aware_datetime.replace(hour=23), 3)
        expected = datetime(2024, 6, 11, 2, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(result, expected)

    # ---------- STRING REPRESENTATION ----------
    def test_str_representation(self):
        self.assertEqual(str(self.aware_datetime), '2024-06-10 12:00:00+00:00')

    def test_repr_string(self):
        self.assertIn('datetime.datetime', repr(self.aware_datetime))

    # ---------- SERIALIZATION/DESERIALIZATION ----------
    def test_json_dump_load_roundtrip(self):
        import json
        from datetime import dumps, loads
        json_str = dumps([self.aware_datetime])
        parsed = loads(json_str)
        self.assertEqual(parsed[0], self.aware_datetime)

    # ---------- ADDITIONAL EDGE CASES ----------
    def test_doy_at_edges(self):
        self.assertEqual(get_doy(datetime(2024, 1, 1, tzinfo=timezone.utc)), 1)
        self.assertEqual(get_doy(datetime(2024, 12, 31, tzinfo=timezone.utc)), 366)

    def test_invalid_timezone_raises(self):
        with self.assertRaises(ValueError):
            datetime.now(timezone(timedelta(hours=13)))

if __name__ == '__main__':
    unittest.main()