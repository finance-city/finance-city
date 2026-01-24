"""
미국 주식 시장 프로바이더 구현.

이 모듈은 NASDAQ, NYSE, AMEX를 포함한 미국 주식 시장을 위한
마켓별 기능을 제공합니다.
"""

from datetime import datetime, time
from typing import Optional, Tuple
import re

from core import MarketConfig, MarketSession, FieldConfig
from .base import BaseMarketProvider


class USMarketProvider(BaseMarketProvider):
    """미국 주식 시장(NASDAQ, NYSE, AMEX)용 마켓 프로바이더."""
    
    @classmethod
    def create_default_config(cls) -> MarketConfig:
        """미국 마켓의 기본 설정을 생성합니다."""
        
        # 미국 세션: 24시간 (KIS API에서 처리)
        session = MarketSession(
            start_time="00:00",
            end_time="23:59",
            timezone="America/New_York"
        )
        
        # 미국 마켓 필드 설정  
        fields = FieldConfig(
            fields={
                "stock_code": "0",
                "stock_name": "1",
                "current_price": "2", 
                "change": "3",
                "change_rate": "4",
                "volume": "5",
                "ask_price": "6",
                "bid_price": "7",
                "high_price": "8",
                "low_price": "9", 
                "open_price": "10",
                "prev_close": "11",
                "currency": "12"
            },
            required_fields=[
                "stock_code", "stock_name", "current_price",
                "change", "change_rate", "volume"
            ],
            optional_fields=[
                "ask_price", "bid_price", "high_price",
                "low_price", "open_price", "prev_close", "currency"
            ]
        )
        
        return MarketConfig(
            name="US",
            tr_id="HDFSCNT0",  # 미국 마켓 실시간 데이터
            session=session,
            fields=fields,
            exchange_codes={
                # 야간거래 코드 (한국 마켓 시간)
                "NASDAQ_NIGHT": "NAS",
                "NYSE_NIGHT": "NYS", 
                "AMEX_NIGHT": "AMS",
                # 주간거래 코드 (미국 마켓 시간) 
                "NASDAQ_DAY": "BAQ",
                "NYSE_DAY": "BAY",
                "AMEX_DAY": "BAA"
            }
        )
    
    def __init__(self):
        """미국 마켓 프로바이더를 초기화합니다."""
        super().__init__(self.create_default_config())
    
    def parse_stock_code(self, code: str) -> Optional[str]:
        """미국 주식 코드를 파싱하고 검증합니다.
        
        미국 주식 코드의 형태:
        - 일반 심볼 (AAPL, MSFT, GOOGL)
        - KIS API 포맷 코드 (DNASAAPL, RBAYMSFT)
        
        Args:
            code: 파싱할 주식 코드
            
        Returns:
            유효한 경우 정제된 심볼, 그렇지 않으면 None
        """
        if not code:
            return None
        
        cleaned_code = code.strip().upper()
        
        # KIS 포맷 코드인지 확인 (DNASAAPL, RBAYMSFT)
        kis_match = re.match(r'^[DR][A-Z]{3}([A-Z]+)$', cleaned_code)
        if kis_match:
            return kis_match.group(1)  # 심볼 부분 추출
        
        # 일반 심볼인지 확인 (1-5자리 대문자)
        if self.validate_stock_code_format(cleaned_code, r'^[A-Z]{1,5}$'):
            return cleaned_code
        
        return None
    
    def format_stock_code(self, code: str, is_night_trading: bool = False) -> str:
        """API 요청을 위한 미국 주식 코드를 포맷합니다.
        
        거래 세션과 DST 상태에 따라 코드를 포맷합니다.
        
        Args:
            code: 포맷할 주식 심볼
            is_night_trading: 야간거래 세션 여부
            
        Returns:
            KIS API용 포맷된 코드 (예: DNASAAPL, RBAYMSFT)
        """
        symbol = self.parse_stock_code(code)
        if symbol is None:
            raise ValueError(f"Invalid US stock code: {code}")
        
        # 거래소 결정 (명시되지 않은 경우 NASDAQ으로 가정)
        exchange = self._detect_exchange(symbol)
        
        if is_night_trading:
            # 한국 마켓 시간 (야간거래)
            prefix = "D"  # 주간거래 접두사
            exchange_code = self._get_night_exchange_code(exchange)
        else:
            # 미국 마켓 시간 (한국 관점에서의 주간거래)
            prefix = "R"  # 실시간 접두사
            exchange_code = self._get_day_exchange_code(exchange)
        
        return f"{prefix}{exchange_code}{symbol}"
    
    def _detect_exchange(self, symbol: str) -> str:
        """주어진 심볼의 가능한 거래소를 감지합니다.
        
        이것은 휴리스틱 접근법입니다. 프로덕션 시스템에서는
        적절한 심볼-거래소 매핑을 유지해야 합니다.
        """
        # 잘 알려진 NASDAQ 주식들
        nasdaq_stocks = {
            'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'TSLA', 
            'META', 'NVDA', 'NFLX', 'ADBE', 'INTC', 'AMD'
        }
        
        # 잘 알려진 NYSE 주식들  
        nyse_stocks = {
            'BRK.A', 'BRK.B', 'JPM', 'JNJ', 'V', 'PG', 'UNH',
            'HD', 'MA', 'DIS', 'BAC', 'ADBE', 'CRM', 'NFLX'
        }
        
        if symbol in nasdaq_stocks:
            return "NASDAQ"
        elif symbol in nyse_stocks:
            return "NYSE"
        else:
            # 알 수 없는 심볼은 기본적으로 NASDAQ
            return "NASDAQ"
    
    def _get_night_exchange_code(self, exchange: str) -> str:
        """야간거래 거래소 코드를 가져옵니다."""
        night_codes = {
            "NASDAQ": "NAS",
            "NYSE": "NYS", 
            "AMEX": "AMS"
        }
        return night_codes.get(exchange, "NAS")
    
    def _get_day_exchange_code(self, exchange: str) -> str:
        """주간거래 거래소 코드를 가져옵니다."""
        day_codes = {
            "NASDAQ": "BAQ",
            "NYSE": "BAY",
            "AMEX": "BAA"
        }
        return day_codes.get(exchange, "BAQ")
    
    def is_dst_period(self, dt: Optional[datetime] = None) -> bool:
        """일광절약시간(DST)이 활성화되어 있는지 확인합니다.
        
        미국의 DST: 3월 둘째 일요일부터 11월 첫째 일요일까지
        """
        if dt is None:
            dt = datetime.now()
        
        year = dt.year
        
        # DST 시작일 계산 (3월 둘째 일요일)
        march_1 = datetime(year, 3, 1)
        days_to_second_sunday = 7 + (6 - march_1.weekday()) % 7
        dst_start = march_1.replace(day=days_to_second_sunday + 7)
        
        # DST 종료일 계산 (11월 첫째 일요일)
        november_1 = datetime(year, 11, 1)
        days_to_first_sunday = (6 - november_1.weekday()) % 7
        dst_end = november_1.replace(day=1 + days_to_first_sunday)
        
        return dst_start <= dt < dst_end
    
    def should_use_night_trading(self, current_time: Optional[datetime] = None) -> bool:
        if current_time is None:
            current_time = datetime.now()
        
        hour = current_time.hour
        minute = current_time.minute

        is_us_day_trading_hours = (
            (hour >= 10 and hour <= 15) or
            (hour == 16 and minute == 0)
        )
        
        return not is_us_day_trading_hours


    # def should_use_night_trading(self, current_time: Optional[datetime] = None) -> bool:
    #     """야간거래 코드를 사용해야 하는지 결정합니다.
        
    #     KIS API 시간대별 코드 사용법:
    #     - D prefix (야간거래): 프리마켓, 애프터마켓 시간 (미국 장외 시간)
    #     - R prefix (주간거래): 미국 정규장 시간 (09:30-16:00 ET)
        
    #     현재 시간이 미국 정규장 시간인지 확인하여 결정:
    #     - 정규장 시간 (09:30-16:00 ET) → R prefix (False 반환)
    #     - 정규장 외 시간 (프리마켓, 애프터마켓) → D prefix (True 반환)
    #     """
    #     if current_time is None:
    #         current_time = datetime.now()
        
    #     hour = current_time.hour
    #     minute = current_time.minute
        
    #     if self.is_dst_period(current_time):
    #         # EDT (써머타임): 미국 정규장 09:30-16:00 ET = 한국시간 22:30-05:00
    #         is_us_regular_hours = (
    #             (hour == 22 and minute >= 30) or  # 22:30~23:59
    #             (23 <= hour <= 23) or             # 23:00~23:59  
    #             (0 <= hour <= 4) or               # 00:00~04:59
    #             (hour == 5 and minute == 0)       # 05:00 (정확히 16:00 ET)
    #         )
    #     else:
    #         # EST (표준시): 미국 정규장 09:30-16:00 ET = 한국시간 23:30-06:00
    #         is_us_regular_hours = (
    #             (hour == 23 and minute >= 30) or  # 23:30~23:59
    #             (0 <= hour <= 5) or               # 00:00~05:59
    #             (hour == 6 and minute == 0)       # 06:00 (정확히 16:00 ET)
    #         )
        
    #     # 정규장 시간이 아니면 야간거래 코드(D) 사용
    #     # 정규장 시간이면 주간거래 코드(R) 사용
    #     return not is_us_regular_hours
    
    def get_trading_session_info(self, current_time: Optional[datetime] = None) -> dict:
        """상세한 거래 세션 정보를 가져옵니다."""
        if current_time is None:
            current_time = datetime.now()
        
        is_night = self.should_use_night_trading(current_time)
        is_dst = self.is_dst_period(current_time)
        
        return {
            "is_night_trading": is_night,
            "is_dst_active": is_dst,
            "session_type": "night" if is_night else "day",
            "timezone": "EST" if not is_dst else "EDT",
            "current_hour": current_time.hour
        }
    
    def format_stock_code_with_session(self, code: str, current_time: Optional[datetime] = None) -> str:
        """현재 거래 세션을 기반으로 주식 코드를 포맷합니다."""
        is_night = self.should_use_night_trading(current_time)
        return self.format_stock_code(code, is_night_trading=is_night)
    
    def parse_kis_formatted_code(self, kis_code: str) -> Optional[Tuple[str, str, str]]:
        """KIS 포맷 코드를 구성 요소로 파싱합니다.
        
        Returns:
            (심볼, 거래소, 세션_타입) 튜플 또는 유효하지 않으면 None
        """
        if not kis_code:
            return None
        
        match = re.match(r'^([DR])([A-Z]{3})([A-Z]+)$', kis_code.strip().upper())
        if not match:
            return None
        
        session_prefix, exchange_code, symbol = match.groups()
        session_type = "night" if session_prefix == "D" else "day"
        
        # 거래소명 역방향 조회
        exchange_name = self._reverse_lookup_exchange(exchange_code, session_type)
        
        return symbol, exchange_name, session_type
    
    def _reverse_lookup_exchange(self, exchange_code: str, session_type: str) -> str:
        """거래소 코드에서 거래소명을 역방향 조회합니다."""
        if session_type == "night":
            code_map = {"NAS": "NASDAQ", "NYS": "NYSE", "AMS": "AMEX"}
        else:
            code_map = {"BAQ": "NASDAQ", "BAY": "NYSE", "BAA": "AMEX"}
        
        return code_map.get(exchange_code, "UNKNOWN")
