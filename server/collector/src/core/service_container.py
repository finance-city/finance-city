# core/service_container.py

from typing import Dict, Any, TypeVar, Type, Optional, Callable, Set, Union
from dataclasses import dataclass
import logging
import redis

from .interfaces import (
    IStockManager, IMarketManager, ITimeCalculator, 
    IAuthManager, IWebSocketManager, IRequestBuilder, IDataParser
)

T = TypeVar('T')
ServiceKey = Union[Type, str]


@dataclass
class ServiceDefinition:
    """서비스 정의"""
    service_type: ServiceKey
    factory: Callable[[], Any]
    singleton: bool = True
    dependencies: Optional[Set[ServiceKey]] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = set()


class ServiceContainer:
    """의존성 주입 컨테이너
    
    서비스들의 생성, 의존성 해결, 라이프사이클을 관리합니다.
    """
    
    def __init__(self, config: Any):  # AppConfig 임포트 문제로 Any 사용
        """컨테이너 초기화
        
        Args:
            config: 애플리케이션 설정
        """
        self.config = config
        self._services: Dict[ServiceKey, ServiceDefinition] = {}
        self._instances: Dict[ServiceKey, Any] = {}
        self._building: Set[ServiceKey] = set()  # 순환 의존성 방지
        self._initialized = False
        
        # 기본 서비스들 등록
        self._register_core_services()
    
    def _register_core_services(self) -> None:
        """핵심 서비스들을 컨테이너에 등록"""
        
        # PYTHONPATH에 현재 src 디렉터리 추가 (import 문제 해결)
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.dirname(current_dir)  # src 디렉터리
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
            logging.info(f"PYTHONPATH에 추가: {src_dir}")
        
        # Redis 클라이언트 (외부 의존성)
        self.register(
            redis.Redis,
            factory=lambda: redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                decode_responses=True
            ),
            singleton=True
        )
        
        # 주식 서비스 (의존성 없음)
        def create_stock_service():
            from services.stock_service import StockService
            return StockService(self.config.stocks_csv_path)
        
        self.register(
            IStockManager,
            factory=create_stock_service,
            singleton=True
        )
        
        # 시간 계산 서비스 (의존성 없음)
        def create_time_calculator():
            from services.time_calculator import TimeCalculatorService
            return TimeCalculatorService()
            
        self.register(
            ITimeCalculator,
            factory=create_time_calculator,
            singleton=True
        )
        
        # TradingConfig (AppConfig에서 변환)
        def create_trading_config():
            import importlib
            config_module = importlib.import_module('config')
            TradingConfig = getattr(config_module, 'TradingConfig')
            return TradingConfig.create_default(
                kis_app_key=self.config.kis_app_key,
                kis_app_secret=self.config.kis_app_secret
            )
            
        self.register(
            'TradingConfig',  # 문자열 키 사용
            factory=create_trading_config,
            singleton=True
        )
        
        # 인증 서비스 (TradingConfig, Redis 의존)
        def create_auth_service():
            from services.auth_service import AuthService
            return AuthService(
                config=self.get('TradingConfig'),
                redis_client=self.get(redis.Redis)
            )
            
        self.register(
            IAuthManager,
            factory=create_auth_service,
            singleton=True,
            dependencies={'TradingConfig', redis.Redis}
        )
        
        # KRX 마켓 프로바이더
        def create_krx_provider():
            import importlib
            markets_module = importlib.import_module('markets.krx')
            KRXMarketProvider = getattr(markets_module, 'KRXMarketProvider')
            return KRXMarketProvider()
            
        self.register(
            'KRXMarketProvider',
            factory=create_krx_provider,
            singleton=True
        )
        
        # US 마켓 프로바이더
        def create_us_provider():
            import importlib
            markets_module = importlib.import_module('markets.us')
            USMarketProvider = getattr(markets_module, 'USMarketProvider')
            return USMarketProvider()
            
        self.register(
            'USMarketProvider',
            factory=create_us_provider,
            singleton=True
        )
        
        # 마켓 매니저 서비스 (StockService 의존)
        def create_market_manager():
            from services.market_manager_service import MarketManagerService
            return MarketManagerService()
            
        self.register(
            IMarketManager,
            factory=create_market_manager,
            singleton=True
        )
        
        # WebSocket 매니저 서비스 (AuthManager, RequestBuilder 의존)
        def create_websocket_manager():
            from services.websocket_manager_service import WebSocketManagerService
            return WebSocketManagerService(
                auth_manager=self.get(IAuthManager),  # AuthManager 다시 연결
                request_builder=self.get(IRequestBuilder),
                api_url=getattr(self.config, 'kis_ws_url', 'wss://ops.koreainvestment.com:21000')
            )
            
        self.register(
            IWebSocketManager,
            factory=create_websocket_manager,
            singleton=True,
            dependencies={IAuthManager, IRequestBuilder}
        )
        
        # 요청 빌더 서비스 (MarketManager, TimeCalculator, AuthManager 의존)
        def create_request_builder():
            from services.request_builder import RequestBuilderService
            return RequestBuilderService(
                market_manager=self.get(IMarketManager),
                time_calculator=self.get(ITimeCalculator),
                approval_key=self.get(IAuthManager).get_approval_key()  # 실제 approval_key 사용
            )
            
        self.register(
            IRequestBuilder,
            factory=create_request_builder,
            singleton=True,
            dependencies={IMarketManager, ITimeCalculator, IAuthManager}
        )
        
        # 데이터 파서 서비스 (MarketManager 의존)
        def create_data_parser():
            from data.parser import KISDataParser
            return KISDataParser(
                market_manager=self.get(IMarketManager)
            )
            
        self.register(
            IDataParser,
            factory=create_data_parser,
            singleton=True,
            dependencies={IMarketManager}
        )
    
    def register(
        self, 
        service_type: ServiceKey, 
        factory: Callable[[], Any],
        singleton: bool = True,
        dependencies: Optional[Set[ServiceKey]] = None
    ) -> None:
        """서비스를 컨테이너에 등록
        
        Args:
            service_type: 서비스 타입 (인터페이스, 클래스 또는 문자열 키)
            factory: 서비스 인스턴스 생성 팩토리 함수
            singleton: 싱글톤 여부 (기본값: True)
            dependencies: 의존하는 서비스 타입들
        """
        if dependencies is None:
            dependencies = set()
            
        self._services[service_type] = ServiceDefinition(
            service_type=service_type,
            factory=factory,
            singleton=singleton,
            dependencies=dependencies
        )
        
        service_name = getattr(service_type, '__name__', str(service_type))
        logging.debug(f"Service registered: {service_name}")
    
    def get(self, service_type: ServiceKey) -> Any:
        """서비스 인스턴스 조회
        
        Args:
            service_type: 요청할 서비스 타입 또는 키
            
        Returns:
            서비스 인스턴스
            
        Raises:
            ValueError: 서비스가 등록되지 않은 경우
            RuntimeError: 순환 의존성이 발견된 경우
        """
        # 순환 의존성 검사
        if service_type in self._building:
            cycle_names = []
            for t in list(self._building) + [service_type]:
                name = getattr(t, '__name__', str(t))
                cycle_names.append(name)
            cycle = " -> ".join(cycle_names)
            raise RuntimeError(f"Circular dependency detected: {cycle}")
        
        # 이미 생성된 인스턴스 반환 (싱글톤)
        if service_type in self._instances:
            return self._instances[service_type]
        
        # 서비스 정의 확인
        if service_type not in self._services:
            service_name = getattr(service_type, '__name__', str(service_type))
            raise ValueError(f"Service not registered: {service_name}")
        
        definition = self._services[service_type]
        
        # 의존성 해결
        self._building.add(service_type)
        try:
            # 의존성 먼저 생성
            for dep_type in (definition.dependencies or set()):
                self.get(dep_type)
            
            # 인스턴스 생성
            instance = definition.factory()
            
            # 싱글톤인 경우 캐시
            if definition.singleton:
                self._instances[service_type] = instance
            
            service_name = getattr(service_type, '__name__', str(service_type))
            logging.debug(f"Service created: {service_name}")
            return instance
            
        finally:
            self._building.remove(service_type)
    
    def get_optional(self, service_type: Type[T]) -> Optional[T]:
        """서비스 인스턴스 조회 (옵셔널)
        
        Args:
            service_type: 요청할 서비스 타입
            
        Returns:
            서비스 인스턴스 또는 None
        """
        try:
            return self.get(service_type)
        except (ValueError, RuntimeError):
            return None
    
    def initialize_services(self) -> None:
        """모든 싱글톤 서비스들을 미리 초기화
        
        애플리케이션 시작 시 호출하여 의존성 문제를 조기에 발견
        """
        if self._initialized:
            return
        
        singleton_services = [
            service_type for service_type, definition in self._services.items()
            if definition.singleton
        ]
        
        logging.info(f"Initializing {len(singleton_services)} singleton services...")
        
        for service_type in singleton_services:
            try:
                self.get(service_type)
                logging.debug(f"✅ {_get_service_name(service_type)}")
            except Exception as e:
                logging.error(f"❌ Failed to initialize {_get_service_name(service_type)}: {e}")
                raise
        
        self._initialized = True
        logging.info("✅ All services initialized successfully")
    
    def health_check(self) -> Dict[str, Any]:
        """컨테이너 및 서비스 상태 확인
        
        Returns:
            상태 정보 딕셔너리
        """
        status = {
            "container_initialized": self._initialized,
            "registered_services": len(self._services),
            "active_instances": len(self._instances),
            "services": {}
        }
        
        for service_type, definition in self._services.items():
            service_name = _get_service_name(service_type)
            is_instantiated = service_type in self._instances
            
            dep_names = []
            for dep in (definition.dependencies or set()):
                dep_names.append(_get_service_name(dep))
            
            status["services"][service_name] = {
                "singleton": definition.singleton,
                "instantiated": is_instantiated,
                "dependencies": dep_names
            }
        
        return status
    
    def shutdown(self) -> None:
        """컨테이너 정리
        
        관리되는 모든 리소스를 정리합니다.
        """
        logging.info("Shutting down service container...")
        
        # 생성된 인스턴스들 정리 (역순으로)
        for service_type, instance in reversed(list(self._instances.items())):
            try:
                # cleanup 메서드가 있으면 호출
                if hasattr(instance, 'cleanup'):
                    instance.cleanup()
                    logging.debug(f"Cleaned up: {_get_service_name(service_type)}")
                elif hasattr(instance, 'close'):
                    instance.close()
                    logging.debug(f"Closed: {_get_service_name(service_type)}")
            except Exception as e:
                logging.warning(f"Failed to cleanup {_get_service_name(service_type)}: {e}")
        
        # 상태 초기화
        self._instances.clear()
        self._building.clear()
        self._initialized = False
        
        logging.info("Service container shutdown complete")


# 전역 컨테이너 인스턴스 (싱글톤 패턴)
def _get_service_name(service_type: ServiceKey) -> str:
    """서비스 타입에서 이름 추출"""
    return getattr(service_type, '__name__', str(service_type))


# 전역 컨테이너 인스턴스 (싱글톤 패턴)
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """전역 서비스 컨테이너 인스턴스 반환
    
    Returns:
        ServiceContainer 인스턴스
        
    Raises:
        RuntimeError: 컨테이너가 초기화되지 않은 경우
    """
    global _container
    if _container is None:
        raise RuntimeError(
            "Service container not initialized. "
            "Call initialize_container() first."
        )
    return _container


def initialize_container(config: Any) -> ServiceContainer:  # Any로 타입 문제 해결
    """전역 서비스 컨테이너 초기화
    
    Args:
        config: 애플리케이션 설정
        
    Returns:
        초기화된 ServiceContainer 인스턴스
    """
    global _container
    if _container is not None:
        logging.warning("Service container already initialized")
        return _container
    
    _container = ServiceContainer(config)
    return _container


def cleanup_container() -> None:
    """전역 서비스 컨테이너 정리"""
    global _container
    if _container is not None:
        _container.shutdown()
        _container = None
