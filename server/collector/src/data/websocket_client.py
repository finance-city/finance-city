"""
실시간 데이터 스트리밍을 위한 KIS WebSocket 클라이언트.

이 모듈은 실시간 마켓 데이터 스트림을 수신하기 위한
KIS API에 대한 WebSocket 연결을 제공합니다.
"""

import asyncio
import websockets
from typing import Callable, Optional, Dict, Any, List
from datetime import datetime
import logging
import time

from core import IWebSocketManager, StockInfo, WebSocketError, TimeoutError
from services.metrics_service import metrics_service


class KISWebSocketClient(IWebSocketManager):
    """KIS 실시간 데이터 API용 WebSocket 클라이언트."""
    
    def __init__(
        self, 
        ws_url: str,
        on_message: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None
    ):
        """KIS WebSocket 클라이언트를 초기화합니다.
        
        Args:
            ws_url: KIS API용 WebSocket URL
            on_message: 수신된 메시지에 대한 콜백
            on_error: 에러 처리를 위한 콜백
            on_connect: 연결 설정에 대한 콜백
            on_disconnect: 연결 해제에 대한 콜백
        """
        self._ws_url = ws_url
        self._websocket: Optional[Any] = None  # WebSocket 연결 객체
        self._is_connected = False
        self._connection_task: Optional[asyncio.Task] = None
        
        # 콜백들
        self._on_message = on_message
        self._on_error = on_error
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        
        # 연결 관리
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5.0  # 초
        
        # 구독 추적
        self._subscribed_requests: List[Dict[str, Any]] = []
        
        # 로깅 설정
        self._logger = logging.getLogger(__name__)
        
        # 시장 식별 (메트릭용)
        self._market = 'krx' if 'ops.koreainvestment.com' in ws_url else 'us'
    
    async def connect(self) -> None:
        """WebSocket 연결을 설정합니다.
        
        Raises:
            WebSocketError: 연결이 실패한 경우
        """
        if self._is_connected:
            return
        
        try:
            self._logger.info(f"Connecting to WebSocket: {self._ws_url}")
            
            # WebSocket 연결 설정
            self._websocket = await websockets.connect(
                self._ws_url,
                ping_interval=30,  # 30초마다 ping 전송
                ping_timeout=10,   # pong을 10초 대기
                close_timeout=10   # close를 10초 대기
            )
            
            self._is_connected = True
            self._reconnect_attempts = 0
            
            # 메시지 수신 태스크 시작
            self._connection_task = asyncio.create_task(self._message_loop())
            
            # 메트릭: WebSocket 연결 상태 업데이트
            metrics_service.set_websocket_status(self._market, True)
            
            # 연결 설정 알림
            if self._on_connect:
                self._on_connect()
            
            self._logger.info("WebSocket connected successfully")
            
        except Exception as e:
            self._is_connected = False
            # 메트릭: 연결 실패 상태
            metrics_service.set_websocket_status(self._market, False)
            raise WebSocketError(f"Failed to connect to WebSocket: {e}", connection_state="disconnected")
    
    async def disconnect(self) -> None:
        """WebSocket 연결을 닫습니다."""
        if not self._is_connected and not self._websocket:
            return
        
        self._logger.info("Disconnecting WebSocket...")
        
        try:
            # 먼저 메시지 루프 태스크 취소
            if self._connection_task and not self._connection_task.done():
                self._connection_task.cancel()
                try:
                    await self._connection_task
                except asyncio.CancelledError:
                    pass
            
            # WebSocket 연결 안전하게 닫기
            if self._websocket:
                try:
                    # 닫기 전에 연결이 여전히 활성 상태인지 확인
                    if not self._websocket.closed:
                        await self._websocket.close()
                except AttributeError:
                    # 'closed' 속성이 없는 websockets 버전용
                    try:
                        await self._websocket.close()
                    except Exception as close_error:
                        self._logger.debug(f"WebSocket already closed: {close_error}")
                except Exception as e:
                    self._logger.debug(f"Error closing WebSocket: {e}")
            
        except Exception as e:
            self._logger.error(f"Error during disconnect: {e}")
        finally:
            self._is_connected = False
            self._websocket = None
            self._connection_task = None
            
            # 구독 정보 지우기
            self._subscribed_requests.clear()
            
            # 메트릭: WebSocket 연결 해제
            metrics_service.set_websocket_status(self._market, False)
            metrics_service.set_active_subscriptions(self._market, 0)
            
            # 연결 해제 알림
            if self._on_disconnect:
                try:
                    self._on_disconnect()
                except Exception as callback_error:
                    self._logger.error(f"Error in disconnect callback: {callback_error}")
            
            self._logger.info("WebSocket disconnected")
    
    async def subscribe_stocks(self, stocks: List[StockInfo]) -> None:
        """주어진 주식들의 실시간 데이터를 구독합니다.
        
        Args:
            stocks: 구독할 주식 목록
            
        Raises:
            WebSocketError: 연결되지 않았거나 구독이 실패한 경우
        """
        if not self._is_connected or not self._websocket:
            raise WebSocketError("WebSocket is not connected", connection_state="disconnected")
        
        # 참고: 실제 구독 요청은 RequestBuilderService에 의해 빌드되어야 함
        # 이 메서드는 일반적으로 미리 빌드된 요청 패킷을 받음
        self._logger.info(f"Subscribing to {len(stocks)} stocks")
        
        # 재연결을 위해 구독 정보 저장
        for stock in stocks:
            self._subscribed_requests.append({
                "type": "subscribe",
                "stock": stock,
                "timestamp": datetime.now()
            })
        
        # 메트릭: 활성 구독 수 업데이트
        metrics_service.set_active_subscriptions(self._market, len(stocks))
    
    async def unsubscribe_stocks(self, stocks: List[StockInfo]) -> None:
        """주어진 주식들의 실시간 데이터 구독을 해제합니다.
        
        Args:
            stocks: 구독 해제할 주식 목록
            
        Raises:
            WebSocketError: 연결되지 않았거나 구독 해제가 실패한 경우
        """
        if not self._is_connected or not self._websocket:
            raise WebSocketError("WebSocket is not connected", connection_state="disconnected")
        
        self._logger.info(f"Unsubscribing from {len(stocks)} stocks")
        
        # 구독 추적에서 제거
        stock_codes = {stock.code for stock in stocks}
        self._subscribed_requests = [
            req for req in self._subscribed_requests
            if req.get("stock", {}).code not in stock_codes
        ]
    
    async def send_request(self, request_packet: str) -> None:
        """WebSocket에 요청 패킷을 전송합니다.
        
        Args:
            request_packet: 전송할 JSON 요청 패킷
            
        Raises:
            WebSocketError: 연결되지 않았거나 전송이 실패한 경우
        """
        if not self._is_connected or not self._websocket:
            raise WebSocketError("WebSocket is not connected", connection_state="disconnected")
        
        try:
            # _websocket이 None이 아님을 보장하는 타입 가드
            websocket = self._websocket
            if websocket is None:
                raise WebSocketError("WebSocket connection is None", connection_state="disconnected")
                
            await websocket.send(request_packet)
            self._logger.debug(f"Sent request: {request_packet[:100]}...")
            
        except websockets.ConnectionClosed as e:
            self._is_connected = False
            raise WebSocketError(f"Connection closed while sending: {e}", connection_state="closed")
        except Exception as e:
            raise WebSocketError(f"Failed to send request: {e}")
    
    def is_connected(self) -> bool:
        """WebSocket이 연결되어 있는지 확인합니다.
        
        Returns:
            연결되어 있으면 True, 그렇지 않으면 False
        """
        return self._is_connected and self._websocket is not None
    
    async def _message_loop(self) -> None:
        """메인 메시지 수신 루프."""
        if not self._websocket:
            return
        
        try:
            async for message in self._websocket:
                try:
                    if self._on_message:
                        self._on_message(message)
                except Exception as e:
                    self._logger.error(f"Error in message callback: {e}")
                    if self._on_error:
                        self._on_error(e)
        
        except websockets.ConnectionClosed as e:
            self._logger.warning(f"WebSocket connection closed: {e}")
            self._is_connected = False
            await self._handle_disconnection()
        
        except Exception as e:
            self._logger.error(f"Error in message loop: {e}")
            if self._on_error:
                self._on_error(e)
            self._is_connected = False
            await self._handle_disconnection()
    
    async def _handle_disconnection(self) -> None:
        """예상치 못한 연결 해제를 처리합니다."""
        self._logger.info("Handling unexpected disconnection...")
        
        if self._on_disconnect:
            self._on_disconnect()
        
        # 설정된 경우 재연결 시도
        if self._reconnect_attempts < self._max_reconnect_attempts:
            await self._attempt_reconnection()
    
    async def _attempt_reconnection(self) -> None:
        """연결 해제 후 재연결을 시도합니다."""
        self._reconnect_attempts += 1
        
        self._logger.info(
            f"Attempting reconnection {self._reconnect_attempts}/{self._max_reconnect_attempts} "
            f"in {self._reconnect_delay} seconds..."
        )
        
        await asyncio.sleep(self._reconnect_delay)
        
        try:
            await self.connect()
            
            # 이전 주식들에 대해 재구독
            if self._subscribed_requests:
                self._logger.info(f"Resubscribing to {len(self._subscribed_requests)} previous subscriptions")
                # 참고: 실제 구현에서는 구독 요청을 재빌드하고 전송해야 함
                
        except Exception as e:
            self._logger.error(f"Reconnection attempt {self._reconnect_attempts} failed: {e}")
            
            if self._reconnect_attempts < self._max_reconnect_attempts:
                # 지수적 백오프
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)
                await self._attempt_reconnection()
            else:
                self._logger.error("Max reconnection attempts reached. Giving up.")
                if self._on_error:
                    self._on_error(WebSocketError("Max reconnection attempts reached"))
    
    def get_connection_info(self) -> Dict[str, Any]:
        """연결 정보를 가져옵니다.
        
        Returns:
            연결 세부 정보가 포함된 딕셔너리
        """
        return {
            "is_connected": self._is_connected,
            "ws_url": self._ws_url,
            "reconnect_attempts": self._reconnect_attempts,
            "subscribed_count": len(self._subscribed_requests),
            "local_address": getattr(self._websocket, "local_address", None) if self._websocket else None,
            "remote_address": getattr(self._websocket, "remote_address", None) if self._websocket else None
        }
    
    def set_reconnect_config(self, max_attempts: int, initial_delay: float) -> None:
        """재연결 동작을 설정합니다.
        
        Args:
            max_attempts: 최대 재연결 시도 횟수
            initial_delay: 재연결 시도 사이의 초기 지연 시간 (초)
        """
        self._max_reconnect_attempts = max_attempts
        self._reconnect_delay = initial_delay
    
    async def wait_for_connection(self, timeout: float = 30.0) -> None:
        """WebSocket 연결이 설정될 때까지 대기합니다.
        
        Args:
            timeout: 대기할 최대 시간 (초)
            
        Raises:
            TimeoutError: 타임아웃 내에 연결이 설정되지 않은 경우
        """
        start_time = asyncio.get_event_loop().time()
        
        while not self._is_connected:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(
                    f"WebSocket connection not established within {timeout} seconds",
                    timeout_duration=timeout,
                    operation="connect"
                )
            
            await asyncio.sleep(0.1)  # 100ms마다 확인
