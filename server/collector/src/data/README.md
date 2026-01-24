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

KIS WebSocket API에서 수신한 실시간 데이터를 파싱하는 서비스입니다. `IDataParser` 인터페이스를 구현합니다.

#### 핵심 기능

- **실시간 데이터 파싱**: JSON 메시지를 MarketData 객체로 변환
- **시장별 필드 매핑**: TR_ID에 따른 동적 필드 매핑
- **TR_ID 자동 감지**: 메시지의 TR_ID를 통한 시장 자동 식별
- **에러 메시지 처리**: API 오류 응답 파싱 및 예외 발생
- **데이터 검증**: 필수 필드 존재 여부 및 형식 검증
- **종목 코드 정규화**: KIS 형식 → 표준 형식 변환
- **필드 매핑 캐싱**: 성능 최적화를 위한 필드 매핑 캐시

```python
from data import KISDataParser
from markets import MarketManagerService

# 마켓 매니저 설정 (실제 구현체 사용)
market_manager = MarketManagerService()

# 파서 초기화
parser = KISDataParser(market_manager)

# 실시간 데이터 파싱 (TR_ID 자동 감지)
raw_message = '''{
  "header": {"tr_id": "H0STCNT0"},
  "body": {"output": {
    "0": "005930", "1": "삼성전자", "2": "75000",
    "3": "1000", "4": "1.35", "5": "1000000"
  }}
}'''

# 시장은 TR_ID를 통해 자동 감지됨
market_data = parser.parse_realtime_data(raw_message, "AUTO")

if market_data:
    print(f"종목: {market_data.stock_name}")
    print(f"현재가: {market_data.price:,}원")
    print(f"변화율: {market_data.change_rate:+.2f}%")
    
# 에러 메시지 파싱
error_message = parser.parse_error_message(raw_message)
if error_message:
    print(f"에러: {error_message}")
```

market_data = parser.parse_realtime_data(raw_message, "KRX")

if market_data:
    print(f"종목: {market_data.stock_name}")
    print(f"현재가: {market_data.price:,}원")
    print(f"변화율: {market_data.change_rate:+.2f}%")
```

### KISWebSocketClient (websocket_client.py)

KIS 실시간 API와의 WebSocket 연결을 관리하는 클라이언트입니다. `IWebSocketManager` 인터페이스를 구현합니다.

#### 핵심 기능

- **자동 재연결**: 연결 끊김 시 exponential backoff로 재연결 (최대 5회)
- **연결 상태 관리**: ping/pong을 통한 연결 상태 모니터링
- **메시지 큐잉**: 연결 끊김 중 메시지 버퍼링 및 재전송
- **콜백 기반**: 이벤트 드리븐 아키텍처 (connect, disconnect, message, error)
- **비동기 처리**: asyncio 기반 비동기 메시지 처리
- **구독 추적**: 전송된 구독 요청 추적 및 재연결 시 복원
- **타임아웃 관리**: ping/pong 타임아웃 및 연결 타임아웃 설정

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

# 클라이언트 생성 (콜백 및 재연결 설정 포함)
client = KISWebSocketClient(
    ws_url="ws://ops.koreainvestment.com:21000",
    on_message=on_message,
    on_error=on_error,
    on_connect=on_connect,
    on_disconnect=on_disconnect
)

# 비동기 연결 및 구독
async def main():
    try:
        # WebSocket 연결
        await client.connect()
        
        # 구독 메시지 전송
        subscription_message = {
            "header": {
                "approval_key": "approval_key_here",
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": "H0STCNT0",
                    "tr_key": "005930^000660"
                }
            }
        }
        
        await client.send_message(subscription_message)
        
        # 메시지 수신 대기 (자동 재연결 포함)
        await client.listen()
        
    except KeyboardInterrupt:
        print("사용자 중단")
    finally:
        await client.disconnect()

# 실행
asyncio.run(main())
```
```

## ⚠️ 주의사항

**WebSocket 연결 제한**
- KIS API는 동시 연결 수 제한 (보통 5개)
- 여러 인스턴스 실행 시 연결 실패 가능
- 프로덕션에서는 연결 풀링 고려

**재연결 관리**
- 최대 재연결 시도 횟수: 5회 (exponential backoff)
- 재연결 지연: 5초부터 시작하여 점진적 증가
- 구독 상태는 재연결 시 자동으로 복원됨

**메시지 처리 성능**
- 초당 수백~수천 개의 메시지 수신 가능
- 블로킹 작업은 별도 스레드에서 처리 권장
- 메시지 버퍼 오버플로우 방지 필요

**데이터 정합성**
- 네트워크 지연으로 인한 순서 뒤바뀜 가능
- 타임스탬프 기반 순서 정렬 권장
- 중복 메시지 필터링 구현 고려

**에러 처리**
- DataParsingError 예외를 통한 구조화된 에러 처리
- WebSocketError 예외를 통한 연결 관련 에러 처리
- 로깅을 통한 상세한 에러 추적

## 🧪 테스트

**파서 테스트**
```python
import pytest
from data import KISDataParser
from core import DataParsingError

def test_parse_krx_message():
    parser = KISDataParser(mock_market_manager)
    
    raw_message = '''{"header":{"tr_id":"H0STCNT0"},"body":{"output":{"0":"005930","1":"삼성전자","2":"75000"}}}'''
    
    market_data = parser.parse_realtime_data(raw_message, "AUTO")
    
    assert market_data.stock_code == "005930"
    assert market_data.stock_name == "삼성전자"
    assert market_data.price == 75000.0
    assert market_data.market == "KRX"  # TR_ID로 자동 감지

def test_parse_invalid_message():
    parser = KISDataParser(mock_market_manager)
    
    with pytest.raises(DataParsingError):
        parser.parse_realtime_data("invalid json", "KRX")

def test_parse_error_message():
    parser = KISDataParser(mock_market_manager)
    
    error_msg = '''{"header":{"tr_cd":"1","tr_msg":"Invalid request"}}'''
    
    result = parser.parse_error_message(error_msg)
    assert "Error 1: Invalid request" in result
```

**WebSocket 테스트**
```python
import pytest
import asyncio
from data import KISWebSocketClient
from core import WebSocketError

@pytest.mark.asyncio
async def test_websocket_connection():
    client = KISWebSocketClient("ws://test-url")
    
    # 연결 성공 테스트 (mock 필요)
    await client.connect()
    assert client.is_connected()

@pytest.mark.asyncio
async def test_websocket_reconnection():
    client = KISWebSocketClient("ws://test-url")
    
    # 재연결 로직 테스트
    client._max_reconnect_attempts = 2
    
    # 연결 실패 시나리오 테스트
    with pytest.raises(WebSocketError):
        await client.connect()

@pytest.mark.asyncio  
async def test_message_queuing():
    client = KISWebSocketClient("ws://test-url")
    
    # 연결 끊김 상태에서 메시지 큐잉 테스트
    test_message = {"test": "message"}
    await client.send_message(test_message)
    
    assert len(client._subscribed_requests) > 0
```

## 🔗 의존성

**내부 모듈**
- `core`: 인터페이스, 모델, 예외 클래스
- `markets`: 시장별 필드 매핑 정보

**외부 라이브러리**
- `websockets`: WebSocket 클라이언트 (비동기 연결 관리)
- `asyncio`: 비동기 처리 및 이벤트 루프
- `json`: JSON 메시지 파싱
- `logging`: 에러 추적 및 디버깅

## 📚 관련 문서

- [Core README](../core/README.md) - 데이터 모델 및 인터페이스
- [Markets README](../markets/README.md) - 시장별 필드 매핑
- [KIS API 문서](https://apiportal.koreainvestment.com/) - WebSocket API 명세
