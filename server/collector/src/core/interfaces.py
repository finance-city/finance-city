"""
금융 데이터 수집 시스템의 코어 인터페이스.

이 모듈은 시스템의 다양한 구성 요소 간 계약을 설정하는 코어 인터페이스들을 정의하여
인터페이스 중심 설계와 더 나은 테스트 가능성을 제공합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime

from .models import StockInfo, MarketSession, FieldConfig, MarketData


class IMarketProvider(ABC):
    """마켓별 데이터 제공자를 위한 인터페이스."""
    
    @abstractmethod
    def get_market_name(self) -> str:
        """마켓 이름을 가져옵니다."""
        pass
    
    @abstractmethod
    def get_tr_id(self) -> str:
        """이 마켓의 TR ID를 가져옵니다."""
        pass
    
    @abstractmethod
    def get_session_config(self) -> MarketSession:
        """마켓 세션 설정을 가져옵니다."""
        pass
    
    @abstractmethod
    def get_field_config(self) -> FieldConfig:
        """이 마켓의 필드 설정을 가져옵니다."""
        pass
    
    @abstractmethod
    def is_market_open(self, current_time: datetime) -> bool:
        """마켓이 현재 열려있는지 확인합니다."""
        pass
    
    @abstractmethod
    def parse_stock_code(self, code: str) -> Optional[str]:
        """이 마켓의 종목 코드를 파싱하고 검증합니다."""
        pass
    
    @abstractmethod
    def format_stock_code(self, code: str, is_night_trading: bool = False) -> str:
        """API 요청을 위한 종목 코드를 포맷합니다."""
        pass


class IStockManager(ABC):
    """주식 관리를 위한 인터페이스."""
    
    @abstractmethod
    def load_stocks(self) -> None:
        """설정된 소스에서 주식 데이터를 로드합니다."""
        pass
    
    @abstractmethod
    def get_active_stocks(self) -> List[StockInfo]:
        """활성 주식 목록을 가져옵니다."""
        pass
    
    @abstractmethod
    def get_stocks_by_market(self, market: str) -> List[StockInfo]:
        """마켓별로 필터링된 주식을 가져옵니다."""
        pass
    
    @abstractmethod
    def is_stock_active(self, code: str) -> bool:
        """주식이 활성 상태인지 확인합니다."""
        pass
    
    @abstractmethod
    def add_stock(self, stock_info: StockInfo) -> None:
        """새로운 주식을 추가합니다."""
        pass
    
    @abstractmethod
    def remove_stock(self, code: str) -> None:
        """주식을 제거합니다."""
        pass


class IRequestBuilder(ABC):
    """API 요청 빌딩을 위한 인터페이스."""
    
    @abstractmethod
    def build_subscription_request(self, stocks: List[StockInfo]) -> Dict[str, Any]:
        """주어진 주식들의 구독 요청을 빌드합니다."""
        pass
    
    @abstractmethod
    def build_unsubscription_request(self, stocks: List[StockInfo]) -> Dict[str, Any]:
        """주어진 주식들의 구독 해제 요청을 빌드합니다."""
        pass


class IDataParser(ABC):
    """마켓 데이터 파싱을 위한 인터페이스."""
    
    @abstractmethod
    def parse_realtime_data(self, message: str, market: str) -> Optional[MarketData]:
        """WebSocket 메시지에서 실시간 마켓 데이터를 파싱합니다."""
        pass
    
    @abstractmethod
    def parse_error_message(self, message: str) -> Optional[str]:
        """WebSocket 응답에서 에러 메시지를 파싱합니다."""
        pass


class ITimeCalculator(ABC):
    """시간 관련 계산을 위한 인터페이스."""
    
    @abstractmethod
    def is_dst_active(self, dt: datetime) -> bool:
        """주어진 날짜/시간에 일광절약시간이 활성화되어 있는지 확인합니다."""
        pass
    
    @abstractmethod
    def get_market_time(self, market: str, dt: Optional[datetime] = None) -> datetime:
        """마켓 시간대의 현재 또는 지정된 시간을 가져옵니다."""
        pass
    
    @abstractmethod
    def is_trading_hours(self, market: str, dt: Optional[datetime] = None) -> bool:
        """주어진 시간이 마켓의 거래 시간 내에 있는지 확인합니다."""
        pass


class IAuthManager(ABC):
    """인증 관리를 위한 인터페이스."""
    
    @abstractmethod
    def get_access_token(self) -> str:
        """현재 액세스 토큰을 가져옵니다."""
        pass
    
    @abstractmethod
    def get_approval_key(self) -> str:
        """WebSocket 연결을 위한 승인 키를 가져옵니다."""
        pass
    
    @abstractmethod
    def refresh_token_if_needed(self) -> bool:
        """필요한 경우 토큰을 갱신합니다. 갱신된 경우 True를 반환합니다."""
        pass
    
    @abstractmethod
    def is_token_valid(self) -> bool:
        """현재 토큰이 유효한지 확인합니다."""
        pass


class IWebSocketManager(ABC):
    """WebSocket 연결 관리를 위한 인터페이스."""
    
    @abstractmethod
    async def connect(self) -> None:
        """WebSocket 연결을 설정합니다."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """WebSocket 연결을 닫습니다."""
        pass
    
    @abstractmethod
    async def subscribe_stocks(self, stocks: List[StockInfo]) -> None:
        """주어진 주식들의 실시간 데이터를 구독합니다."""
        pass
    
    @abstractmethod
    async def unsubscribe_stocks(self, stocks: List[StockInfo]) -> None:
        """주어진 주식들의 실시간 데이터 구독을 해제합니다."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """WebSocket이 연결되어 있는지 확인합니다."""
        pass
    
    @abstractmethod
    async def start_data_stream(self, data_handler: Callable) -> None:
        """데이터 스트림을 수신하고 처리하기 시작합니다."""
        pass


class IMarketManager(ABC):
    """복수 마켓 관리를 위한 인터페이스."""
    
    @abstractmethod
    def get_supported_markets(self) -> Set[str]:
        """지원되는 마켓 이름의 집합을 가져옵니다."""
        pass
    
    @abstractmethod
    def get_available_markets(self) -> List[str]:
        """사용 가능한 마켓 이름의 목록을 가져옵니다."""
        pass
    
    @abstractmethod
    def get_market_provider(self, market: str) -> IMarketProvider:
        """지정된 마켓의 마켓 프로바이더를 가져옵니다."""
        pass
    
    @abstractmethod
    def classify_stocks_by_market(self, stocks: List[StockInfo]) -> Dict[str, List[StockInfo]]:
        """주식들을 대상 마켓별로 분류합니다."""
        pass
    
    @abstractmethod
    def get_active_sessions(self) -> Dict[str, MarketSession]:
        """현재 활성화된 마켓 세션들을 가져옵니다."""
        pass
    
    @abstractmethod
    def get_session_by_tr_id(self, tr_id: str) -> Optional[MarketSession]:
        """TR ID로 마켓 세션을 가져옵니다 (레거시 호환성)."""
        pass


class ICollectorOrchestrator(ABC):
    """메인 컬렉터 오케스트레이터를 위한 인터페이스."""
    
    @abstractmethod
    async def start(self) -> None:
        """데이터 수집 프로세스를 시작합니다."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """데이터 수집 프로세스를 중지합니다."""
        pass
    
    @abstractmethod
    async def restart(self) -> None:
        """데이터 수집 프로세스를 재시작합니다."""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """컬렉터의 현재 상태를 가져옵니다."""
        pass
