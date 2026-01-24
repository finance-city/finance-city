"""
KRX (한국거래소) 마켓 프로바이더 구현.

이 모듈은 KOSPI와 KOSDAQ를 포함한 한국 주식 시장을 위한
마켓별 기능을 제공합니다.
"""

from datetime import time
from typing import Optional

from core import MarketConfig, MarketSession, FieldConfig
from .base import BaseMarketProvider


class KRXMarketProvider(BaseMarketProvider):
    """한국거래소(KRX)용 마켓 프로바이더."""
    
    @classmethod
    def create_default_config(cls) -> MarketConfig:
        """KRX 마켓의 기본 설정을 생성합니다."""
        
        # KRX 정규 세션: 09:00-15:30
        regular_session = MarketSession(
            start_time="09:00",
            end_time="15:30",
            timezone="Asia/Seoul"
        )
        
        # KRX 필드 설정
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
                "prev_close": "11"
            },
            required_fields=[
                "stock_code", "stock_name", "current_price", 
                "change", "change_rate", "volume"
            ],
            optional_fields=[
                "ask_price", "bid_price", "high_price", 
                "low_price", "open_price", "prev_close"
            ]
        )
        
        return MarketConfig(
            name="KRX",
            tr_id="H0STCNT0",  # 정규 거래 시간
            session=regular_session,
            fields=fields,
            exchange_codes={
                "KOSPI": "J",
                "KOSDAQ": "Q"
            }
        )
    
    @classmethod
    def create_after_hours_config(cls) -> MarketConfig:
        """KRX 마켓의 시간외 거래 설정을 생성합니다."""
        
        # KRX 시간외 거래 세션: 16:00-18:00
        after_session = MarketSession(
            start_time="16:00",
            end_time="18:00", 
            timezone="Asia/Seoul"
        )
        
        # 정규 세션과 동일한 필드 설정
        fields = cls.create_default_config().fields
        
        return MarketConfig(
            name="KRX_AFTER",
            tr_id="H0NXCNT0",  # 시간외 거래
            session=after_session,
            fields=fields,
            exchange_codes={
                "KOSPI": "J",
                "KOSDAQ": "Q"
            }
        )
    
    def __init__(self, use_after_hours: bool = False):
        """KRX 마켓 프로바이더를 초기화합니다.
        
        Args:
            use_after_hours: 시간외 거래 세션 설정을 사용할지 여부
        """
        if use_after_hours:
            config = self.create_after_hours_config()
        else:
            config = self.create_default_config()
            
        super().__init__(config)
        self._use_after_hours = use_after_hours
        
    def is_after_hours_mode(self) -> bool:
        """이 프로바이더가 시간외 거래 모드인지 확인합니다."""
        return self._use_after_hours
    
    def parse_stock_code(self, code: str) -> Optional[str]:
        """KRX 종목 코드를 파싱하고 검증합니다.
        
        KRX 코드는 일반적으로 6자리 숫자입니다 (예: 삼성전자의 경우 005930).
        
        Args:
            code: 파싱할 종목 코드
            
        Returns:
            유효한 경우 정리된 종목 코드, 그렇지 않으면 None
        """
        if not code:
            return None
        
        # 코드 정리
        cleaned_code = code.strip()
        
        # KRX 종목 코드는 6자리 숫자
        if self.validate_stock_code_format(cleaned_code, r'^\d{6}$'):
            return cleaned_code
        
        return None
    
    def format_stock_code(self, code: str, is_night_trading: bool = False) -> str:
        """API 요청을 위한 KRX 종목 코드를 포맷합니다.
        
        KRX의 경우 코드는 수정 없이 그대로 사용됩니다.
        
        Args:
            code: 포맷할 종목 코드
            is_night_trading: KRX에서는 사용되지 않음
            
        Returns:
            포맷된 종목 코드
        """
        parsed_code = self.parse_stock_code(code)
        if parsed_code is None:
            raise ValueError(f"Invalid KRX stock code: {code}")
        
        return parsed_code
    
    def is_kospi_stock(self, code: str) -> bool:
        """주식이 KOSPI 주식인지 확인합니다.
        
        이것은 코드 범위에 기반한 간단한 휴리스틱입니다.
        실제 거래소 상장 정보를 바탕으로 더 정교한 로직을
        구현할 수 있습니다.
        """
        if not self.parse_stock_code(code):
            return False
        
        # 간단한 휴리스틱: KOSPI 주식은 보통 0-3으로 시작
        # KOSDAQ 주식은 보통 4-8로 시작
        first_digit = int(code[0])
        return first_digit <= 3
    
    def is_kosdaq_stock(self, code: str) -> bool:
        """주식이 KOSDAQ 주식인지 확인합니다."""
        if not self.parse_stock_code(code):
            return False
        
        return not self.is_kospi_stock(code)
    
    def get_exchange_for_stock(self, code: str) -> Optional[str]:
        """주어진 종목 코드에 대한 거래소 이름을 가져옵니다."""
        if self.is_kospi_stock(code):
            return "KOSPI"
        elif self.is_kosdaq_stock(code):
            return "KOSDAQ"
        return None
    
    def supports_after_hours(self) -> bool:
        """이 프로바이더가 시간외 거래를 지원하는지 확인합니다."""
        return True
    
    def switch_to_after_hours(self) -> None:
        """시간외 거래 설정으로 전환합니다."""
        if not self._use_after_hours:
            self._config = self.create_after_hours_config()
            self._tr_id = self._config.tr_id
            self._session = self._config.session
            self._use_after_hours = True
    
    def switch_to_regular_hours(self) -> None:
        """정규 거래 시간 설정으로 전환합니다."""
        if self._use_after_hours:
            self._config = self.create_default_config()
            self._tr_id = self._config.tr_id
            self._session = self._config.session
            self._use_after_hours = False
