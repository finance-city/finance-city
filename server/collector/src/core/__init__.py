"""
금융 데이터 수집 시스템의 코어 모듈.

이 모듈은 시스템 전반에서 사용되는 인터페이스, 데이터 모델,
예외 클래스를 포함한 기본 구성 요소들을 제공합니다.
"""

# 코어 모델 임포트
from .models import (
    MarketType,
    TradingStatus,
    StockInfo,
    MarketSession,
    FieldConfig,
    MarketData,
    MarketConfig,
    AuthCredentials,
    SystemStatus,
    RequestInfo,
    ErrorInfo
)

# 코어 인터페이스 임포트
from .interfaces import (
    IMarketProvider,
    IStockManager,
    IRequestBuilder,
    IDataParser,
    ITimeCalculator,
    IAuthManager,
    IWebSocketManager,
    IMarketManager,
    ICollectorOrchestrator
)

# 코어 예외 임포트
from .exceptions import (
    CollectorError,
    ConfigurationError,
    AuthenticationError,
    MarketError,
    StockCodeError,
    WebSocketError,
    DataParsingError,
    APIError,
    TimeoutError,
    ValidationError,
    ServiceError,
    InitializationError,
    ResourceError,
    # 편의 함수들
    raise_config_missing,
    raise_invalid_stock_code,
    raise_market_not_supported,
    raise_auth_token_expired,
    raise_websocket_not_connected
)

# 서비스 컨테이너 임포트
from .service_container import (
    ServiceContainer,
    get_container,
    initialize_container,
    cleanup_container
)

__all__ = [
    # Models
    "MarketType",
    "TradingStatus", 
    "StockInfo",
    "MarketSession",
    "FieldConfig",
    "MarketData",
    "MarketConfig",
    "AuthCredentials",
    "SystemStatus",
    "RequestInfo",
    "ErrorInfo",
    
    # Interfaces
    "IMarketProvider",
    "IStockManager",
    "IRequestBuilder",
    "IDataParser",
    "ITimeCalculator",
    "IAuthManager",
    "IWebSocketManager",
    "IMarketManager",
    "ICollectorOrchestrator",
    
    # Exceptions
    "CollectorError",
    "ConfigurationError",
    "AuthenticationError",
    "MarketError",
    "StockCodeError",
    "WebSocketError",
    "DataParsingError",
    "APIError",
    "TimeoutError",
    "ValidationError",
    "ServiceError",
    "InitializationError",
    "ResourceError",
    "raise_config_missing",
    "raise_invalid_stock_code",
    "raise_market_not_supported",
    "raise_auth_token_expired",
    "raise_websocket_not_connected",
    
    # Service Container
    "ServiceContainer",
    "get_container", 
    "initialize_container",
    "cleanup_container"
]
