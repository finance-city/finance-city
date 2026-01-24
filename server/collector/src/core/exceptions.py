"""
금융 데이터 수집 시스템의 사용자 정의 예외.

이 모듈은 시스템의 다양한 구성 요소에 대한 특정
오류 처리를 제공하는 사용자 정의 예외 클래스들을 정의합니다.
"""

from typing import Optional


class CollectorError(Exception):
    """모든 컬렉터 관련 오류의 기본 예외."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "COLLECTOR_ERROR"
        self.context = context or {}
    
    def to_dict(self) -> dict:
        """예외를 딕셔너리 형식으로 변환합니다."""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'context': self.context
        }


class ConfigurationError(CollectorError):
    """설정 관련 오류가 있을 때 발생합니다."""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(
            message,
            error_code="CONFIG_ERROR",
            context={'config_key': config_key} if config_key else {}
        )


class AuthenticationError(CollectorError):
    """인증이 실패할 때 발생합니다."""
    
    def __init__(self, message: str, auth_type: Optional[str] = None):
        super().__init__(
            message,
            error_code="AUTH_ERROR",
            context={'auth_type': auth_type} if auth_type else {}
        )


class MarketError(CollectorError):
    """마켓 관련 오류가 있을 때 발생합니다."""
    
    def __init__(self, message: str, market: Optional[str] = None):
        super().__init__(
            message,
            error_code="MARKET_ERROR",
            context={'market': market} if market else {}
        )


class StockCodeError(MarketError):
    """유효하지 않은 종목 코드가 있을 때 발생합니다."""
    
    def __init__(self, message: str, stock_code: Optional[str] = None, market: Optional[str] = None):
        super().__init__(
            message,
            market=market
        )
        self.error_code = "STOCK_CODE_ERROR"
        self.context.update({'stock_code': stock_code} if stock_code else {})


class WebSocketError(CollectorError):
    """WebSocket 관련 오류가 있을 때 발생합니다."""
    
    def __init__(self, message: str, connection_state: Optional[str] = None):
        super().__init__(
            message,
            error_code="WEBSOCKET_ERROR",
            context={'connection_state': connection_state} if connection_state else {}
        )


class DataParsingError(CollectorError):
    """데이터 파싱이 실패할 때 발생합니다."""
    
    def __init__(self, message: str, raw_data: Optional[str] = None, parser_type: Optional[str] = None):
        context = {}
        if raw_data:
            # 로깅을 위해 원본 데이터 자르기
            context['raw_data'] = raw_data[:200] + "..." if len(raw_data) > 200 else raw_data
        if parser_type:
            context['parser_type'] = parser_type
        
        super().__init__(
            message,
            error_code="PARSING_ERROR",
            context=context
        )


class APIError(CollectorError):
    """API 호출이 실패할 때 발생합니다."""
    
    def __init__(self, message: str, api_endpoint: Optional[str] = None, status_code: Optional[int] = None, response: Optional[str] = None):
        context = {}
        if api_endpoint:
            context['api_endpoint'] = api_endpoint
        if status_code:
            context['status_code'] = status_code
        if response:
            # 로깅을 위해 응답 자르기
            context['response'] = response[:200] + "..." if len(response) > 200 else response
        
        super().__init__(
            message,
            error_code="API_ERROR",
            context=context
        )


class TimeoutError(CollectorError):
    """작업 시간이 초과될 때 발생합니다."""
    
    def __init__(self, message: str, timeout_duration: Optional[float] = None, operation: Optional[str] = None):
        context = {}
        if timeout_duration:
            context['timeout_duration'] = timeout_duration
        if operation:
            context['operation'] = operation
        
        super().__init__(
            message,
            error_code="TIMEOUT_ERROR",
            context=context
        )


class ValidationError(CollectorError):
    """데이터 검증이 실패할 때 발생합니다."""
    
    def __init__(self, message: str, validation_type: Optional[str] = None, invalid_data: Optional[dict] = None):
        context = {}
        if validation_type:
            context['validation_type'] = validation_type
        if invalid_data:
            context['invalid_data'] = invalid_data
        
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            context=context
        )


class ServiceError(CollectorError):
    """서비스 작업이 실패할 때 발생합니다."""
    
    def __init__(self, message: str, service_name: Optional[str] = None, operation: Optional[str] = None):
        context = {}
        if service_name:
            context['service_name'] = service_name
        if operation:
            context['operation'] = operation
        
        super().__init__(
            message,
            error_code="SERVICE_ERROR",
            context=context
        )


class InitializationError(CollectorError):
    """구성 요소 초기화가 실패할 때 발생합니다."""
    
    def __init__(self, message: str, component: Optional[str] = None, dependency: Optional[str] = None):
        context = {}
        if component:
            context['component'] = component
        if dependency:
            context['dependency'] = dependency
        
        super().__init__(
            message,
            error_code="INIT_ERROR",
            context=context
        )


class ResourceError(CollectorError):
    """리소스 접근이 실패할 때 발생합니다."""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, resource_path: Optional[str] = None):
        context = {}
        if resource_type:
            context['resource_type'] = resource_type
        if resource_path:
            context['resource_path'] = resource_path
        
        super().__init__(
            message,
            error_code="RESOURCE_ERROR",
            context=context
        )


# 공통 오류 시나리오를 위한 편의 함수들

def raise_config_missing(key: str):
    """누락된 설정 키에 대한 ConfigurationError를 발생시킵니다."""
    raise ConfigurationError(f"Missing required configuration: {key}", config_key=key)


def raise_invalid_stock_code(code: str, market: Optional[str] = None):
    """유효하지 않은 종목 코드에 대한 StockCodeError를 발생시킵니다."""
    raise StockCodeError(f"Invalid stock code: {code}", stock_code=code, market=market)


def raise_market_not_supported(market: str):
    """지원되지 않는 마켓에 대한 MarketError를 발생시킵니다."""
    raise MarketError(f"Market not supported: {market}", market=market)


def raise_auth_token_expired():
    """만료된 토큰에 대한 AuthenticationError를 발생시킵니다."""
    raise AuthenticationError("Access token has expired", auth_type="token")


def raise_websocket_not_connected():
    """연결되지 않은 상태일 때 WebSocketError를 발생시킵니다."""
    raise WebSocketError("WebSocket is not connected", connection_state="disconnected")
