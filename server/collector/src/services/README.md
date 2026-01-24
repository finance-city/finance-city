# Services Module

비즈니스 로직과 외부 API 연동을 담당하는 서비스 레이어입니다. 각 서비스는 단일 책임을 가지며 인터페이스를 통해 상호작용하여 테스트 가능하고 확장 가능한 구조를 제공합니다.

## 📁 파일 구조

```
services/
├── __init__.py           # 서비스 모듈 익스포트
├── auth_service.py       # KIS API 인증 및 토큰 관리
├── stock_service.py      # 종목 관리 및 필터링
├── request_builder.py    # API 요청 생성 (미구현)
├── time_calculator.py    # 시간 계산 서비스 (미구현)
└── README.md            # 이 파일
```

## 🏗️ 구현된 서비스

### AuthService (auth_service.py)

KIS API 인증 및 토큰 관리를 담당하는 핵심 서비스입니다.

#### 핵심 기능

- **토큰 관리**: access_token 자동 발급 및 갱신
- **Redis 캐싱**: 토큰 캐싱으로 API 호출 최소화
- **Approval Key**: WebSocket 접속용 approval_key 관리
- **토큰 검증**: 토큰 유효성 및 만료 시간 확인
- **에러 처리**: 인증 실패 시 적절한 예외 발생

#### 사용 예시

```python
from services import AuthService
from config import TradingConfig
import redis

# 설정 및 Redis 클라이언트
config = TradingConfig.create_default()
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# 인증 서비스 초기화
auth_service = AuthService(config, redis_client)

# 액세스 토큰 획득
access_token = auth_service.get_access_token()
print(f"Access Token: {access_token}")

# Approval Key 획득 (WebSocket용)
approval_key = auth_service.get_approval_key()
print(f"Approval Key: {approval_key}")

# 토큰 유효성 검증
is_valid = auth_service.is_token_valid()
print(f"토큰 유효함: {is_valid}")
```

#### 캐싱 전략

**Access Token**
- 캐시 키: `kis:auth:access_token:{app_key}`
- TTL: 토큰 만료시간 - 5분 (안전 마진)
- 자동 갱신: 만료 5분 전 자동 갱신

**Approval Key**  
- 캐시 키: `kis:auth:approval:{app_key}`
- TTL: 24시간
- 갱신 주기: 매일 자동 갱신

#### 에러 처리

```python
from core import AuthenticationError

try:
    token = auth_service.get_access_token()
except AuthenticationError as e:
    print(f"인증 실패: {e}")
    # 재시도 로직 또는 알림
```

### StockService (stock_service.py)

종목 정보 관리 및 필터링을 담당하는 서비스입니다.

#### 핵심 기능

- **CSV 로딩**: stocks.csv 파일에서 종목 정보 로드
- **시장별 필터링**: KRX, US 시장별 종목 분리
- **상태 관리**: 활성/비활성 종목 구분
- **종목 검색**: 코드 또는 이름으로 종목 검색
- **동적 추가/제거**: 런타임 종목 추가/제거

#### 사용 예시

```python
from services import StockService

# 종목 서비스 초기화
stock_service = StockService("path/to/stocks.csv")

# 종목 데이터 로드
stock_service.load_stocks()

# 활성 종목 조회
active_stocks = stock_service.get_active_stocks()
print(f"활성 종목 수: {len(active_stocks)}")

# KRX 시장 종목만 조회
krx_stocks = stock_service.get_stocks_by_market("KRX")
print(f"KRX 종목 수: {len(krx_stocks)}")

# 특정 종목 확인
is_active = stock_service.is_stock_active("005930")
print(f"삼성전자 활성 상태: {is_active}")
```

#### 데이터 구조

**stocks.csv 형식**
```csv
code,name,market,status,exchange
005930,삼성전자,KRX,active,
000660,SK하이닉스,KRX,active,
AAPL,Apple Inc.,US,active,NASDAQ
MSFT,Microsoft Corp.,US,active,NASDAQ
```

**StockInfo 객체**
```python
@dataclass
class StockInfo:
    code: str          # 종목 코드
    name: str          # 종목명
    market: str        # 시장 (KRX, US)
    status: str        # 상태 (active, inactive)
    exchange: Optional[str] = None  # 거래소 (NASDAQ, NYSE, AMEX)
```

## 📋 미구현 서비스

### RequestBuilderService (request_builder.py)

KIS API 요청 패킷을 동적으로 생성하는 서비스입니다.

#### 계획된 기능

- **동적 TR_ID 선택**: 시장별로 적절한 TR_ID 자동 선택
- **종목 코드 변환**: 시장별 종목 코드 포맷팅
- **구독/구독취소**: WebSocket 구독 요청 생성
- **세션 기반 포맷팅**: 미국 주식의 야간/주간 거래 자동 처리

#### 요청 패킷 구조 (예상)

```json
{
  "header": {
    "approval_key": "approval_key_here",
    "custtype": "P",
    "tr_type": "1",
    "content-type": "utf-8"
  },
  "body": {
    "input": {
      "tr_id": "H0STCNT0",
      "tr_key": "005930^000660^005490"
    }
  }
}
```

### TimeCalculatorService (time_calculator.py)

시장 시간 관련 계산을 담당하는 서비스입니다.

#### 계획된 기능

- **DST 계산**: 미국 써머타임 자동 감지
- **시장 시간 변환**: 시장별 시간대 변환
- **거래시간 확인**: 현재 시간이 거래시간인지 판단
- **세션 유형 결정**: 미국 주식의 야간/주간 거래 구분

## ⚠️ 주의사항

**Redis 의존성**
- AuthService는 Redis 캐싱을 사용하지만 선택적
- Redis 연결 실패 시에도 기본 동작 가능하도록 구현됨
- 프로덕션 환경에서는 Redis 사용 강력히 권장

**토큰 관리**
- access_token은 24시간 유효 (KIS API 정책)
- approval_key는 웹소켓 연결마다 새로 발급 권장
- 토큰 만료 5분 전 자동 갱신으로 서비스 중단 방지

**종목 데이터**
- CSV 파일 구조 변경 시 StockService 수정 필요
- 대량 종목 처리 시 메모리 사용량 고려
- 종목 추가/삭제 시 WebSocket 구독도 동기화 필요

## 🧪 테스트

**AuthService 테스트**
```python
import pytest
from unittest.mock import Mock, patch
from services import AuthService

@patch('redis.Redis')
def test_auth_service_without_redis(mock_redis):
    mock_redis.return_value = None
    auth_service = AuthService(mock_config, None)
    
    # Redis 없이도 동작해야 함
    token = auth_service.get_access_token()
    assert token is not None

def test_token_caching():
    auth_service = AuthService(config, redis_client)
    
    # 첫 번째 호출
    token1 = auth_service.get_access_token()
    
    # 두 번째 호출 (캐시에서 가져와야 함)
    token2 = auth_service.get_access_token()
    
    assert token1 == token2
```

**StockService 테스트**
```python
def test_stock_loading():
    stock_service = StockService("test_stocks.csv")
    stock_service.load_stocks()
    
    active_stocks = stock_service.get_active_stocks()
    assert len(active_stocks) > 0

def test_market_filtering():
    stock_service = StockService("test_stocks.csv")
    stock_service.load_stocks()
    
    krx_stocks = stock_service.get_stocks_by_market("KRX")
    us_stocks = stock_service.get_stocks_by_market("US")
    
    assert all(stock.market == "KRX" for stock in krx_stocks)
    assert all(stock.market == "US" for stock in us_stocks)
```

## 🔗 의존성

**내부 모듈**
- `core`: 인터페이스 및 데이터 모델
- `config`: 설정 관리

**외부 라이브러리**
- `redis`: 토큰 캐싱 (선택적)
- `requests`: HTTP API 호출
- `pandas`: CSV 데이터 처리 (StockService)

## 📚 관련 문서

- [Core README](../core/README.md) - 인터페이스 및 데이터 모델
- [Config README](../config/README.md) - 설정 관리
- [Data README](../data/README.md) - 데이터 처리 및 WebSocket
