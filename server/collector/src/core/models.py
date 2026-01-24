"""
금융 데이터 수집 시스템의 코어 데이터 모델.

이 모듈은 금융 데이터, 마켓 설정, 거래 정보를 나타내기 위해
시스템 전반에서 사용되는 코어 데이터 구조를 정의합니다.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Dict, List, Optional, Any, Union
from enum import Enum


class MarketType(Enum):
    """지원되는 마켓 타입의 열거형."""
    KRX = "KRX"  # 한국거래소
    US = "US"    # 미국 마켓
    CRYPTO = "CRYPTO"  # 암호화폐 (향후)


class TradingStatus(Enum):
    """거래 상태의 열거형."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELISTED = "delisted"


@dataclass
class StockInfo:
    """주식/증권에 대한 정보."""
    code: str
    name: str
    market: str
    status: str = "active"
    exchange: Optional[str] = None
    
    def is_active(self) -> bool:
        """주식이 거래 가능한 상태인지 확인합니다."""
        return self.status.lower() == "active"
    
    def get_display_name(self) -> str:
        """코드와 이름이 포함된 표시 이름을 가져옵니다."""
        return f"{self.code} ({self.name})"


@dataclass
class MarketSession:
    """마켓 세션 설정."""
    start_time: str  # 형식: "HH:MM"
    end_time: str    # 형식: "HH:MM"
    timezone: str    # 시간대 이름
    
    def is_session_time(self, current_time: time) -> bool:
        """현재 시간이 세션 시간 내에 있는지 확인합니다."""
        start = time.fromisoformat(self.start_time)
        end = time.fromisoformat(self.end_time)
        
        if start <= end:
            # 일반적인 경우: 09:00 - 15:30
            return start <= current_time <= end
        else:
            # 야간 경우: 23:00 - 06:00
            return current_time >= start or current_time <= end


@dataclass
class FieldConfig:
    """마켓의 필드 매핑 설정."""
    fields: Dict[str, str]  # field_name -> position_in_data
    required_fields: List[str]
    optional_fields: List[str] = field(default_factory=list)
    
    def get_field_position(self, field_name: str) -> Optional[str]:
        """데이터에서 필드의 위치를 가져옵니다."""
        return self.fields.get(field_name)
    
    def validate_data(self, data_dict: Dict[str, Any]) -> bool:
        """모든 필수 필드가 존재하는지 검증합니다."""
        return all(field_name in data_dict for field_name in self.required_fields)


@dataclass
class MarketData:
    """주식의 파싱된 마켓 데이터."""
    stock_code: str
    stock_name: str
    market: str
    timestamp: datetime
    price: float
    change: float
    change_rate: float
    volume: int
    ask_price: Optional[float] = None
    bid_price: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open_price: Optional[float] = None
    prev_close: Optional[float] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 형식으로 변환합니다."""
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'market': self.market,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'change': self.change,
            'change_rate': self.change_rate,
            'volume': self.volume,
            'ask_price': self.ask_price,
            'bid_price': self.bid_price,
            'high': self.high,
            'low': self.low,
            'open_price': self.open_price,
            'prev_close': self.prev_close
        }
    
    def get_formatted_output(self) -> str:
        """포맷된 문자열 표현을 가져옵니다."""
        change_sign = "+" if self.change >= 0 else ""
        return (
            f"[{self.market}] {self.stock_name}({self.stock_code}) "
            f"${self.price:.2f} {change_sign}{self.change:.2f} "
            f"({change_sign}{self.change_rate:.2f}%) Vol: {self.volume:,}"
        )


@dataclass
class MarketConfig:
    """마켓의 완전한 설정."""
    name: str
    tr_id: str
    session: MarketSession
    fields: FieldConfig
    exchange_codes: Dict[str, str] = field(default_factory=dict)
    
    def is_market_open(self, current_time: datetime) -> bool:
        """마켓이 현재 열려있는지 확인합니다."""
        return self.session.is_session_time(current_time.time())


@dataclass
class AuthCredentials:
    """인증 자격증명."""
    app_key: str
    app_secret: str
    access_token: str = ""
    access_token_expired: str = ""
    approval_key: str = ""
    
    def is_token_valid(self) -> bool:
        """액세스 토큰이 유효한지 확인합니다."""
        if not self.access_token or not self.access_token_expired:
            return False
        
        try:
            expired_time = datetime.fromisoformat(self.access_token_expired)
            return datetime.now() < expired_time
        except (ValueError, TypeError):
            return False


@dataclass
class SystemStatus:
    """시스템 상태 정보."""
    is_running: bool = False
    connected_markets: List[str] = field(default_factory=list)
    subscribed_stocks: Dict[str, List[str]] = field(default_factory=dict)
    last_data_time: Optional[datetime] = None
    error_count: int = 0
    start_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 형식으로 변환합니다."""
        return {
            'is_running': self.is_running,
            'connected_markets': self.connected_markets,
            'subscribed_stocks': self.subscribed_stocks,
            'last_data_time': self.last_data_time.isoformat() if self.last_data_time else None,
            'error_count': self.error_count,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }


@dataclass
class RequestInfo:
    """API 요청에 대한 정보."""
    tr_id: str
    stocks: List[StockInfo]
    request_type: str  # "subscribe" 또는 "unsubscribe"
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_stock_codes(self) -> List[str]:
        """주식 코드 목록을 가져옵니다."""
        return [stock.code for stock in self.stocks]


@dataclass
class ErrorInfo:
    """에러 정보."""
    error_code: str
    error_message: str
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.error_message}"
