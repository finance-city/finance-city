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
        """KRX 마켓의 기본 설정을 생성합니다 (장중/장외 통합)."""
        
        # 국내 주식 통합 세션(KRX+NXT): 08:00-20:00 (정규 + 시간외)
        unified_session = MarketSession(
            start_time="08:00",
            end_time="20:00",
            timezone="Asia/Seoul"
        )
        
        # 필드 설정
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
            tr_id="H0UNCNT0",  # 통합 API (장중 + 장외)
            session=unified_session,
            fields=fields,
            exchange_codes={
                "KOSPI": "J",
                "KOSDAQ": "Q"
            }
        )
    
    def __init__(self):
        """KRX 마켓 프로바이더를 초기화합니다."""
        config = self.create_default_config()
        super().__init__(config)
    
    def parse_stock_code(self, code: str) -> Optional[str]:
        """종목 코드를 파싱하고 검증합니다.
        
        국내 주식 종목 코드는 일반적으로 6자리 숫자입니다 (예: 삼성전자의 경우 005930).
        
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
            is_night_trading: 국내에서는 사용되지 않음
            
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
