"""
미국 주식 시장 프로바이더 구현.

이 모듈은 NASDAQ, NYSE, AMEX를 포함한 미국 주식 시장을 위한
마켓별 기능을 제공합니다.

WebSocket 데이터 발생 시간 (KST 기준):
- 한국투자증권 미국장전거래: 10:00 ~ 16:00
- 미국시장 (프리+정규+애프터): 18:00 ~ 07:00
  * 프리마켓: 18:00 ~ 23:30
  * 정규장: 23:30 ~ 06:00 (EST 기준, EDT는 -1시간)
  * 애프터마켓: 06:00 ~ 07:00
  
주의: 장전거래는 현재 중단 상태인 경우가 많아 대부분의 체결 데이터는 18:00 이후 발생
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
                # D prefix: 한국투자증권 미국장전거래 시간 (10:00-16:00 KST)
                "NASDAQ_PREMARKET_SESSION": "NAS",
                "NYSE_PREMARKET_SESSION": "NYS", 
                "AMEX_PREMARKET_SESSION": "AMS",
                # R prefix: 실제 미국시장 시간 (18:00-07:00 KST) 
                "NASDAQ_US_HOURS": "BAQ",
                "NYSE_US_HOURS": "BAY",
                "AMEX_US_HOURS": "BAA"
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
    
    def format_stock_code(self, code: str, use_premarket_session: bool = False) -> str:
        """API 요청을 위한 미국 주식 코드를 포맷합니다.
        
        WebSocket 운영시간에 따라 prefix를 선택합니다:
        - D prefix: 한국투자증권 미국장전거래 시간 (10:00-16:00 KST)
        - R prefix: 실제 미국시장 시간 (18:00-07:00 KST, 프리+정규+애프터)
        
        Args:
            code: 포맷할 주식 심볼
            use_premarket_session: 장전거래 세션 사용 여부 (10:00-16:00 KST)
            
        Returns:
            KIS API용 포맷된 코드 (예: DNASAAPL, RBAYMSFT)
        """
        symbol = self.parse_stock_code(code)
        if symbol is None:
            raise ValueError(f"Invalid US stock code: {code}")
        
        # 거래소 결정 (명시되지 않은 경우 NASDAQ으로 가정)
        exchange = self._detect_exchange(symbol)
        
        if use_premarket_session:
            # 한국투자증권 미국장전거래 시간 (10:00-16:00 KST)
            prefix = "D"
            exchange_code = self._get_premarket_session_exchange_code(exchange)
        else:
            # 실제 미국시장 시간 (18:00-07:00 KST)
            prefix = "R"
            exchange_code = self._get_us_hours_exchange_code(exchange)
        
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
    
    def _get_premarket_session_exchange_code(self, exchange: str) -> str:
        """한국투자증권 장전거래(10:00-16:00 KST) 거래소 코드를 가져옵니다."""
        premarket_session_codes = {
            "NASDAQ": "NAS",
            "NYSE": "NYS", 
            "AMEX": "AMS"
        }
        return premarket_session_codes.get(exchange, "NAS")
    
    def _get_us_hours_exchange_code(self, exchange: str) -> str:
        """실제 미국시장 시간(18:00-07:00 KST) 거래소 코드를 가져옵니다."""
        us_hours_codes = {
            "NASDAQ": "BAQ",
            "NYSE": "BAY",
            "AMEX": "BAA"
        }
        return us_hours_codes.get(exchange, "BAQ")
    
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
    
    def is_in_websocket_operational_hours(self, current_time: Optional[datetime] = None) -> bool:
        """WebSocket 데이터가 발생하는 시간대인지 확인합니다.
        
        WebSocket 운영시각 (KST 기준):
        - 한국투자증권 미국장전거래: 10:00 ~ 16:00
        - 실제 미국시장: 18:00 ~ 07:00 (다음날)
        
        Args:
            current_time: 확인할 시간 (None이면 현재 시각)
            
        Returns:
            WebSocket 운영시간대이면 True, 아니면 False (채널 닫힘)
        """
        if current_time is None:
            current_time = datetime.now()
        
        hour = current_time.hour
        
        # 장전거래 시간 (10:00-16:00 KST)
        is_premarket_session = 10 <= hour < 16
        
        # 미국시장 시간 (18:00-07:00 KST, 자정 넘어감)
        is_us_market_hours = hour >= 18 or hour < 7
        
        return is_premarket_session or is_us_market_hours
    
    def should_use_premarket_session(self, current_time: Optional[datetime] = None) -> bool:
        """한국투자증권 장전거래 시간대인지 확인합니다.
        
        장전거래 시간: 10:00 ~ 16:00 KST (D prefix 사용)
        그 외 시간: 18:00 ~ 07:00 KST (R prefix 사용)
        
        주의: 16:00-18:00, 07:00-10:00는 WebSocket 채널이 닫혀있는 시간
        
        Args:
            current_time: 확인할 시간 (None이면 현재 시각)
            
        Returns:
            장전거래 시간대이면 True, 미국시장 시간대이면 False
        """
        if current_time is None:
            current_time = datetime.now()
        
        hour = current_time.hour
        
        # 장전거래 시간대 (10:00-16:00)
        return 10 <= hour < 16
    
    def get_trading_session_info(self, current_time: Optional[datetime] = None) -> dict:
        """상세한 거래 세션 정보를 가져옵니다.
        
        Returns:
            세션 정보 딕셔너리:
            - is_operational: WebSocket 운영시간 여부
            - use_premarket_session: 장전거래 세션 사용 여부
            - session_type: 'premarket_session' (10-16시) 또는 'us_hours' (18-07시)
            - current_hour: 현재 시각
        """
        if current_time is None:
            current_time = datetime.now()
        
        is_operational = self.is_in_websocket_operational_hours(current_time)
        use_premarket = self.should_use_premarket_session(current_time)
        
        if use_premarket:
            session_type = "premarket_session"
        elif is_operational:
            session_type = "us_hours"
        else:
            session_type = "closed"
        
        return {
            "is_operational": is_operational,
            "use_premarket_session": use_premarket,
            "session_type": session_type,
            "current_hour": current_time.hour
        }
    
    def format_stock_code_with_session(self, code: str, current_time: Optional[datetime] = None) -> str:
        """현재 거래 세션을 기반으로 주식 코드를 포맷합니다.
        
        Args:
            code: 포맷할 주식 심볼
            current_time: 확인할 시간 (None이면 현재 시각)
            
        Returns:
            포맷된 주식 코드
            
        Raises:
            ValueError: WebSocket 채널이 닫혀있는 시간대인 경우
        """
        session_info = self.get_trading_session_info(current_time)
        
        # WebSocket 운영시간 확인
        if not session_info["is_operational"]:
            raise ValueError(
                f"WebSocket 채널이 닫혀있는 시간대입니다 (현재: {session_info['current_hour']}시). "
                f"운영시간: 10:00-16:00 또는 18:00-07:00 (KST)"
            )
        
        use_premarket = session_info["use_premarket_session"]
        return self.format_stock_code(code, use_premarket_session=use_premarket)
    
    def parse_kis_formatted_code(self, kis_code: str) -> Optional[Tuple[str, str, str]]:
        """KIS 포맷 코드를 구성 요소로 파싱합니다.
        
        Returns:
            (심볼, 거래소, 세션_타입) 튜플 또는 유효하지 않으면 None
            세션_타입: 'premarket_session' 또는 'us_hours'
        """
        if not kis_code:
            return None
        
        match = re.match(r'^([DR])([A-Z]{3})([A-Z]+)$', kis_code.strip().upper())
        if not match:
            return None
        
        session_prefix, exchange_code, symbol = match.groups()
        session_type = "premarket_session" if session_prefix == "D" else "us_hours"
        
        # 거래소명 역방향 조회
        exchange_name = self._reverse_lookup_exchange(exchange_code, session_type)
        
        return symbol, exchange_name, session_type
    
    def _reverse_lookup_exchange(self, exchange_code: str, session_type: str) -> str:
        """거래소 코드에서 거래소명을 역방향 조회합니다."""
        if session_type == "premarket_session":
            code_map = {"NAS": "NASDAQ", "NYS": "NYSE", "AMS": "AMEX"}
        else:  # us_hours
            code_map = {"BAQ": "NASDAQ", "BAY": "NYSE", "BAA": "AMEX"}
        
        return code_map.get(exchange_code, "UNKNOWN")
