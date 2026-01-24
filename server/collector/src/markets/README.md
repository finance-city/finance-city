# Markets Module

다양한 금융 시장별 특화 기능을 제공하는 모듈입니다. 각 시장의 고유한 거래 시간, 종목 코드 형식, API 매핑을 처리하여 시장별 차이를 추상화합니다.

## 📁 파일 구조

```
markets/
├── __init__.py         # 마켓 프로바이더 익스포트
├── base.py            # 베이스 마켓 프로바이더 추상 클래스
├── krx.py             # 한국 거래소 (KOSPI/KOSDAQ) 구현
├── us.py              # 미국 시장 (NASDAQ/NYSE/AMEX) 구현  
└── README.md          # 이 파일
```

## 🏗️ 아키텍처

### BaseMarketProvider (base.py)

모든 시장 프로바이더의 기본 추상 클래스입니다.

#### 핵심 인터페이스

```python
class BaseMarketProvider(IMarketProvider):
    """시장 프로바이더 기본 클래스"""
    
    # 필수 구현 메서드
    @abstractmethod
    def get_market_name() -> str
    def get_tr_id() -> str
    def parse_stock_code(code: str) -> Optional[str]
    def format_stock_code(code: str, is_night_trading: bool) -> str
    
    # 공통 기능 제공
    def get_session_config() -> MarketSession
    def get_field_config() -> FieldConfig
    def is_market_open(current_time: datetime) -> bool
    def validate_stock_code_format(code: str, pattern: str) -> bool
```

#### 설정 관리

```python
# 각 프로바이더는 고유한 MarketConfig를 가집니다
config = MarketConfig(
    name="KRX",
    timezone="Asia/Seoul",
    sessions={
        "regular": MarketSession("09:00", "15:30"),
        "after_hours": MarketSession("16:00", "18:00")
    },
    tr_ids={
        "regular": "H0STCNT0",
        "after_hours": "H0NXCNT0"
    }
)
```

### KRX Market Provider (krx.py)

한국 거래소(KRX) 전용 구현체입니다.

#### 지원 기능

**거래 세션**
- 정규장: 09:00-15:30 (H0STCNT0)
- 시간외: 16:00-18:00 (H0NXCNT0)
- 동적 세션 전환 지원

**종목 코드**
- 6자리 숫자 형식 (예: 005930)
- KOSPI/KOSDAQ 구분 (첫 자리 기준)
- 코드 유효성 검증

**거래소 지원**
- KOSPI (코드: J)
- KOSDAQ (코드: Q)

#### 사용 예시

```python
from markets import KRXMarketProvider

# 정규장 프로바이더
krx_regular = KRXMarketProvider(use_after_hours=False)

# 시간외 프로바이더  
krx_after = KRXMarketProvider(use_after_hours=True)

# 종목 코드 검증
valid_code = krx_regular.parse_stock_code("005930")  # "005930"
invalid_code = krx_regular.parse_stock_code("AAPL")  # None

# 거래소 구분
is_kospi = krx_regular.is_kospi_stock("005930")     # True
is_kosdaq = krx_regular.is_kosdaq_stock("035420")   # True

# 동적 세션 전환
krx_regular.switch_to_after_hours()
print(krx_regular.get_tr_id())  # "H0NXCNT0"
```

### US Market Provider (us.py)

미국 시장(NASDAQ/NYSE/AMEX) 전용 구현체입니다.

#### 고급 기능

**써머타임 자동 계산**
- DST 기간 자동 감지 (3월 둘째 일요일 ~ 11월 첫째 일요일)
- 한국 시간 기준 미국 시장 시간 계산

**거래 세션 관리**
- 야간거래: 한국 시장 시간대 (D + 거래소코드)
- 주간거래: 미국 시장 시간대 (R + 거래소코드)
- 자동 세션 감지

**종목 코드 변환**
- 심볼 → KIS 포맷 변환 (AAPL → DNASAAPL)
- KIS 포맷 → 심볼 파싱 (DNASAAPL → AAPL)
- 거래소별 코드 생성

#### 거래소별 코드 매핑

| 거래소 | 야간거래 | 주간거래 | 예시 |
|--------|----------|----------|------|
| NASDAQ | NAS | BAQ | DNASAAPL, RBAQAAPL |
| NYSE | NYS | BAY | DNYSTSLA, RBAYTSLA |
| AMEX | AMS | BAA | DAMSSPDR, RBAASPDR |

#### 사용 예시

```python
from markets import USMarketProvider
from datetime import datetime

us_provider = USMarketProvider()

# 써머타임 확인
is_dst = us_provider.is_dst_period()
print(f"현재 DST 여부: {is_dst}")

# 거래 세션 정보
session_info = us_provider.get_trading_session_info()
print(f"세션 타입: {session_info['session_type']}")
print(f"시간대: {session_info['timezone']}")

# 종목 코드 변환
# 현재 시간 기준 자동 세션 결정
formatted_aapl = us_provider.format_stock_code_with_session("AAPL")
print(f"AAPL 포맷: {formatted_aapl}")  # DNASAAPL 또는 RBAQAAPL

# 수동 세션 지정
night_trading = us_provider.format_stock_code("MSFT", is_night_trading=True)
day_trading = us_provider.format_stock_code("MSFT", is_night_trading=False)
print(f"MSFT 야간: {night_trading}")  # DNASMSFT
print(f"MSFT 주간: {day_trading}")    # RBAQMSFT

# KIS 코드 파싱
symbol, exchange, session = us_provider.parse_kis_formatted_code("DNASAAPL")
print(f"심볼: {symbol}, 거래소: {exchange}, 세션: {session}")
# 심볼: AAPL, 거래소: NASDAQ, 세션: night
```

## 🔧 시장 추가 가이드

### 새로운 시장 추가하기

1. **새 파일 생성** (예: `crypto.py`)

```python
from .base import BaseMarketProvider
from ..core import MarketConfig, MarketSession, FieldConfig

class CryptoMarketProvider(BaseMarketProvider):
    @classmethod
    def create_default_config(cls) -> MarketConfig:
        session = MarketSession(
            start_time="00:00",
            end_time="23:59",
            timezone="UTC"
        )
        
        fields = FieldConfig(
            fields={
                "symbol": "0",
                "price": "1", 
                "volume": "2"
            },
            required_fields=["symbol", "price"],
            optional_fields=["volume"]
        )
        
        return MarketConfig(
            name="CRYPTO",
            tr_id="CRYPTO_RT",
            session=session,
            fields=fields
        )
    
    def parse_stock_code(self, code: str) -> Optional[str]:
        # 암호화폐 심볼 검증 로직
        if self.validate_stock_code_format(code, r'^[A-Z]{3,10}$'):
            return code.upper()
        return None
    
    def format_stock_code(self, code: str, is_night_trading: bool = False) -> str:
        # 암호화폐는 24시간이므로 야간거래 구분 불필요
        return self.parse_stock_code(code) or code
```

2. **`__init__.py`에 추가**

```python
from .crypto import CryptoMarketProvider

__all__ = [
    "BaseMarketProvider",
    "KRXMarketProvider", 
    "USMarketProvider",
    "CryptoMarketProvider"  # 새로 추가
]
```

## 📊 시장별 특성 요약

### KRX (한국 거래소)

- **시간대**: Asia/Seoul (UTC+9)
- **거래시간**: 09:00-15:30 (정규), 16:00-18:00 (시간외)
- **종목코드**: 6자리 숫자 (005930, 035420 등)
- **특징**: KOSPI/KOSDAQ 구분, 시간외 거래 지원

### US Markets (미국 시장)

- **시간대**: America/New_York (UTC-5/-4, DST 적용)
- **거래시간**: KIS API를 통해 24시간 접근 가능
- **종목코드**: 1-5자 알파벳 (AAPL, MSFT 등)
- **특징**: 써머타임 자동 처리, 거래소별 코드 변환

## 🧪 테스트 예시

### KRX 테스트

```python
def test_krx_provider():
    krx = KRXMarketProvider()
    
    # 종목 코드 검증
    assert krx.parse_stock_code("005930") == "005930"
    assert krx.parse_stock_code("AAPL") is None
    
    # 거래소 구분
    assert krx.is_kospi_stock("005930") == True
    assert krx.is_kosdaq_stock("035420") == True
    
    # 설정 확인
    assert krx.get_market_name() == "KRX"
    assert krx.get_tr_id() == "H0STCNT0"
```

### US 테스트

```python
def test_us_provider():
    us = USMarketProvider()
    
    # 종목 코드 변환
    assert "AAPL" in us.format_stock_code("AAPL")
    
    # KIS 코드 파싱
    result = us.parse_kis_formatted_code("DNASAAPL")
    assert result[0] == "AAPL"
    assert result[1] == "NASDAQ"
    assert result[2] == "night"
    
    # 설정 확인
    assert us.get_market_name() == "US"
    assert us.get_tr_id() == "HDFSCNT0"
```

## 🔗 의존성

- **Python**: 3.8+
- **Core 모듈**: 인터페이스 및 데이터 모델
- **외부 라이브러리**: 
  - `pytz` (시간대 처리, US 시장용)
  - `re` (정규식, 종목 코드 검증용)

## 📚 관련 문서

- [Core README](../core/README.md) - 기본 인터페이스 및 모델
- [Services README](../services/README.md) - 시장 프로바이더를 사용하는 서비스들
- [KIS API 문서](https://apiportal.koreainvestment.com/) - API 명세서
