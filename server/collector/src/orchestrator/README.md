# Orchestrator Module

전체 데이터 수집 프로세스를 통합 관리하는 오케스트레이션 모듈입니다. 기존 collector.py의 거대한 main() 함수를 역할별로 분리하여 체계적으로 관리합니다.

## 📁 파일 구조

```
orchestrator/
├── __init__.py                   # 모듈 익스포트
├── collector_orchestrator.py    # 메인 오케스트레이터
└── README.md                    # 이 파일
```

## 🎼 주요 컴포넌트

### CollectorOrchestrator

실시간 주식 수집기의 전체 생명주기를 관리하는 핵심 클래스입니다.

#### 실행 단계

1. **Initialize**: 설정 로드, DI 컨테이너, 서비스 초기화
2. **Validate**: 종목, 시장, 세션 유효성 검증  
3. **Setup Subscriptions**: WebSocket 연결, 종목 구독 설정
4. **Run**: 실시간 데이터 수집 및 처리 (블로킹)
5. **Cleanup**: 리소스 해제 및 정리

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
- 테스트용 Mock 서비스 교체 가능

**에러 핸들링**
- 각 단계별 실패 시 적절한 롤백
- 시그널 핸들러를 통한 안전한 종료
- 리소스 누수 방지

**상태 관리**
- 실시간 수집 상태 추적
- 연결 상태 모니터링  
- 구독 종목 관리

#### 사용 예시

**기본 실행**
```python
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
            
        # 실행 (블로킹)
        orchestrator.run()
        
        return 0
        
    except Exception as e:
        logging.error(f"실행 오류: {e}")
        return 1
```

**커스텀 설정**
```python
# 특정 설정으로 실행
custom_config = AppConfig(
    kis_app_key="custom_key",
    kis_app_secret="custom_secret",
    environment="development"
)

orchestrator = CollectorOrchestrator(custom_config)
```

## 🔧 DI 서비스 통합

오케스트레이터는 다음 서비스들을 DI 컨테이너에서 가져와 사용합니다:

| 서비스 | 인터페이스 | 역할 |
|--------|-----------|------|
| **Stock Service** | `IStockManager` | 종목 관리 및 필터링 |
| **Market Manager** | `IMarketManager` | 시장별 프로바이더 관리 |
| **Request Builder** | `IRequestBuilder` | API 요청 생성 |
| **Auth Manager** | `IAuthManager` | KIS API 인증 |
| **Data Parser** | `IDataParser` | 실시간 데이터 파싱 |
| **WebSocket Manager** | `IWebSocketManager` | WebSocket 연결 관리 |

## ⚠️ 주의사항

**Redis 의존성**
- 토큰 캐싱을 위해 Redis 클라이언트 사용
- Redis 연결 실패 시에도 동작하도록 fallback 필요

**시그널 처리**
- SIGINT, SIGTERM 시그널에 대한 graceful shutdown
- 모든 리소스의 안전한 해제

**에러 복구**
- WebSocket 연결 끊김 시 자동 재연결
- API 인증 토큰 만료 시 자동 갱신
- 일시적 네트워크 오류에 대한 재시도

## 📊 모니터링

**로깅**
- 각 단계별 진행 상황 로깅
- 에러 발생 시 상세 로그
- 성능 메트릭 수집

**상태 추적**
- 활성 종목 수
- WebSocket 연결 상태
- 수신 메시지 수
- 에러 발생 횟수

## 🧪 테스트

**단위 테스트**
```python
import pytest
from unittest.mock import Mock
from orchestrator import CollectorOrchestrator

def test_orchestrator_initialization():
    mock_config = Mock()
    orchestrator = CollectorOrchestrator(mock_config)
    
    # Mock 서비스들 주입
    orchestrator.container = Mock()
    
    assert orchestrator.initialize() == True

def test_validation_with_no_stocks():
    orchestrator = create_test_orchestrator()
    orchestrator.stock_service.get_active_stocks.return_value = []
    
    assert orchestrator.validate() == False
```

**통합 테스트**
```python
def test_full_workflow():
    config = AppConfig.create_test_config()
    orchestrator = CollectorOrchestrator(config)
    
    # 전체 워크플로우 테스트
    assert orchestrator.initialize() == True
    assert orchestrator.validate() == True
    assert orchestrator.setup_subscriptions() == True
```

## 🔗 의존성

**내부 모듈**
- `config`: 설정 관리
- `core`: 인터페이스 및 DI 컨테이너
- 모든 서비스 모듈들

**외부 라이브러리**
- `redis`: 토큰 캐싱
- `websockets`: 실시간 데이터 수신
- `requests`: HTTP API 호출

## 📚 관련 문서

- [Core README](../core/README.md) - DI 컨테이너 및 인터페이스
- [Services README](../services/README.md) - 비즈니스 로직 서비스들
- [Config README](../config/README.md) - 설정 관리
