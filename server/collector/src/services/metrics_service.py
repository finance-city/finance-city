"""
Prometheus 메트릭 서비스

Collector의 모든 비즈니스 메트릭을 중앙 관리하는 싱글톤 서비스
"""

import time
from typing import Optional
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    REGISTRY,
    start_http_server,
    generate_latest,
)
import logging


class MetricsService:
    """Collector 메트릭 관리 서비스 (싱글톤)"""
    
    _instance: Optional['MetricsService'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """메트릭 초기화 (한 번만 실행)"""
        if self._initialized:
            return
            
        self.logger = logging.getLogger(__name__)
        self.registry = REGISTRY
        
        # ==========================================
        # 비즈니스 메트릭 정의
        # ==========================================
        
        # 수집된 총 틱 개수 (Counter)
        self.ticks_total = Counter(
            'fc_collector_ticks_total',
            'Total number of ticks collected',
            labelnames=['market', 'symbol'],
            registry=self.registry
        )
        
        # 처리 소요 시간 (Histogram)
        self.processing_duration = Histogram(
            'fc_collector_processing_duration_seconds',
            'Time taken to process tick data from reception to Redis publish',
            labelnames=['market'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        # 시장 상태 (Gauge: 0=Closed, 1=Open)
        self.market_status = Gauge(
            'fc_collector_market_status',
            'Market operational status (0=Closed, 1=Open)',
            labelnames=['market'],
            registry=self.registry
        )
        
        # WebSocket 연결 상태 (Gauge: 0=Disconnected, 1=Connected)
        self.websocket_connected = Gauge(
            'fc_collector_websocket_connected',
            'WebSocket connection status (0=Disconnected, 1=Connected)',
            labelnames=['market'],
            registry=self.registry
        )
        
        # Redis 발행 성공/실패 카운터
        self.redis_publish_total = Counter(
            'fc_collector_redis_publish_total',
            'Total number of Redis publish operations',
            labelnames=['market', 'status'],  # status: success, failure
            registry=self.registry
        )
        
        # 활성 구독 종목 수 (Gauge)
        self.active_subscriptions = Gauge(
            'fc_collector_active_subscriptions',
            'Number of actively subscribed stocks',
            labelnames=['market'],
            registry=self.registry
        )
        
        # 에러 카운터
        self.errors_total = Counter(
            'fc_collector_errors_total',
            'Total number of errors encountered',
            labelnames=['market', 'error_type'],  # parsing, network, auth, etc
            registry=self.registry
        )
        
        # 초기 메트릭 값 설정 (Prometheus가 즉시 수집할 수 있도록)
        self._initialize_default_metrics()
        
        self._initialized = True
        self.logger.info("✅ MetricsService initialized")
    
    def _initialize_default_metrics(self) -> None:
        """기본 메트릭 초기값 설정"""
        # 주요 시장에 대한 초기값 설정
        for market in ['krx', 'us']:
            # WebSocket 연결 상태: 초기값 0 (연결 안됨)
            self.websocket_connected.labels(market=market).set(0)
            
            # 시장 상태: 초기값 0 (폐장)
            self.market_status.labels(market=market).set(0)
            
            # 활성 구독: 초기값 0
            self.active_subscriptions.labels(market=market).set(0)
        
        self.logger.debug("Default metrics initialized")
    
    # ==========================================
    # 메트릭 기록 메서드
    # ==========================================
    
    def record_tick(self, market: str, symbol: str) -> None:
        """틱 데이터 수신 기록
        
        Args:
            market: 시장 (krx, us)
            symbol: 종목 코드
        """
        self.ticks_total.labels(market=market, symbol=symbol).inc()
        # 첫 틱 수신 시에만 로깅
        count = self.ticks_total.labels(market=market, symbol=symbol)._value.get()
        if count <= 1:
            self.logger.info(f"📊 First tick recorded: {market}/{symbol}")
    
    def record_processing_time(self, market: str, duration_seconds: float) -> None:
        """처리 시간 기록
        
        Args:
            market: 시장 (krx, us)
            duration_seconds: 처리 시간 (초)
        """
        self.processing_duration.labels(market=market).observe(duration_seconds)
    
    def set_market_status(self, market: str, is_open: bool) -> None:
        """시장 상태 설정
        
        Args:
            market: 시장 (krx, us)
            is_open: 개장 여부
        """
        status = 1 if is_open else 0
        self.market_status.labels(market=market).set(status)
        self.logger.debug(f"Market status updated: {market} = {'Open' if is_open else 'Closed'}")
    
    def get_market_status(self, market: str) -> int:
        """현재 시장 상태 조회
        
        Args:
            market: 시장 (krx, us)
            
        Returns:
            0 (Closed) 또는 1 (Open)
        """
        try:
            # Prometheus Gauge의 현재 값 조회
            metric = self.market_status.labels(market=market)
            # _value는 Gauge 내부 구조이므로 안전하게 접근
            if hasattr(metric, '_value'):
                return int(metric._value.get())
            return 0  # 기본값
        except Exception as e:
            self.logger.warning(f"시장 상태 조회 실패: {e}")
            return 0
    
    def set_websocket_status(self, market: str, is_connected: bool) -> None:
        """WebSocket 연결 상태 설정
        
        Args:
            market: 시장 (krx, us)
            is_connected: 연결 여부
        """
        status = 1 if is_connected else 0
        self.websocket_connected.labels(market=market).set(status)
        self.logger.info(f"📊 WebSocket status metric updated: {market} = {'Connected (1)' if is_connected else 'Disconnected (0)'}")
    
    def record_redis_publish(self, market: str, success: bool) -> None:
        """Redis publish 결과 기록
        
        Args:
            market: 시장 (krx, us)
            success: 성공 여부
        """
        status = 'success' if success else 'failure'
        self.redis_publish_total.labels(market=market, status=status).inc()
    
    def set_active_subscriptions(self, market: str, count: int) -> None:
        """활성 구독 종목 수 설정
        
        Args:
            market: 시장 (krx, us)
            count: 구독 종목 수
        """
        self.active_subscriptions.labels(market=market).set(count)
        self.logger.info(f"📊 Active subscriptions metric updated: {market} = {count}")
    
    def record_error(self, market: str, error_type: str) -> None:
        """에러 발생 기록
        
        Args:
            market: 시장 (krx, us)
            error_type: 에러 유형 (parsing, network, auth, etc)
        """
        self.errors_total.labels(market=market, error_type=error_type).inc()
    
    # ==========================================
    # Context Manager (처리 시간 자동 측정)
    # ==========================================
    
    class ProcessingTimer:
        """처리 시간 자동 측정을 위한 Context Manager"""
        
        def __init__(self, metrics_service: 'MetricsService', market: str):
            self.metrics_service = metrics_service
            self.market = market
            self.start_time = None
        
        def __enter__(self):
            self.start_time = time.perf_counter()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.start_time is not None:
                duration = time.perf_counter() - self.start_time
                self.metrics_service.record_processing_time(self.market, duration)
            return False  # 예외를 전파
    
    def processing_timer(self, market: str) -> 'ProcessingTimer':
        """처리 시간 측정 Context Manager 생성
        
        사용 예:
            with metrics_service.processing_timer('krx'):
                # 처리 로직
                pass
        
        Args:
            market: 시장 (krx, us)
            
        Returns:
            ProcessingTimer: Context Manager
        """
        return self.ProcessingTimer(self, market)


# 싱글톤 인스턴스 export
metrics_service = MetricsService()


def start_metrics_server(port: int = 8090) -> None:
    """Prometheus 메트릭 HTTP 서버 시작
    
    Args:
        port: 서버 포트 (기본값: 8090)
    """
    try:
        start_http_server(port)
        logging.info(f"📊 Prometheus metrics server started on port {port}")
        logging.info(f"   Metrics endpoint: http://localhost:{port}/metrics")
    except OSError as e:
        if 'Address already in use' in str(e):
            logging.warning(f"⚠️ Port {port} already in use, metrics server may already be running")
        else:
            logging.error(f"❌ Failed to start metrics server: {e}")
            raise
