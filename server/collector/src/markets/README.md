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
    def parse_stock_code(code: str) -> Optional[str]
    def format_stock_code(code: str, is_night_trading: bool) -> str
    
    # 공통 기능 제공
    def get_market_name() -> str
    def get_tr_id() -> str
    def get_session_config() -> MarketSession
    def get_field_config() -> FieldConfig
    def is_market_open(current_time: datetime) -> bool
    def validate_stock_code_format(code: str, pattern: str) -> bool
    def get_exchange_code(exchange_name: str) -> Optional[str]
    def get_supported_exchanges() -> List[str]
    def is_trading_hours(current_time: Optional[datetime]) -> bool
    def get_market_config() -> MarketConfig
```

#### 설정 관리

```python
# 각 프로바이더는 고유한 MarketConfig를 가집니다
# KRX 예시
config = MarketConfig(
    name="KRX",
    tr_id="H0STCNT0",
    session=MarketSession(
        start_time="09:00",
        end_time="15:30",
        timezone="Asia/Seoul"
    ),
    fields=FieldConfig(
        fields={
            "stock_code": "0",
            "stock_name": "1", 
            "current_price": "2"
        },
        required_fields=["stock_code", "stock_name", "current_price"]
    ),
    exchange_codes={
        "KOSPI": "J",
        "KOSDAQ": "Q"
    }
)
```

### KRX Market Provider (krx.py)

한국 거래소(KRX) 전용 구현체입니다.

#### 지원 기능

**설정 팩토리 메서드**
- `create_default_config()`: 정규장 설정 생성
- `create_after_hours_config()`: 시간외 거래 설정 생성

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

# 설정 정보 접근
market_config = krx_regular.get_market_config()
print(f"TR ID: {krx_regular.get_tr_id()}")
print(f"시간외 모드: {krx_regular.is_after_hours_mode()}")

# 거래시간 확인
from datetime import datetime
now = datetime.now()
is_open = krx_regular.is_trading_hours(now)
```

### US Market Provider (us.py)

미국 시장(NASDAQ/NYSE/AMEX) 전용 구현체입니다.

#### 고급 기능

**거래소별 코드 매핑**
- NASDAQ: 야간(NAS), 주간(BAQ) 
- NYSE: 야간(NYS), 주간(BAY)
- AMEX: 야간(AMS), 주간(BAA)

**종목 코드 변환**
- 심볼 → KIS 포맷 변환 (AAPL → DNASAAPL)
- KIS 포맷 → 심볼 파싱 (DNASAAPL → AAPL)
- 자동 거래소 감지 및 세션 구분

**24시간 거래 지원**
- KIS API를 통해 24시간 접근 가능
- 실시간 세션 타입 감지
- 야간/주간 거래 자동 처리

#### 거래소별 코드 매핑

| 거래소 | 야간거래 | 주간거래 | 예시 |
|--------|----------|----------|------|
| NASDAQ | NAS | BAQ | DNASAAPL, RBAQAAPL |
| NYSE | NYS | BAY | DNYSTSLA, RBAYTSLA |
| AMEX | AMS | BAA | DAMSSPDR, RBAASPDR |

#### 사용 예시

```python
from markets import USMarketProvider

us_provider = USMarketProvider()

# 종목 코드 파싱 (심볼 추출)
symbol = us_provider.parse_stock_code("AAPL")      # "AAPL"
symbol2 = us_provider.parse_stock_code("DNASAAPL") # "AAPL"

# 코드 포맷팅 (야간/주간 구분)
night_code = us_provider.format_stock_code("AAPL", is_night_trading=True)
day_code = us_provider.format_stock_code("AAPL", is_night_trading=False)
print(f"야간: {night_code}")  # "DNASAAPL" 
print(f"주간: {day_code}")    # "RBAQAAPL"

# KIS 포맷 코드 파싱
result = us_provider.parse_kis_formatted_code("DNASAAPL")
if result:
    symbol, exchange, session = result
    print(f"심볼: {symbol}, 거래소: {exchange}, 세션: {session}")
    # 심볼: AAPL, 거래소: NASDAQ, 세션: night

# 거래소 코드 확인
nasdaq_night = us_provider.get_exchange_code("NASDAQ_NIGHT")  # "NAS"
nyse_day = us_provider.get_exchange_code("NYSE_DAY")          # "BAY"

# 지원 거래소 목록
exchanges = us_provider.get_supported_exchanges()
print(exchanges)  # ['NASDAQ_NIGHT', 'NYSE_NIGHT', 'AMEX_NIGHT', ...]
```

## 🔧 시장 추가 가이드

### 새로운 시장 추가하기

1. **새 파일 생성** (예: `crypto.py`)

```python
from .base import BaseMarketProvider
from core import MarketConfig, MarketSession, FieldConfig

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
    
    def __init__(self):
        super().__init__(self.create_default_config())
    
    def parse_stock_code(self, code: str) -> Optional[str]:
        # 암호화폐 심볼 검증 로직
        if self.validate_stock_code_format(code, r'^[A-Z]{3,10}$'):
            return code.upper()
        return None
    
    def format_stock_code(self, code: str, is_night_trading: bool = False) -> str:
        # 암호화폐는 24시간이므로 야간거래 구분 불필요
        parsed_code = self.parse_stock_code(code)
        if parsed_code is None:
            raise ValueError(f"Invalid crypto symbol: {code}")
        return parsed_code
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
    
    # 시간외 모드 테스트
    krx_after = KRXMarketProvider(use_after_hours=True)
    assert krx_after.get_tr_id() == "H0NXCNT0"
    assert krx_after.is_after_hours_mode() == True

def test_krx_config():
    # 설정 팩토리 메서드 테스트
    regular_config = KRXMarketProvider.create_default_config()
    after_config = KRXMarketProvider.create_after_hours_config()
    
    assert regular_config.tr_id == "H0STCNT0"
    assert after_config.tr_id == "H0NXCNT0"
```

### US 테스트

```python
def test_us_provider():
    us = USMarketProvider()
    
    # 종목 코드 파싱
    assert us.parse_stock_code("AAPL") == "AAPL"
    assert us.parse_stock_code("DNASAAPL") == "AAPL"
    
    # 코드 포맷팅
    night_code = us.format_stock_code("AAPL", is_night_trading=True)
    day_code = us.format_stock_code("AAPL", is_night_trading=False)
    
    assert "AAPL" in night_code
    assert "AAPL" in day_code
    assert night_code.startswith("D")  # 야간거래
    assert day_code.startswith("R")    # 주간거래
    
    # KIS 코드 파싱
    result = us.parse_kis_formatted_code("DNASAAPL")
    if result:
        symbol, exchange, session = result
        assert symbol == "AAPL"
        assert exchange == "NASDAQ"
        assert session == "night"
    
    # 거래소 코드 확인
    assert us.get_exchange_code("NASDAQ_NIGHT") == "NAS"
    assert us.get_exchange_code("NYSE_DAY") == "BAY"
    
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
