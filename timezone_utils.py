import datetime
from datetime import timezone, timedelta
test from zoneinfo import ZoneInfo

class TimezoneUtils:
    """
    A collection of utilities for working with timezone-aware datetime objects.
    """

    @staticmethod
    def localize(dt, tz='UTC'):
        """
        Localize a naive datetime object to a specific timezone.
        
        Args:
            dt: Naive datetime object to localize
            tz: Target timezone (string or ZoneInfo object)
        
        Returns:
            Timezone-aware datetime object
        """
        if isinstance(tz, str):
            tz = ZoneInfo(tz)
        
        return dt.replace(tzinfo=tz)

    @staticmethod
    def convert(dt, from_tz='UTC', to_tz='UTC'):
        """
        Convert a datetime object between timezones.
        
        Args:
            dt: Datetime object (can be naive or aware)
            from_tz: Original timezone (string or ZoneInfo object)
            to_tz: Target timezone (string or ZoneInfo object)
        
        Returns:
            Converted datetime object
        """
        if not dt.tzinfo:
            dt = TimezoneUtils.localize(dt, from_tz)
        
        if isinstance(tz, str):
            to_tz = ZoneInfo(to_tz)
        
        return dt.astimezone(to_tz)

    @staticmethod
    def now(tz='UTC'):
        """
        Get the current time for a specific timezone.
        
        Args:
            tz: Target timezone (string or ZoneInfo object)
        
        Returns:
            Current datetime in the specified timezone
        """
        if isinstance(tz, str):
            tz = ZoneInfo(tz)
        
        return datetime.datetime.now(tz)

    @staticmethod
    def utcnow():
        """
        Get the current UTC time.
        
        Returns:
            Current UTC datetime
        """
        return datetime.datetime.utcnow()

    @staticmethod
    def is_dst(dt, tz='UTC'):
        """
        Check if a datetime object is in Daylight Saving Time.
        
        Args:
            dt: Datetime object
            tz: Timezone (string or ZoneInfo object)
        
        Returns:
            True if DST is in effect, False otherwise
        """
        aware_dt = TimezoneUtils.localize(dt, tz)
        return aware_dt.dst() != timedelta(0)

    @staticmethod
    def all_timezones():
        """
        List all known timezones.
        
        Returns:
            Dictionary of all timezones
        """
        import zoneinfo
        return dict(zoneinfo.available_timezones())

if __name__ == '__main__':
    # Example usage
    from pprint import pprint

    print('='*50)
    print("Timezone Utils - Examples")
    print('-'*50)

    # Create some sample datetimes
    naive_dt = datetime.datetime(2023, 11, 5, 12, 0, 0)
    aware_utc = TimezoneUtils.localize(naive_dt, 'UTC')
    aware_pacific = TimezoneUtils.localize(naive_dt, 'US/Pacific')

    print(f"Naive datetime: {naive_dt}")
    print(f"Localized (UTC): {aware_utc}")
    print(f"Localized (US/Pacific): {aware_pacific}")

    print('\n'+'-'*50)

    # Conversion examples
    dt_paris = TimezoneUtils.now('Europe/Paris')
    dt_new_york = TimezoneUtils.convert(dt_paris, 'Europe/Paris', 'US/Eastern')

    print(f"Current time in Paris: {dt_paris}")
    print(f"Converted to New York: {dt_new_york}")

    print('\n'+'-'*50)

    # DST check
    test_date = datetime.datetime(2023, 11, 5, tzinfo=ZoneInfo('US/Eastern'))
    print(f"Is DST in effect (US/Eastern on 2023-11-05)? {TimezoneUtils.is_dst(test_date)}")

    test_date = datetime.datetime(2023, 7, 1, tzinfo=ZoneInfo('US/Eastern'))
    print(f"Is DST in effect (US/Eastern on 2023-07-01)? {TimezoneUtils.is_dst(test_date)}")