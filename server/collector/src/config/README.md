# Config Module

Config 모듈은 Finance City 데이터 수집기의 모든 설정을 중앙 집중식으로 관리합니다. 환경별 설정, 거래 시간, API 자격증명 등을 체계적으로 구성합니다.

## 📁 파일 구조

```
config/
├── __init__.py           # 모듈 내보내기  
├── base_config.py        # 기본 설정 클래스
├── trading_config.py     # 거래 관련 설정
└── README.md            # 이 파일
```

## 🏗️ 주요 컴포넌트

### Base Config (base_config.py)

시스템의 기본 설정을 관리합니다.

#### 주요 클래스

- **`AppConfig`**: 애플리케이션 전체 설정 (KIS API, Redis, 파일 경로 등)
- **`get_app_config()`**: 싱글톤 설정 인스턴스 반환
- **`reload_config()`**: 설정 강제 재로드

#### 주요 설정 항목

**KIS API 설정**
- kis_app_key, kis_app_secret: API 인증 정보
- kis_ws_url, kis_api_base_url: API 엔드포인트

**Redis 설정** 
- redis_host, redis_port: Redis 서버 정보
- redis_channel: 실시간 데이터 채널

**애플리케이션 설정**
- environment: 실행 환경 (development/staging/production)
- debug_mode: 디버그 모드 활성화
- revoke_token_on_exit: 종료 시 토큰 해제 여부

**파일 경로**
- stocks_csv_path: 종목 목록 CSV 파일 경로

#### 사용 예시

```python
from config import get_app_config

# 환경변수에서 설정 자동 로드
config = get_app_config()

# 설정 접근
print(f"API URL: {config.kis_api_base_url}")
print(f"Redis: {config.redis_host}:{config.redis_port}")
print(f"Environment: {config.environment}")

# 환경 체크
if config.is_development():
    print("개발 모드입니다")

# 특정 .env 파일 사용
config = get_app_config("/path/to/custom.env")

# 설정 재로드
from config import reload_config
config = reload_config()
```

### Trading Config (trading_config.py)

거래 관련 설정을 전담합니다.

#### 주요 클래스

- **`TradingConfig`**: 전체 거래 설정 통합
- **`MarketConfig`**: 시장별 설정 (시간대, 거래시간 등)
- **`ExchangeMapping`**: 거래소 코드 매핑 (US 주식용)
- **`MarketType`**: 시장 타입 열거형 (KRX_REGULAR, KRX_AFTER, US_REGULAR)
- **`get_trading_config()`**: 싱글톤 거래 설정 인스턴스 반환

#### 설정 항목들

**시장 설정**
- KRX: 정규장(09:00-15:30), 시간외(16:00-18:00)
- US: 24시간 활성화 (KIS API 특성상)

**거래소 매핑**
- NASDAQ: 야간(NAS), 주간(BAQ)
- NYSE: 야간(NYS), 주간(BAY)
- AMEX: 야간(AMS), 주간(BAA)

**써머타임 설정**
- 시작: 3월 둘째 일요일
- 종료: 11월 첫째 일요일

#### 사용 예시

```python
from config import TradingConfig

# 기본 설정으로 생성
config = TradingConfig.create_default(
    kis_app_key="your_app_key",
    kis_app_secret="your_app_secret"
)

# 시장 설정 가져오기
krx_config = config.get_market_config("KRX")
print(f"KRX 정규장: {krx_config.regular_hours}")

# 거래소 코드 가져오기
nasdaq_night = config.get_us_exchange_code("NASDAQ", is_day_trading=False)
print(f"NASDAQ 야간거래 코드: {nasdaq_night}")  # NAS
```

## 🔧 설정 구조

### 계층적 설정 관리

```python
AppConfig                    # 애플리케이션 전체 설정
├── KIS API 설정
│   ├── kis_app_key
│   ├── kis_app_secret
│   ├── kis_api_base_url
│   └── kis_ws_url
├── Redis 설정
│   ├── redis_host
│   ├── redis_port
│   └── redis_channel
├── 애플리케이션 설정
│   ├── environment
│   ├── debug_mode
│   └── revoke_token_on_exit
└── 파일 경로
    └── stocks_csv_path

TradingConfig               # 거래 전용 설정
├── 시장별 설정
│   ├── KRX
│   │   ├── 정규장 시간
│   │   ├── 시간외 시간
│   │   └── TR_ID 매핑
│   └── US
│       ├── 거래소 매핑
│       └── TR_ID
└── 써머타임 설정
    ├── 시작/종료 규칙
    └── 시간대 처리
```

### 환경별 설정

```bash
# .env 파일 예시
# KIS API 설정
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_API_BASE_URL=https://openapi.koreainvestment.com:9443  # 실제투자
KIS_WS_URL=ws://ops.koreainvestment.com:21000

# Redis 설정  
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_CHANNEL=stock:realtime

# 애플리케이션 설정
ENVIRONMENT=production
DEBUG=false
REVOKE_TOKEN_ON_EXIT=true
```

```bash
# development 환경 예시
ENVIRONMENT=development
KIS_API_BASE_URL=https://openapivts.koreainvestment.com:29443  # 모의투자
DEBUG=true
REVOKE_TOKEN_ON_EXIT=false
```

## 📋 사용 방법

### 1. 애플리케이션 설정 사용

```python
from config import get_app_config

# 싱글톤 인스턴스 가져오기 
config = get_app_config()

# API 설정 접근
api_url = config.kis_api_base_url
ws_url = config.kis_ws_url
app_key = config.kis_app_key

# Redis 설정 접근
redis_host = config.redis_host
redis_port = config.redis_port

# 환경 확인
if config.is_production():
    print("프로덕션 모드에서 실행 중")
```

### 2. 거래 설정 사용

```python
from config import get_trading_config

# 거래 설정 인스턴스 가져오기
trading_config = get_trading_config()

# 시장 설정 접근
krx_config = trading_config.get_market_config("KRX")
print(f"KRX 정규장: {krx_config.regular_hours}")

# 거래소 코드 가져오기
nasdaq_night = trading_config.get_us_exchange_code("NASDAQ", is_day_trading=False)
print(f"NASDAQ 야간거래 코드: {nasdaq_night}")  # NAS
```

### 3. 환경변수와 함께 사용

```bash
# .env 파일
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_secret_here
ENVIRONMENT=development
REDIS_HOST=redis.example.com
REDIS_PORT=6379
```

```python
from config import get_app_config, reload_config

# 자동으로 .env 파일에서 로드
config = get_app_config()

# 특정 환경파일 사용
config = get_app_config("/path/to/staging.env")

# 설정 재로드 (환경변수 변경 후)
config = reload_config()
```

### 4. 커스텀 설정

```python
from config import TradingConfig, MarketConfig
from datetime import time

# 커스텀 시장 설정
custom_market = MarketConfig(
    name="CRYPTO",
    timezone="UTC",
    regular_hours=(time(0, 0), time(23, 59)),  # 24시간
    tr_ids={"regular": "CRYPTO_TR_ID"}
)

# 기존 설정에 추가
trading_config = TradingConfig.create_default()
trading_config.markets["CRYPTO"] = custom_market
```

## 🔧 설정 확장

### 새로운 시장 추가

1. `MarketConfig` 객체 생성
2. `TradingConfig.markets`에 추가
3. 필요한 경우 새로운 TR_ID 매핑 추가

```python
def add_crypto_market(config: TradingConfig):
    crypto_config = MarketConfig(
        name="CRYPTO",
        timezone="UTC", 
        regular_hours=(time(0, 0), time(23, 59)),
        tr_ids={"regular": "CRYPTO_REALTIME"}
    )
    
    config.markets["CRYPTO"] = crypto_config
```

### 새로운 거래소 추가

1. `ExchangeMapping` 객체 생성
2. `TradingConfig.exchanges`에 추가

```python
def add_new_exchange(config: TradingConfig):
    new_exchange = ExchangeMapping(
        name="CBOE",
        night_code="CBO", 
        day_code="CBE"
    )
    
    config.exchanges["CBOE"] = new_exchange
```

## ⚙️ 설정 검증

### 자동 검증

설정 로드 시 자동으로 유효성을 검증합니다.

```python
from config import get_app_config, AppConfig

try:
    config = get_app_config()
    print("설정이 유효합니다")
except ValueError as e:
    print(f"설정 오류: {e}")

# 수동 검증
config = AppConfig.from_environment()
try:
    config.validate()
    print("검증 성공")
except ValueError as e:
    print(f"검증 실패: {e}")
```

#### 검증 항목

- **필수 필드**: KIS API 키와 시크릿 존재 여부
- **URL 형식**: API URL과 WebSocket URL 형식 검증
- **포트 범위**: Redis 포트 유효 범위 (1-65535)
- **환경값**: 유효한 환경값 (development/staging/production)

## 🧪 테스트

### 단위 테스트 예시

```python
import pytest
from config import get_app_config, get_trading_config, AppConfig, TradingConfig

def test_app_config_creation():
    """애플리케이션 설정 생성 테스트"""
    config = AppConfig.from_environment()
    
    assert hasattr(config, 'kis_app_key')
    assert hasattr(config, 'redis_host')
    assert config.redis_port > 0

def test_app_config_validation():
    """설정 검증 테스트"""
    config = AppConfig(
        kis_app_key="test_key",
        kis_app_secret="test_secret", 
        kis_ws_url="ws://test.com",
        kis_api_base_url="https://test.com",
        redis_host="localhost",
        redis_port=6379,
        redis_channel="test",
        environment="development",
        revoke_token_on_exit=False,
        debug_mode=True,
        stocks_csv_path="/test/stocks.csv"
    )
    
    # 검증 성공해야 함
    config.validate()

def test_trading_config_creation():
    """거래 설정 생성 테스트"""
    config = TradingConfig.create_default(
        kis_app_key="test_key",
        kis_app_secret="test_secret"
    )
    
    assert config.kis_app_key == "test_key"
    assert "KRX" in config.markets
    assert "US" in config.markets

def test_exchange_mapping():
    """거래소 매핑 테스트"""
    config = TradingConfig.create_default()
    
    nasdaq_night = config.get_us_exchange_code("NASDAQ", is_day_trading=False)
    nasdaq_day = config.get_us_exchange_code("NASDAQ", is_day_trading=True)
    
    assert nasdaq_night == "NAS"
    assert nasdaq_day == "BAQ"

def test_singleton_behavior():
    """싱글톤 동작 테스트"""
    config1 = get_app_config()
    config2 = get_app_config()
    
    # 같은 인스턴스여야 함
    assert config1 is config2
```

## 🔗 의존성

- **Python**: 3.8+
- **외부 라이브러리**: 
  - `python-dotenv`: 환경변수 파일 로딩

## 📚 관련 문서

- [Core README](../core/README.md) - 핵심 모델 및 인터페이스
- [Markets README](../markets/README.md) - 시장별 구현체
- [환경 설정 가이드](../../docs/environment-setup.md) - 환경변수 설정 방법
