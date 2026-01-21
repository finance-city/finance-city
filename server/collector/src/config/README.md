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

- **`BaseConfig`**: 모든 설정의 기본 클래스
- **`EnvironmentConfig`**: 환경별 설정 (development, production 등)

#### 특징

- 환경변수 자동 로딩
- 설정 유효성 검증
- 기본값 제공
- 타입 안전성

#### 사용 예시

```python
from config import BaseConfig

class MyConfig(BaseConfig):
    def __init__(self):
        super().__init__()
        self.my_setting = self.get_env("MY_SETTING", "default_value")
```

### Trading Config (trading_config.py)

거래 관련 설정을 전담합니다.

#### 주요 클래스

- **`MarketConfig`**: 시장별 설정 (시간대, 거래시간 등)
- **`ExchangeMapping`**: 거래소 코드 매핑 (US 주식용)
- **`TradingConfig`**: 전체 거래 설정 통합

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
TradingConfig
├── KIS API 설정
│   ├── kis_app_key
│   ├── kis_app_secret
│   ├── kis_api_base_url
│   └── kis_ws_url
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

```python
# development 환경
ENVIRONMENT=development
KIS_API_BASE_URL=https://openapivts.koreainvestment.com:29443  # 모의투자

# production 환경  
ENVIRONMENT=production
KIS_API_BASE_URL=https://openapi.koreainvestment.com:9443     # 실제투자
```

## 📋 사용 방법

### 1. 기본 설정 사용

```python
from config import get_trading_config

# 싱글톤 인스턴스 가져오기
config = get_trading_config()

# API 설정 접근
api_url = config.kis_api_base_url
ws_url = config.kis_ws_url
```

### 2. 환경변수와 함께 사용

```bash
# .env 파일
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_secret_here
ENVIRONMENT=development
```

```python
import os
from dotenv import load_dotenv
from config import TradingConfig

# 환경변수 로딩
load_dotenv()

# 설정 생성
config = TradingConfig.create_default(
    kis_app_key=os.getenv("KIS_APP_KEY", ""),
    kis_app_secret=os.getenv("KIS_APP_SECRET", "")
)
```

### 3. 커스텀 설정

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
config = TradingConfig.create_default()
config.markets["CRYPTO"] = custom_market
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

```python
def validate_config(config: TradingConfig) -> bool:
    """설정 유효성 검증"""
    
    # API 키 검증
    if not config.kis_app_key or not config.kis_app_secret:
        raise ValueError("KIS API credentials are required")
    
    # URL 검증
    if not config.kis_api_base_url.startswith(('http://', 'https://')):
        raise ValueError("Invalid API base URL")
    
    # 시장 설정 검증
    for market_name, market_config in config.markets.items():
        if not market_config.tr_ids:
            raise ValueError(f"No TR_IDs defined for market: {market_name}")
    
    return True
```

## 🧪 테스트

### 단위 테스트 예시

```python
import pytest
from config import TradingConfig, MarketConfig

def test_trading_config_creation():
    config = TradingConfig.create_default(
        kis_app_key="test_key",
        kis_app_secret="test_secret"
    )
    
    assert config.kis_app_key == "test_key"
    assert "KRX" in config.markets
    assert "US" in config.markets

def test_market_config():
    krx_config = MarketConfig(
        name="KRX",
        timezone="Asia/Seoul",
        regular_hours=(time(9, 0), time(15, 30)),
        tr_ids={"regular": "H0STCNT0"}
    )
    
    assert krx_config.name == "KRX"
    assert krx_config.tr_ids["regular"] == "H0STCNT0"

def test_exchange_mapping():
    config = TradingConfig.create_default()
    
    nasdaq_night = config.get_us_exchange_code("NASDAQ", is_day_trading=False)
    nasdaq_day = config.get_us_exchange_code("NASDAQ", is_day_trading=True)
    
    assert nasdaq_night == "NAS"
    assert nasdaq_day == "BAQ"
```

## 🔗 의존성

- **Python**: 3.8+
- **외부 라이브러리**: 없음 (표준 라이브러리만 사용)

## 📚 관련 문서

- [Core README](../core/README.md) - 핵심 모델 및 인터페이스
- [Markets README](../markets/README.md) - 시장별 구현체
- [환경 설정 가이드](../../docs/environment-setup.md) - 환경변수 설정 방법
