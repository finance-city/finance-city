# Orchestrator Module

전체 데이터 수집 프로세스를 통합 관리하는 오케스트레이션 모듈입니다. 기존 collector.py의 거대한 main() 함수를 역할별로 분리하여 체계적으로 관리합니다.

## 📁 파일 구조

```
orchestrator/
├── __init__.py                   # 모듈 익스포트 (CollectorOrchestrator, run_collector)
├── collector_orchestrator.py    # 메인 오케스트레이터
└── README.md                    # 이 파일
```

## 🎼 주요 컴포넌트

### CollectorOrchestrator

실시간 주식 수집기의 전체 생명주기를 관리하는 핵심 클래스입니다.

#### 실행 단계

1. **Initialize**: 설정 로드/검증, DI 컨테이너, 서비스 초기화, Redis 연결
2. **Validate**: 종목 로드/분류, 시장 세션 확인, 검증 리포트 출력  
3. **Setup Subscriptions**: WebSocket 연결 준비, 종목 구독 설정
4. **Run**: 실시간 데이터 수집 및 처리 (비동기 블로킹)
5. **Cleanup**: WebSocket 연결 해제, 리소스 정리, 토큰 해제

#### 핵심 기능

**설정 및 초기화**
```python
from orchestrator import CollectorOrchestrator
from config import AppConfig

# 환경변수에서 설정 로드
config = AppConfig.from_environment()

# 오케스트레이터 생성  
orchestrator = CollectorOrchestrator(config)

# 초기화
if orchestrator.initialize():
    print("초기화 성공")
```

**의존성 주입**
- ServiceContainer를 통한 중앙집중식 서비스 관리
- 모든 서비스는 인터페이스를 통해 주입
- 서비스 헬스체크 및 디버그 정보 제공
- 테스트용 Mock 서비스 교체 가능

**비동기 실행**
- asyncio 기반 비동기 WebSocket 처리
- 실시간 데이터 스트림 핸들링
- 논블로킹 데이터 처리 파이프라인

**에러 핸들링**
- 각 단계별 실패 시 적절한 롤백
- 시그널 핸들러를 통한 안전한 종료
- 리소스 누수 방지

**상태 관리**
- 실시간 수집 상태 추적
- 연결 상태 모니터링  
- 구독 종목 관리
- 서비스별 개별 상태 추적
- 한국/미국 시장별 종목 분류

#### 사용 예시

**기본 실행 (편의 함수 사용)**
```python
from orchestrator import run_collector
from config import AppConfig

# 간단한 실행
if __name__ == "__main__":
    exit_code = run_collector()
    sys.exit(exit_code)

# 커스텀 설정으로 실행
custom_config = AppConfig.from_environment("custom.env")
exit_code = run_collector(custom_config)
```

**상세 제어 (직접 실행)**
```python
from orchestrator import CollectorOrchestrator
from config import AppConfig

def main():
    try:
        config = AppConfig.from_environment()
        orchestrator = CollectorOrchestrator(config)
        
        # 단계별 실행
        if not orchestrator.initialize():
            return 1
            
        if not orchestrator.validate():
            return 1
            
        if not orchestrator.setup_subscriptions():
            return 1
            
        # 실행 (비동기 블로킹)
        orchestrator.run()
        
        return 0
        
    except Exception as e:
        logging.error(f"실행 오류: {e}")
        return 1
    finally:
        orchestrator.cleanup()
```

**개발/디버깅 모드**
```python
# 디버그 정보 활성화
config = AppConfig.from_environment()
config.debug_mode = True

orchestrator = CollectorOrchestrator(config)
orchestrator.initialize()  # 서비스 헬스체크 정보 출력
```

## 🔧 DI 서비스 통합

오케스트레이터는 다음 서비스들을 DI 컨테이너에서 가져와 사용합니다:

| 서비스 | 인터페이스 | 역할 |
|--------|-----------|------|
| **Stock Service** | `IStockManager` | 종목 관리 및 필터링 |
| **Market Manager** | `IMarketManager` | 시장별 프로바이더 관리 |
| **Request Builder** | `IRequestBuilder` | API 요청 생성, TR_ID 결정 |
| **Auth Manager** | `IAuthManager` | KIS API 인증, 토큰 관리 |
| **Data Parser** | `IDataParser` | 실시간 데이터 파싱 |
| **WebSocket Manager** | `IWebSocketManager` | WebSocket 연결 관리 |
| **Redis Client** | `redis.Redis` | 데이터 캐싱 및 발행 |

## ⚠️ 주의사항

**Redis 의존성**
- 토큰 캐싱 및 실시간 데이터 발행을 위해 Redis 클라이언트 사용
- Redis 연결 실패 시에도 동작하도록 fallback 구현
- DI 컨테이너를 통한 Redis 클라이언트 자동 주입

**비동기 처리**
- asyncio 기반 WebSocket 연결 및 데이터 처리
- 실시간 데이터 스트림 핸들링
- 논블로킹 I/O 작업

**시그널 처리**
- SIGINT, SIGTERM 시그널에 대한 graceful shutdown
- 모든 리소스의 안전한 해제

**에러 복구**
- WebSocket 연결 끊김 시 자동 재연결
- API 인증 토큰 만료 시 자동 갱신
- 일시적 네트워크 오류에 대한 재시도

## 📊 모니터링

**로깅**
- 각 단계별 진행 상황 로깅 (초기화, 검증, 구독, 실행, 정리)
- 에러 발생 시 상세 로그
- 디버그 모드에서 서비스 헬스체크 정보 출력
- 성능 메트릭 수집

**상태 추적**
- 활성 종목 수 및 시장별 분류 (KRX/US)
- WebSocket 연결 상태
- 수신 메시지 수
- 에러 발생 횟수
- DI 컨테이너 서비스 상태

## 🧪 테스트

**단위 테스트**
```python
import pytest
from unittest.mock import Mock
from orchestrator import CollectorOrchestrator

def test_orchestrator_initialization():
    mock_config = Mock()
    mock_config.validate.return_value = None
    mock_config.debug_mode = False
    
    orchestrator = CollectorOrchestrator(mock_config)
    
    # Mock 서비스들 주입 테스트
    assert orchestrator.config == mock_config

def test_validation_with_no_stocks():
    orchestrator = create_test_orchestrator()
    orchestrator.stock_service = Mock()
    orchestrator.stock_service.get_active_stocks.return_value = []
    
    assert orchestrator.validate() == False

def test_run_collector_function():
    """편의 함수 테스트"""
    from orchestrator import run_collector
    
    # Mock 설정으로 테스트
    mock_config = create_mock_config()
    exit_code = run_collector(mock_config)
    
    assert exit_code in [0, 1]  # 성공 또는 실패
```

**통합 테스트**
```python
import asyncio
from orchestrator import CollectorOrchestrator

def test_full_workflow():
    config = AppConfig.create_test_config()
    orchestrator = CollectorOrchestrator(config)
    
    # 전체 워크플로우 테스트
    assert orchestrator.initialize() == True
    assert orchestrator.validate() == True
    assert orchestrator.setup_subscriptions() == True
    
    # cleanup 테스트
    orchestrator.cleanup()

@pytest.mark.asyncio
async def test_async_execution():
    """비동기 실행 테스트"""
    orchestrator = create_test_orchestrator()
    
    # 짧은 시간 실행 후 종료
    try:
        await asyncio.wait_for(
            orchestrator._async_run(), 
            timeout=1.0
        )
    except asyncio.TimeoutError:
        pass  # 예상된 타임아웃
```

## 🔗 의존성

**내부 모듈**
- `config`: 설정 관리
- `core`: 인터페이스 및 DI 컨테이너
- 모든 서비스 모듈들

**외부 라이브러리**
- `redis`: 토큰 캐싱 및 데이터 발행
- `asyncio`: 비동기 WebSocket 처리
- `websockets`: 실시간 데이터 수신
- `requests`: HTTP API 호출

## 📚 관련 문서

- [Core README](../core/README.md) - DI 컨테이너 및 인터페이스
- [Services README](../services/README.md) - 비즈니스 로직 서비스들
- [Config README](../config/README.md) - 설정 관리
