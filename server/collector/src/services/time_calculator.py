"""
마켓 시간 계산을 위한 시간 계산기 서비스.

이 서비스는 DST 계산, 마켓 시간 검증, 시간대 변환을 포함한
시간 관련 유틸리티를 제공합니다.
"""

from datetime import datetime, time, timedelta
from typing import Optional, Dict, Any
import pytz

from core import ITimeCalculator


class TimeCalculatorService(ITimeCalculator):
    """거래 시스템에서의 시간 관련 계산을 위한 서비스."""
    
    def __init__(self):
        """시간대 데이터로 시간 계산기를 초기화합니다."""
        self._timezone_map = {
            "KRX": "Asia/Seoul",
            "US": "America/New_York", 
            "UTC": "UTC"
        }
        
        self._market_hours = {
            "KRX": {
                "regular": {"start": "09:00", "end": "15:30"},
                "after_hours": {"start": "16:00", "end": "18:00"}
            },
            "US": {
                "regular": {"start": "09:30", "end": "16:00"}  # 미국 동부 시간
            }
        }
    
    def is_dst_active(self, dt: datetime) -> bool:
        """주어진 datetime에 대해 일광절약시간이 활성화되어 있는지 확인합니다.
        
        Args:
            dt: 확인할 Datetime (미국 동부 시간대로 가정)
            
        Returns:
            DST가 활성화되어 있으면 True, 그렇지 않으면 False
        """
        try:
            # 미국 동부 시간대 가져오기
            eastern = pytz.timezone('America/New_York')
            
            # dt가 naive하면 동부 시간으로 가정
            if dt.tzinfo is None:
                dt_eastern = eastern.localize(dt)
            else:
                dt_eastern = dt.astimezone(eastern)
            
            # DST가 활성화되어 있는지 확인
            return bool(dt_eastern.dst())
            
        except Exception:
            # DST에 대한 폴백 계산 (3월 둘째 일요일부터 11월 첫째 일요일까지)
            year = dt.year
            
            # DST는 3월 둘째 일요일에 시작
            march_1 = datetime(year, 3, 1)
            days_to_second_sunday = 7 + (6 - march_1.weekday()) % 7
            dst_start = march_1.replace(day=days_to_second_sunday + 7)
            
            # DST는 11월 첫째 일요일에 종료
            november_1 = datetime(year, 11, 1)
            days_to_first_sunday = (6 - november_1.weekday()) % 7
            dst_end = november_1.replace(day=1 + days_to_first_sunday)
            
            return dst_start <= dt < dst_end
    
    def get_market_time(self, market: str, dt: Optional[datetime] = None) -> datetime:
        """마켓 시간대에서 현재 또는 지정된 시간을 가져옵니다.
        
        Args:
            market: 마켓 식별자 (KRX, US 등)
            dt: 변환할 특정 datetime (기본적으로 현재 시간)
            
        Returns:
            마켓 시간대의 Datetime
        """
        if dt is None:
            dt = datetime.now(pytz.UTC)
        
        timezone_name = self._timezone_map.get(market, "UTC")
        
        try:
            target_tz = pytz.timezone(timezone_name)
            
            # 입력 datetime이 naive하면 UTC로 가정
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            
            return dt.astimezone(target_tz)
            
        except Exception as e:
            print(f"Warning: Failed to convert timezone for {market}: {e}")
            return dt
    
    def is_trading_hours(self, market: str, dt: Optional[datetime] = None) -> bool:
        """주어진 시간이 마켓의 거래 시간 내에 있는지 확인합니다.
        
        Args:
            market: 마켓 식별자
            dt: 확인할 Datetime (기본적으로 현재 시간)
            
        Returns:
            거래 시간 내이면 True, 그렇지 않으면 False
        """
        if dt is None:
            dt = datetime.now()
        
        # 마켓 시간대로 변환
        market_time = self.get_market_time(market, dt)
        current_time = market_time.time()
        
        # 마켓 시간 설정 가져오기
        market_config = self._market_hours.get(market, {})
        
        if market == "US":
            # 미국 마켓 특별 처리 (KIS API를 통한 24시간 가용성)
            # 하지만 필요시 실제 미국 마켓 시간도 확인 가능
            regular_hours = market_config.get("regular", {})
            if regular_hours:
                start_time = time.fromisoformat(regular_hours["start"])
                end_time = time.fromisoformat(regular_hours["end"])
                return start_time <= current_time <= end_time
            else:
                # 기본값: 미국 마켓은 항상 가능
                return True
        
        elif market == "KRX":
            # 정규 및 시간외 거래 세션 모두 확인
            regular_hours = market_config.get("regular", {})
            after_hours = market_config.get("after_hours", {})
            
            # 정규 시간 확인 (09:00-15:30)
            if regular_hours:
                start_time = time.fromisoformat(regular_hours["start"])
                end_time = time.fromisoformat(regular_hours["end"])
                if start_time <= current_time <= end_time:
                    return True
            
            # 시간외 거래 확인 (16:00-18:00)
            if after_hours:
                start_time = time.fromisoformat(after_hours["start"])
                end_time = time.fromisoformat(after_hours["end"])
                if start_time <= current_time <= end_time:
                    return True
            
            return False
        
        # 기본값: 설정되지 않은 경우 마켓이 항상 열려있다고 가정
        return True
    
    def get_us_trading_session_type(self, dt: Optional[datetime] = None) -> str:
        """한국 관점에서 미국 거래 세션 타입을 결정합니다.
        
        Args:
            dt: 확인할 Datetime (기본적으로 현재 시간)
            
        Returns:
            "day" 또는 "night" 거래 세션
        """
        if dt is None:
            dt = datetime.now()
        
        # 세션 결정을 위해 한국 시간으로 변환
        korean_time = self.get_market_time("KRX", dt)
        hour = korean_time.hour
        
        # DST가 활성화되어 있는지 확인
        is_dst = self.is_dst_active(dt)
        
        if is_dst:
            # DST 기간: 미국 마켓은 22:30-05:00 (한국 시간)에 열림
            us_open = (hour >= 22 and korean_time.minute >= 30) or (0 <= hour <= 5)
        else:
            # 표준시 기간: 미국 마켓은 23:30-06:00 (한국 시간)에 열림
            us_open = (hour >= 23 and korean_time.minute >= 30) or (0 <= hour <= 6)
        
        return "day" if us_open else "night"
    
    def calculate_market_overlap(self, market1: str, market2: str, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """두 마켓 간의 거래 시간 겹침을 계산합니다.
        
        Args:
            market1: 첫 번째 마켓 식별자
            market2: 두 번째 마켓 식별자
            dt: 기준 datetime (기본적으로 현재 시간)
            
        Returns:
            겹침 정보를 포함하는 딕셔너리
        """
        if dt is None:
            dt = datetime.now()
        
        market1_open = self.is_trading_hours(market1, dt)
        market2_open = self.is_trading_hours(market2, dt)
        
        return {
            "market1": market1,
            "market2": market2,
            "market1_open": market1_open,
            "market2_open": market2_open,
            "both_open": market1_open and market2_open,
            "either_open": market1_open or market2_open,
            "reference_time": dt.isoformat()
        }
    
    def get_next_market_open(self, market: str, dt: Optional[datetime] = None) -> Optional[datetime]:
        """다음 마켓 개장 시간을 가져옵니다.
        
        Args:
            market: 마켓 식별자
            dt: 기준 datetime (기본적으로 현재 시간)
            
        Returns:
            다음 마켓 개장 datetime, 결정할 수 없으면 None
        """
        if dt is None:
            dt = datetime.now()
        
        market_config = self._market_hours.get(market, {})
        if not market_config:
            return None
        
        market_time = self.get_market_time(market, dt)
        current_date = market_time.date()
        
        # 정규 거래 시간 가져오기
        regular_hours = market_config.get("regular", {})
        if not regular_hours:
            return None
        
        # 먼저 오늘 시도
        try:
            start_time_str = regular_hours["start"]
            opening_time = datetime.combine(
                current_date,
                time.fromisoformat(start_time_str)
            )
            
            # 마켓 시간대로 변환
            timezone_name = self._timezone_map.get(market, "UTC")
            market_tz = pytz.timezone(timezone_name)
            opening_time = market_tz.localize(opening_time)
            
            # 개장 시간이 오늘 미래 시간이면 반환
            if opening_time > market_time:
                return opening_time
            
            # 그렇지 않으면 내일 개장 시간 반환
            tomorrow = current_date + timedelta(days=1)
            opening_time = datetime.combine(tomorrow, time.fromisoformat(start_time_str))
            opening_time = market_tz.localize(opening_time)
            
            return opening_time
            
        except Exception as e:
            print(f"Error calculating next market open for {market}: {e}")
            return None
    
    def format_market_time_info(self, market: str, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """마켓에 대한 포맷된 시간 정보를 가져옵니다.
        
        Args:
            market: 마켓 식별자
            dt: 기준 datetime (기본적으로 현재 시간)
            
        Returns:
            포맷된 시간 정보를 포함하는 딕셔너리
        """
        if dt is None:
            dt = datetime.now()
        
        market_time = self.get_market_time(market, dt)
        is_open = self.is_trading_hours(market, dt)
        next_open = self.get_next_market_open(market, dt)
        
        info = {
            "market": market,
            "current_time": market_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "is_open": is_open,
            "timezone": self._timezone_map.get(market, "Unknown")
        }
        
        if next_open:
            info["next_open"] = next_open.strftime("%Y-%m-%d %H:%M:%S %Z")
        
        if market == "US":
            info["is_dst"] = self.is_dst_active(dt)
            info["session_type"] = self.get_us_trading_session_type(dt)
        
        return info
