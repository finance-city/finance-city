# Data Module

실시간 데이터 수신, 파싱, WebSocket 연결 관리를 담당하는 모듈입니다. KIS API로부터 받은 원시 데이터를 구조화된 형태로 변환하고, 안정적인 실시간 통신을 제공합니다.

## 📁 파일 구조

```
data/
├── __init__.py           # 데이터 모듈 익스포트
├── parser.py            # KIS 데이터 파싱 서비스
├── websocket_client.py  # WebSocket 실시간 클라이언트
└── README.md           # 이 파일
```

## 🏗️ 주요 컴포넌트

### KISDataParser (parser.py)

KIS WebSocket API에서 수신한 실시간 데이터를 파싱하는 서비스입니다.

#### 핵심 기능

- **실시간 데이터 파싱**: JSON 메시지를 MarketData 객체로 변환
- **시장별 필드 매핑**: TR_ID에 따른 동적 필드 매핑
- **에러 메시지 처리**: API 오류 응답 파싱 및 예외 발생
- **데이터 검증**: 필수 필드 존재 여부 및 형식 검증
- **종목 코드 정규화**: KIS 형식 → 표준 형식 변환

#### 사용 예시

```python
from data import KISDataParser
from markets import KRXMarketProvider, USMarketProvider

# 마켓 매니저 설정
market_manager = MarketManager()
market_manager.add_provider("KRX", KRXMarketProvider())
market_manager.add_provider("US", USMarketProvider())

# 파서 초기화
parser = KISDataParser(market_manager)

# 실시간 데이터 파싱
raw_message = '''{
  "header": {"tr_id": "H0STCNT0"},
  "body": {"output": {
    "0": "005930", "1": "삼성전자", "2": "75000",
    "3": "1000", "4": "1.35", "5": "1000000"
  }}
}'''

market_data = parser.parse_realtime_data(raw_message, "KRX")

if market_data:
    print(f"종목: {market_data.stock_name}")
    print(f"현재가: {market_data.price:,}원")
    print(f"변화율: {market_data.change_rate:+.2f}%")
```

### KISWebSocketClient (websocket_client.py)

KIS 실시간 API와의 WebSocket 연결을 관리하는 클라이언트입니다.

#### 핵심 기능

- **자동 재연결**: 연결 끊김 시 exponential backoff로 재연결
- **메시지 큐잉**: 연결 끊김 중 메시지 버퍼링
- **콜백 기반**: 이벤트 드리븐 아키텍처
- **상태 관리**: 연결 상태 실시간 모니터링
- **비동기 처리**: asyncio 기반 비동기 메시지 처리

#### 사용 예시

```python
import asyncio
from data import KISWebSocketClient

# 콜백 함수 정의
def on_message(message: str):
    print(f"수신: {message}")

def on_error(error: Exception):
    print(f"오류: {error}")

def on_connect():
    print("WebSocket 연결됨")

def on_disconnect():
    print("WebSocket 연결 끊어짐")

# 클라이언트 생성
client = KISWebSocketClient(
    ws_url="ws://ops.koreainvestment.com:21000",
    on_message=on_message,
    on_error=on_error,
    on_connect=on_connect,
    on_disconnect=on_disconnect
)

# 비동기 연결 및 구독
async def main():
    await client.connect()
    
    # 구독 메시지 전송
    subscription_message = {
        "header": {
            "approval_key": "approval_key_here",
            "custtype": "P",
            "tr_type": "1"
        },
        "body": {
            "input": {
                "tr_id": "H0STCNT0",
                "tr_key": "005930^000660"
            }
        }
    }
    
    await client.send_message(subscription_message)
    await client.listen()

# 실행
asyncio.run(main())
```

## ⚠️ 주의사항

**WebSocket 연결 제한**
- KIS API는 동시 연결 수 제한 (보통 5개)
- 여러 인스턴스 실행 시 연결 실패 가능
- 프로덕션에서는 연결 풀링 고려

**메시지 처리 성능**
- 초당 수백~수천 개의 메시지 수신 가능
- 블로킹 작업은 별도 스레드에서 처리 권장
- 메시지 버퍼 오버플로우 방지 필요

**데이터 정합성**
- 네트워크 지연으로 인한 순서 뒤바뀜 가능
- 타임스탬프 기반 순서 정렬 권장
- 중복 메시지 필터링 구현 고려

## 🧪 테스트

**파서 테스트**
```python
import pytest
from data import KISDataParser

def test_parse_krx_message():
    parser = KISDataParser(mock_market_manager)
    
    raw_message = '''{"header":{"tr_id":"H0STCNT0"},"body":{"output":{"0":"005930","1":"삼성전자","2":"75000"}}}'''
    
    market_data = parser.parse_realtime_data(raw_message, "KRX")
    
    assert market_data.stock_code == "005930"
    assert market_data.stock_name == "삼성전자"
    assert market_data.price == 75000.0
```

**WebSocket 테스트**
```python
import pytest
import asyncio
from data import KISWebSocketClient

@pytest.mark.asyncio
async def test_websocket_connection():
    client = KISWebSocketClient("ws://test-url")
    
    await client.connect()
    assert client.is_connected()
```

## 🔗 의존성

**내부 모듈**
- `core`: 인터페이스, 모델, 예외 클래스
- `markets`: 시장별 필드 매핑 정보

**외부 라이브러리**
- `websockets`: WebSocket 클라이언트
- `asyncio`: 비동기 처리
- `json`: JSON 파싱

## 📚 관련 문서

- [Core README](../core/README.md) - 데이터 모델 및 인터페이스
- [Markets README](../markets/README.md) - 시장별 필드 매핑
- [KIS API 문서](https://apiportal.koreainvestment.com/) - WebSocket API 명세
