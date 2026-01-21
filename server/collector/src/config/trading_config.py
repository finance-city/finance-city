# config/trading_config.py

from dataclasses import dataclass
from datetime import time
from typing import Dict, Tuple, List, Optional, Any
from enum import Enum


class MarketType(Enum):
    """시장 타입"""
    KRX_REGULAR = "krx_regular"
    KRX_AFTER = "krx_after"
    US_REGULAR = "us_regular"


@dataclass
class MarketConfig:
    """시장별 설정"""
    name: str
    timezone: str
    regular_hours: Tuple[time, time]
    after_hours: Optional[Tuple[time, time]] = None
    tr_ids: Optional[Dict[str, str]] = None  # session_type -> tr_id
    
    def __post_init__(self):
        if self.tr_ids is None:
            self.tr_ids = {}


@dataclass  
class ExchangeMapping:
    """거래소별 코드 매핑"""
    name: str
    night_code: str    # 야간거래 코드 (D + 이 코드)
    day_code: str      # 주간거래 코드 (R + 이 코드)


@dataclass
class TradingConfig:
    """거래 관련 설정"""
    # 시장별 설정
    markets: Dict[str, MarketConfig]
    
    # 거래소 매핑 (미국 주식용)
    exchanges: Dict[str, ExchangeMapping]
    
    # KIS API 설정
    kis_app_key: str = ""
    kis_app_secret: str = ""
    kis_api_base_url: str = "https://openapi.koreainvestment.com:9443"
    kis_ws_url: str = "ws://ops.koreainvestment.com:21000"
    
    # 써머타임 설정
    dst_start_month: int = 3    # 3월
    dst_start_week: int = 2     # 둘째 주  
    dst_start_day: int = 6      # 일요일 (0=월요일, 6=일요일)
    dst_end_month: int = 11     # 11월
    dst_end_week: int = 1       # 첫째 주
    dst_end_day: int = 6        # 일요일
    
    # 필드 매핑 (TR_ID별)
    field_mappings: Optional[Dict[str, Dict[str, Any]]] = None
    
    def __post_init__(self):
        if self.field_mappings is None:
            self.field_mappings = {}
    
    @classmethod
    def create_default(cls, kis_app_key: str = "", kis_app_secret: str = "") -> 'TradingConfig':
        """기본 설정 생성"""
        return cls(
            markets={
                "KRX": MarketConfig(
                    name="KRX",
                    timezone="Asia/Seoul",
                    regular_hours=(time(9, 0), time(15, 30)),
                    after_hours=(time(16, 0), time(18, 0)),
                    tr_ids={
                        "regular": "H0STCNT0",
                        "after": "H0NXCNT0"
                    }
                ),
                "US": MarketConfig(
                    name="US",
                    timezone="US/Eastern", 
                    regular_hours=(time(0, 0), time(23, 59)),  # 24시간 활성화
                    tr_ids={
                        "regular": "HDFSCNT0"
                    }
                )
            },
            exchanges={
                "NASDAQ": ExchangeMapping("NASDAQ", "NAS", "BAQ"),
                "NYSE": ExchangeMapping("NYSE", "NYS", "BAY"),
                "AMEX": ExchangeMapping("AMEX", "AMS", "BAA")
            },
            kis_app_key=kis_app_key,
            kis_app_secret=kis_app_secret
        )
    
    def get_market_config(self, market_name: str) -> MarketConfig:
        """시장 설정 반환"""
        market_config = self.markets.get(market_name.upper())
        if not market_config:
            raise ValueError(f"Unknown market: {market_name}")
        return market_config
    
    def get_exchange_mapping(self, exchange_name: str) -> ExchangeMapping:
        """거래소 매핑 반환"""
        exchange_mapping = self.exchanges.get(exchange_name.upper())
        if not exchange_mapping:
            raise ValueError(f"Unknown exchange: {exchange_name}")
        return exchange_mapping
    
    def get_us_exchange_code(self, exchange: str, is_day_trading: bool = False) -> str:
        """미국 거래소 코드 반환"""
        mapping = self.get_exchange_mapping(exchange)
        return mapping.day_code if is_day_trading else mapping.night_code


# 전역 거래 설정 인스턴스
_trading_config: Optional[TradingConfig] = None


def get_trading_config() -> TradingConfig:
    """거래 설정 인스턴스 반환 (싱글톤)"""
    global _trading_config
    if _trading_config is None:
        _trading_config = TradingConfig.create_default()
    return _trading_config
