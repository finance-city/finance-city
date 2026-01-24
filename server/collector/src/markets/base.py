"""
기본 마켓 프로바이더 구현.

이 모듈은 특정 마켓 구현에 의해 확장될 수 있는
마켓 프로바이더의 기본 구현을 제공합니다.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List
import re

from core import IMarketProvider, MarketSession, FieldConfig, MarketConfig


class BaseMarketProvider(IMarketProvider, ABC):
    """마켓 프로바이더의 기본 구현."""
    
    def __init__(self, config: MarketConfig):
        self._config = config
        self._market_name = config.name
        self._tr_id = config.tr_id
        self._session = config.session
        self._fields = config.fields
        self._exchange_codes = config.exchange_codes
    
    def get_market_name(self) -> str:
        """마켓 이름을 가져옵니다."""
        return self._market_name
    
    def get_tr_id(self) -> str:
        """이 마켓의 TR ID를 가져옵니다."""
        return self._tr_id
    
    def get_session_config(self) -> MarketSession:
        """마켓 세션 설정을 가져옵니다."""
        return self._session
    
    def get_field_config(self) -> FieldConfig:
        """이 마켓의 필드 설정을 가져옵니다."""
        return self._fields
    
    def is_market_open(self, current_time: datetime) -> bool:
        """마켓이 현재 열려있는지 확인합니다."""
        return self._config.is_market_open(current_time)
    
    @abstractmethod
    def parse_stock_code(self, code: str) -> Optional[str]:
        """이 마켓의 종목 코드를 파싱하고 검증합니다."""
        pass
    
    @abstractmethod
    def format_stock_code(self, code: str, is_night_trading: bool = False) -> str:
        """API 요청을 위한 종목 코드를 포맷합니다."""
        pass
    
    def validate_stock_code_format(self, code: str, pattern: str) -> bool:
        """정규식 패턴에 대해 종목 코드를 검증합니다."""
        try:
            return bool(re.match(pattern, code.strip()))
        except (TypeError, AttributeError):
            return False
    
    def get_exchange_code(self, exchange_name: str) -> Optional[str]:
        """주어진 거래소 이름에 대한 거래소 코드를 가져옵니다."""
        return self._exchange_codes.get(exchange_name)
    
    def get_supported_exchanges(self) -> List[str]:
        """이 마켓에서 지원되는 거래소 목록을 가져옵니다."""
        return list(self._exchange_codes.keys())
    
    def is_trading_hours(self, current_time: Optional[datetime] = None) -> bool:
        """현재 시간이 거래 시간 내에 있는지 확인합니다."""
        if current_time is None:
            current_time = datetime.now()
        return self._session.is_session_time(current_time.time())
    
    def get_market_config(self) -> MarketConfig:
        """완전한 마켓 설정을 가져옵니다."""
        return self._config
