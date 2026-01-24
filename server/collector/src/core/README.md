# Core Module

Finance City 수집기의 핵심 인프라를 제공하는 모듈입니다. 모든 다른 모듈이 의존하는 기본 인터페이스, 데이터 모델, 예외 클래스, 의존성 주입 컨테이너를 포함합니다.

## 📁 파일 구조

```
core/
├── __init__.py            # DI 컨테이너 및 모듈 익스포트
├── models.py             # 데이터 모델 정의  
├── interfaces.py         # 서비스 인터페이스 정의
├── exceptions.py         # 커스텀 예외 클래스
├── service_container.py  # 의존성 주입 컨테이너
└── README.md            # 이 파일
```

## 🏗️ 주요 컴포넌트

### Service Container (service_container.py)

중앙집중식 의존성 주입 컨테이너를 제공합니다.

#### 특징
- **싱글톤 관리**: 서비스 인스턴스의 생명주기 관리
- **지연 초기화**: 필요할 때만 서비스 생성
- **타입 안전성**: 제네릭을 통한 타입 힌팅
- **설정 기반**: AppConfig를 통한 서비스 설정

#### 사용 예시
```python
from core import initialize_container, get_container
from core import IStockManager, IAuthManager

# 컨테이너 초기화
config = AppConfig.from_environment()
initialize_container(config)

# 서비스 가져오기
container = get_container()
stock_service = container.get(IStockManager)
auth_service = container.get(IAuthManager)
```

### Models (models.py)

시스템 전반에서 사용되는 데이터 모델들을 정의합니다.

#### 핵심 모델들
- **`StockInfo`**: 종목 정보 (코드, 이름, 시장, 상태)
- **`MarketData`**: 실시간 시장 데이터 (가격, 변화율, 거래량)
- **`MarketSession`**: 시장 세션 정보 (거래 시간, 타임존)  
- **`FieldConfig`**: 데이터 필드 매핑 설정
- **`MarketConfig`**: 시장 전체 설정
- **`AuthCredentials`**: API 인증 자격증명
- **`SystemStatus`**: 시스템 상태 정보
- **`RequestInfo`**: API 요청 정보 (TR_ID, 종목 목록, 요청 타입)
- **`ErrorInfo`**: 에러 정보 (에러 코드, 메시지, 컨텍스트)

#### 열거형 타입들
- **`MarketType`**: 지원 시장 (KRX, US, CRYPTO)
- **`TradingStatus`**: 거래 상태 (ACTIVE, INACTIVE, SUSPENDED, DELISTED)

#### 사용 예시
```python
from core import StockInfo, MarketData, MarketType, TradingStatus, RequestInfo, ErrorInfo

# 종목 정보 생성
stock = StockInfo(
    code="005930",
    name="삼성전자",
    market=MarketType.KRX.value,
    status=TradingStatus.ACTIVE.value
)

# 활성 상태 확인
if stock.is_active():
    print(f"Active stock: {stock.get_display_name()}")

# 요청 정보 생성
request_info = RequestInfo(
    tr_id="H0STCNT0",
    stocks=[stock],
    request_type="subscribe"
)

# 에러 정보 생성
error_info = ErrorInfo(
    error_code="INVALID_STOCK",
    error_message="Stock code not found",
    context={"stock_code": "INVALID"}
)
```

### Interfaces (interfaces.py)

시스템의 각 컴포넌트가 구현해야 하는 인터페이스들을 정의합니다.

#### 주요 인터페이스들

- **`IMarketProvider`**: 시장별 데이터 제공자 인터페이스
- **`IStockManager`**: 종목 관리 인터페이스
- **`IRequestBuilder`**: API 요청 생성 인터페이스
- **`IDataParser`**: 데이터 파싱 인터페이스
- **`ITimeCalculator`**: 시간 계산 인터페이스
- **`IAuthManager`**: 인증 관리 인터페이스
- **`IWebSocketManager`**: WebSocket 연결 관리 인터페이스
- **`IMarketManager`**: 다중 시장 관리 인터페이스
- **`ICollectorOrchestrator`**: 전체 수집기 조율 인터페이스

#### 인터페이스 기반 설계의 장점

- **테스트 용이성**: Mock 객체를 쉽게 생성 가능
- **느슨한 결합**: 구현체 변경 시 다른 컴포넌트에 영향 최소화
- **확장성**: 새로운 시장이나 기능 추가 시 기존 코드 수정 불필요

### Exceptions (exceptions.py)

시스템 전반에서 사용되는 커스텀 예외 클래스들을 정의합니다.

#### 예외 계층 구조

```
CollectorError (기본)
├── ConfigurationError      # 설정 관련 오류
├── AuthenticationError     # 인증 관련 오류
├── MarketError            # 시장 관련 오류
│   └── StockCodeError     # 종목 코드 오류
├── WebSocketError         # WebSocket 관련 오류
├── DataParsingError       # 데이터 파싱 오류
├── APIError              # API 호출 오류
├── TimeoutError          # 타임아웃 오류
├── ValidationError       # 데이터 검증 오류
├── ServiceError          # 서비스 오류
├── InitializationError   # 초기화 오류
└── ResourceError         # 리소스 접근 오류
```

#### 사용 예시

```python
from core import raise_invalid_stock_code, AuthenticationError

# 편의 함수 사용
raise_invalid_stock_code("INVALID", "US")

# 직접 예외 생성
raise AuthenticationError(
    "Token has expired", 
    auth_type="token"
)
```

## 🔧 사용 방법

### 1. 모듈 임포트

```python
# 전체 모듈 임포트
from core import *

# 특정 컴포넌트 임포트
from core import StockInfo, IMarketProvider, CollectorError
```

### 2. 인터페이스 구현

```python
from core import IMarketProvider, MarketConfig

class MyMarketProvider(IMarketProvider):
    def get_market_name(self) -> str:
        return "MY_MARKET"
    
    def get_tr_id(self) -> str:
        return "MY_TR_ID"
    
    # 다른 메서드들 구현...
```

### 3. 예외 처리

```python
from core import CollectorError, AuthenticationError

try:
    # 어떤 작업 수행
    pass
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
    print(f"Error context: {e.context}")
except CollectorError as e:
    print(f"General error: {e}")
```

## 📋 개발 지침

### 새로운 모델 추가

1. `models.py`에 dataclass로 정의
2. 적절한 타입 힌트 사용
3. `to_dict()` 메서드 제공 (필요한 경우)
4. `__init__.py`에 export 추가

### 새로운 인터페이스 추가

1. `interfaces.py`에 ABC 상속받아 정의
2. 모든 메서드에 `@abstractmethod` 데코레이터 적용
3. 명확한 독스트링 제공
4. `__init__.py`에 export 추가

### 새로운 예외 추가

1. `exceptions.py`에 적절한 부모 클래스 상속받아 정의
2. 컨텍스트 정보 포함하도록 생성자 구현
3. 편의 함수 제공 (필요한 경우)
4. `__init__.py`에 export 추가

## 🧪 테스트

```python
# 모델 테스트 예시
def test_stock_info():
    stock = StockInfo(
        code="AAPL",
        name="Apple Inc.",
        market="US",
        status="active"
    )
    
    assert stock.is_active() == True
    assert stock.get_display_name() == "AAPL (Apple Inc.)"

def test_request_info():
    stock = StockInfo(code="005930", name="삼성전자", market="KRX", status="active")
    request = RequestInfo(
        tr_id="H0STCNT0",
        stocks=[stock],
        request_type="subscribe"
    )
    
    assert request.get_stock_codes() == ["005930"]
    assert request.request_type == "subscribe"

def test_error_info():
    error = ErrorInfo(
        error_code="TEST_ERROR",
        error_message="Test error message",
        context={"test": "value"}
    )
    
    assert str(error) == "[TEST_ERROR] Test error message"
    assert error.context["test"] == "value"

# 예외 테스트 예시
def test_custom_exceptions():
    with pytest.raises(AuthenticationError) as exc_info:
        raise_auth_token_expired()
    
    assert exc_info.value.error_code == "AUTH_ERROR"
    assert "token" in exc_info.value.context
```

## 🔗 의존성

- **Python**: 3.8+
- **외부 라이브러리**: 없음 (표준 라이브러리만 사용)

## 📚 관련 문서

- [ARCHITECTURE_V1.md](../../ARCHITECTURE_V1.md) - 전체 아키텍처 문서
- [Markets README](../markets/README.md) - 시장 모듈 문서
- [Services README](../services/README.md) - 서비스 모듈 문서
