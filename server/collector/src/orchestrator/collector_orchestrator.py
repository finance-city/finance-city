"""
CollectorOrchestrator: 실시간 주식 수집기의 역할 분리 오케스트레이터

collector.py의 거대한 main() 함수를 다음과 같이 역할별로 분리:
1. 초기화 (Config, DI Container, 서비스)
2. 검증 (종목, 시장, 세션 확인)
3. 구독 설정 (WebSocket 연결, 종목 구독)
4. 실행 (실시간 데이터 수집 및 처리)
5. 정리 (리소스 해제)
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Callable, Any
import signal
import sys

# 새로운 모듈 임포트
from config import AppConfig
from core import (
    initialize_container, get_container, cleanup_container, 
    IStockManager, IMarketManager, IRequestBuilder, IDataParser,
    IAuthManager, IWebSocketManager, ServiceContainer
)


class CollectorOrchestrator:
    """실시간 주식 수집 오케스트레이터
    
    거대한 main() 함수를 역할별로 분리하여 관리하는 클래스.
    의존성 주입과 중앙집중식 설정을 사용.
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        Args:
            config: 설정 객체. None이면 환경변수에서 로드.
        """
        self.config: Optional[AppConfig] = config
        self.container: Optional[ServiceContainer] = None
        
        # 새로운 DI 서비스들
        self.stock_service: Optional[IStockManager] = None
        self.market_manager: Optional[IMarketManager] = None
        self.request_builder: Optional[IRequestBuilder] = None
        self.auth_manager: Optional[IAuthManager] = None
        self.data_parser: Optional[IDataParser] = None
        self.ws_manager: Optional[IWebSocketManager] = None
        
        # Redis 클라이언트 (DI 컨테이너에서 가져옴)
        self.redis_client: Optional[Any] = None
        
        # 상태
        self.active_stocks: List[Any] = []
        self.krx_stocks: List[str] = []
        self.us_stocks: List[str] = []
        self.krx_tr_id: Optional[str] = None
        self.us_tr_id: Optional[str] = None
        self.is_running: bool = False
        
    def initialize(self) -> bool:
        """1. 초기화: 설정, 로깅, DI 컨테이너, 서비스들
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 설정 로드 및 검증
            if not self._load_and_validate_config():
                return False
            
            # 로깅 설정
            self._setup_logging()
            
            # DI 컨테이너 및 서비스 초기화
            if not self._initialize_services():
                return False
                
            # Redis 및 인증 초기화
            if not self._initialize_infrastructure():
                return False
                
            # 시그널 핸들러 설정
            self._setup_signal_handlers()
            
            logging.info("✅ CollectorOrchestrator 초기화 완료")
            return True
            
        except Exception as e:
            logging.error(f"❌ 초기화 실패: {e}")
            return False
    
    def validate(self) -> bool:
        """2. 검증: 종목 로드, 시장 분류, 세션 확인
        
        Returns:
            bool: 검증 성공 여부
        """
        try:
            # 종목 로드 및 분류
            if not self._load_and_classify_stocks():
                return False
            
            # 시장 세션 확인
            self._check_market_sessions()
            
            # 상태 리포트
            self._print_validation_report()
            
            logging.info("✅ 종목 및 시장 검증 완료")
            return True
            
        except Exception as e:
            logging.error(f"❌ 검증 실패: {e}")
            return False
    
    def setup_subscriptions(self) -> bool:
        """3. 구독 설정: WebSocket 연결, 종목 구독
        
        Returns:
            bool: 구독 설정 성공 여부
        """
        try:
            # 설정 및 서비스 검증
            if not self.config:
                logging.error("설정이 초기화되지 않음")
                return False
                
            if not self.ws_manager:
                logging.error("WebSocketManager가 초기화되지 않음")
                return False
            
            # 종목 구독 검증
            if not self.active_stocks:
                logging.warning("구독할 종목이 없습니다.")
                return False
            
            # WebSocket 연결 (비동기이므로 나중에 run()에서 처리)
            stock_codes = [stock.code for stock in self.active_stocks]
            
            # 구독 완료 리포트
            self._print_subscription_report(stock_codes)
            
            logging.info("✅ 구독 설정 완료")
            return True
            
        except Exception as e:
            logging.error(f"❌ 구독 설정 실패: {e}")
            return False
    
    def run(self) -> None:
        """4. 실행: 실시간 데이터 수집 및 처리"""
        try:
            self.is_running = True
            logging.info("🚀 실시간 데이터 수집 시작...")
            
            # 비동기 실행
            asyncio.run(self._async_run())
            
        except KeyboardInterrupt:
            logging.info("⏹️ 사용자 종료 요청")
        except Exception as e:
            logging.error(f"❌ 실행 중 오류: {e}")
        finally:
            self.is_running = False
    
    async def _async_run(self) -> None:
        """비동기 실행 메서드"""
        try:
            if not self.ws_manager:
                raise RuntimeError("WebSocketManager가 초기화되지 않았습니다")
            
            # WebSocket 연결
            await self.ws_manager.connect()
            
            # 종목 구독
            await self.ws_manager.subscribe_stocks(self.active_stocks)
            
            # 데이터 핸들러 설정
            async def data_handler(data):
                await self._handle_realtime_data(data)
            
            # 데이터 스트림 시작
            await self.ws_manager.start_data_stream(data_handler)
            
        except Exception as e:
            logging.error(f"비동기 실행 실패: {e}")
            raise
        finally:
            if self.ws_manager:
                await self.ws_manager.disconnect()
    
    async def _handle_realtime_data(self, data: Dict) -> None:
        """실시간 데이터 처리 핸들러"""
        try:
            # 데이터를 Redis로 발행
            if self.redis_client and self.config:
                # Redis 연결 상태 확인
                if not self._check_redis_connection():
                    logging.warning("Redis 연결이 끊어져 있어 데이터 발행을 건너뜁니다")
                    return
                
                channel = self.config.redis_channel
                message = json.dumps(data, ensure_ascii=False)
                
                # 메시지 크기 체크 (1MB 제한)
                if len(message.encode('utf-8')) > 1024 * 1024:
                    logging.warning(f"메시지가 너무 큽니다 ({len(message)} bytes), 발행을 건너뜁니다")
                    return
                
                self.redis_client.publish(channel, message)
                
                # 간단한 로깅 (통일된 필드명 사용)
                tr_id = data.get("tr_id", "UNKNOWN")
                # 통일된 데이터 구조에서 종목코드 가져오기
                code = data.get("data", {}).get("code", data.get("stock_code", "UNKNOWN"))
                logging.debug(f"데이터 발행: {tr_id}[{code}] → {channel}")
                
        except Exception as e:
            logging.error(f"실시간 데이터 처리 실패: {e}")
    
    def _check_redis_connection(self) -> bool:
        """Redis 연결 상태 확인"""
        try:
            if self.redis_client:
                self.redis_client.ping()
                return True
        except Exception as e:
            logging.error(f"Redis 연결 확인 실패: {e}")
        return False
    
    def cleanup(self) -> None:
        """5. 정리: 리소스 해제"""
        try:
            logging.info("🧹 리소스 정리 중...")
            
            # WebSocket 연결 종료 (비동기이지만 정리 시에는 강제 종료)
            if self.ws_manager:
                try:
                    # 비동기 메서드를 동기적으로 실행
                    if self.ws_manager.is_connected():
                        asyncio.run(self.ws_manager.disconnect())
                except:
                    pass
            
            # Redis 연결 종료
            if self.redis_client:
                try:
                    self.redis_client.close()
                except:
                    pass
            
            # 서비스 컨테이너 정리
            cleanup_container()
            
            logging.info("✅ 정리 완료")
            
        except Exception as e:
            logging.error(f"❌ 정리 중 오류: {e}")
    
    # === Private Methods ===
    
    def _load_and_validate_config(self) -> bool:
        """설정 로드 및 검증"""
        try:
            if self.config is None:
                self.config = AppConfig.from_environment()
            
            self.config.validate()
            print(f"✅ 설정 로드 완료 (환경: {self.config.environment})")
            return True
            
        except ValueError as e:
            print(f"❌ 설정 오류: {e}")
            return False
    
    def _setup_logging(self) -> None:
        """로깅 설정"""
        # 루트 로거가 이미 설정되어 있는지 확인
        root_logger = logging.getLogger()
        if root_logger.hasHandlers():
            # 이미 핸들러가 있다면 레벨만 조정
            root_logger.setLevel(
                logging.DEBUG if getattr(self.config, 'debug_mode', False) else logging.INFO
            )
            return
        
        # 새로 설정
        logging.basicConfig(
            level=logging.DEBUG if getattr(self.config, 'debug_mode', False) else logging.INFO,  # type: ignore
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def _initialize_services(self) -> bool:
        """DI 컨테이너 및 서비스 초기화"""
        try:
            # 서비스 컨테이너 초기화
            self.container = initialize_container(self.config)
            self.container.initialize_services()
            print("✅ 서비스 컨테이너 초기화 완료")
            
            # 디버그 정보
            if getattr(self.config, 'debug_mode', False):  # type: ignore
                health = self.container.health_check()
                print(f"📊 등록된 서비스: {health['registered_services']}개")
                print(f"📊 인스턴스화된 서비스: {health['active_instances']}개")
            
            # 새로운 서비스들
            self.stock_service = self.container.get(IStockManager)
            self.market_manager = self.container.get(IMarketManager)
            self.request_builder = self.container.get(IRequestBuilder)
            self.auth_manager = self.container.get(IAuthManager)
            self.data_parser = self.container.get(IDataParser)
            self.ws_manager = self.container.get(IWebSocketManager)
            
            return True
            
        except Exception as e:
            print(f"❌ 서비스 컨테이너 초기화 실패: {e}")
            return False
    
    def _initialize_infrastructure(self) -> bool:
        """Redis 및 인증 초기화"""
        try:
            # Redis 연결 (DI 컨테이너에서 가져오기)
            if not self.container:
                raise RuntimeError("DI 컨테이너가 초기화되지 않았습니다")
            
            # Redis 클라이언트를 DI 컨테이너에서 가져오기
            import redis  # 타입만 확인용으로 여기서 import
            self.redis_client = self.container.get(redis.Redis)
            
            # 연결 테스트 (None 체크 추가)
            if self.redis_client is not None:
                self.redis_client.ping()
                redis_host = getattr(self.config, 'redis_host', 'localhost')  # type: ignore
                redis_port = getattr(self.config, 'redis_port', 6379)  # type: ignore
                print(f"✅ Redis 연결: {redis_host}:{redis_port}")
            else:
                raise RuntimeError("Redis 클라이언트를 가져올 수 없습니다")
            
            # 환경설정 표시
            is_dev = getattr(self.config, 'is_development', lambda: False)()  # type: ignore
            revoke_token = getattr(self.config, 'revoke_token_on_exit', True)  # type: ignore
            if is_dev and not revoke_token:
                print("🔧 개발모드: 토큰 유지")
            else:
                print("🚀 운영모드: 종료 시 토큰 파기")
            
            # 인증 관리자는 서비스 초기화에서 이미 설정됨
            if self.auth_manager:
                # 종료 핸들러 추가
                # self.auth_manager.add_shutdown_handler(lambda: logging.info("WebSocket 연결 정리"))
                logging.info("✅ 인증 서비스 준비 완료")
            
            return True
            
        except Exception as e:
            print(f"❌ 인프라 초기화 실패: {e}")
            return False
    
    def _setup_signal_handlers(self) -> None:
        """시그널 핸들러 설정"""
        def signal_handler(signum, frame):
            logging.info(f"시그널 {signum} 수신, 정상 종료 중...")
            self.is_running = False
            self.cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _load_and_classify_stocks(self) -> bool:
        """종목 로드 및 시장별 분류"""
        try:
            # 종목 로드
            if self.stock_service:
                self.stock_service.load_stocks()  # type: ignore
                self.active_stocks = self.stock_service.get_active_stocks()  # type: ignore
            
            if not self.active_stocks:
                print("❌ 수집할 종목이 없습니다. stocks.csv 파일이나 환경변수를 확인하세요.")
                return False
            
            # 시장별 분류
            self.krx_stocks = []
            self.us_stocks = []
            
            for stock in self.active_stocks:
                if self.stock_service:
                    # 활성 종목에서 해당 종목을 찾아 시장 정보 확인
                    stock_info = next((s for s in self.stock_service.get_active_stocks() if s.code == stock.code), None)
                    if stock_info and hasattr(stock_info, 'market') and stock_info.market in ["US", "NASDAQ", "NYSE", "AMEX"]:
                        self.us_stocks.append(stock.code)
                    else:
                        self.krx_stocks.append(stock.code)
            
            return True
            
        except Exception as e:
            print(f"❌ 종목 로딩 실패: {e}")
            return False
    
    def _check_market_sessions(self) -> None:
        """시장 세션 확인"""
        if self.krx_stocks and self.request_builder:
            self.krx_tr_id = self.request_builder.get_current_tr_id(market_filter=["krx"])  # type: ignore
        
        if self.us_stocks and self.request_builder:
            self.us_tr_id = self.request_builder.get_current_tr_id(market_filter=["us"])  # type: ignore
    
    def _print_validation_report(self) -> None:
        """검증 리포트 출력"""
        stock_codes = [stock.code for stock in self.active_stocks]
        
        print(f"🔍 새로운 서비스 시스템 정보:")
        print(f"   - 활성화된 종목: {len(self.active_stocks)}개")
        print(f"   - 종목 코드: {stock_codes}")
        
        print(f"📊 종목 분류:")
        print(f"   - 한국 주식: {len(self.krx_stocks)}개 - {self.krx_stocks}")
        print(f"   - 미국 주식: {len(self.us_stocks)}개 - {self.us_stocks}")
        
        print(f"🕐 현재 세션 정보:")
        if self.krx_tr_id:
            print(f"   - 한국 시장: {self.krx_tr_id}")
        else:
            print(f"   - 한국 시장: 세션 없음 (한국 주식 {len(self.krx_stocks)}개)")
        
        if self.us_tr_id:
            print(f"   - 미국 시장: {self.us_tr_id}")
        else:
            print(f"   - 미국 시장: 세션 없음 (미국 주식 {len(self.us_stocks)}개)")
        
        if not self.krx_tr_id and not self.us_tr_id:
            print(f"   ⚠️ 활성 세션 없음, 기본 설정 사용")
    
    def _print_subscription_report(self, stock_codes: List[str]) -> None:
        """구독 리포트 출력"""
        stock_info_list = []
        for code in stock_codes:
            if self.stock_service:
                try:
                    stocks = self.stock_service.get_active_stocks()
                    stock_info = next((s for s in stocks if s.code == code), None)
                    if stock_info:
                        stock_info_list.append(f"{code}({stock_info.name})")
                    else:
                        stock_info_list.append(f"{code}(Unknown)")
                except Exception:
                    stock_info_list.append(f"{code}(Unknown)")
            else:
                stock_info_list.append(f"{code}(Unknown)")
        
        print(f"📡 구독 완료: {', '.join(stock_info_list)}")
        print(f"🔄 실시간 데이터 수집 중... (Ctrl+C로 종료)")
    
    # def _create_data_handler(self) -> Callable:
    #     """[LEGACY] 실시간 데이터 핸들러 생성 - 더이상 사용하지 않음"""
    #     # 이 메서드는 KISWebSocket과 함께 사용되던 레거시 코드
    #     # 새로운 WebSocketManager 방식에서는 async 핸들러를 사용함
    #     pass


def run_collector(config: Optional[AppConfig] = None) -> int:
    """편의 함수: CollectorOrchestrator를 사용해서 수집기 실행
    
    Args:
        config: 설정 객체. None이면 환경변수에서 로드.
        
    Returns:
        int: 종료 코드 (0=성공, 1=실패)
    """
    orchestrator = CollectorOrchestrator(config)
    
    try:
        # 1. 초기화
        if not orchestrator.initialize():
            return 1
        
        # 2. 검증
        if not orchestrator.validate():
            return 1
        
        # 3. 구독 설정
        if not orchestrator.setup_subscriptions():
            return 1
        
        # 4. 실행
        orchestrator.run()
        
        return 0
        
    except Exception as e:
        logging.error(f"❌ Orchestrator 실행 실패: {e}")
        return 1
        
    finally:
        # 5. 정리
        orchestrator.cleanup()
