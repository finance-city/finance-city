"""
WebSocket Manager Service

KIS API WebSocket 연결 관리 서비스.
실시간 주식 데이터 수신을 위한 WebSocket 연결 및 구독 관리.
"""

import asyncio
import json
import logging
import websockets
from typing import List, Optional, Callable, Dict, Any, Tuple
import pandas as pd
from io import StringIO

from core import IWebSocketManager, StockInfo, IAuthManager, IRequestBuilder
from services.metrics_service import metrics_service


class WebSocketManagerService(IWebSocketManager):
    """WebSocket 연결 관리 서비스 구현"""
    
    def __init__(self, auth_manager: Optional[IAuthManager], request_builder: IRequestBuilder, api_url: str):
        """WebSocket 매니저 서비스 초기화
        
        Args:
            auth_manager: 인증 관리 서비스 (None이면 연결 시점에 별도 처리)
            request_builder: 요청 생성 서비스
            api_url: WebSocket API URL
        """
        self._auth_manager = auth_manager
        self._request_builder = request_builder
        self._api_url = api_url
        self._connection: Optional[websockets.ClientConnection] = None
        self._subscribed_stocks: List[StockInfo] = []
        self._data_handler: Optional[Callable] = None
        self._is_running = False
        
        # 데이터 매핑 (임시로 여기에 둠, 나중에 DataParser로 이전)
        self._data_map: Dict[str, Dict] = {}
        
    async def connect(self) -> None:
        """WebSocket 연결 수립
        
        KIS 공식 문서에 따르면:
        - Approval key는 세션 연결 시 초기 1회만 사용
        - 세션이 유지되면 365일 사용 가능
        - 하지만 재연결 시에는 새로운 approval key가 필요할 수 있음
        """
        try:
            # 승인키 확인
            if self._auth_manager is None:
                raise ValueError("AuthManager가 설정되지 않았습니다.")
            
            # 재연결 시에는 새로운 approval key 발급 (force_refresh=False로 캐시 우선)
            # 캐시가 없거나 만료된 경우에만 새로 발급
            approval_key = self._auth_manager.get_approval_key(force_refresh=False)
            if not approval_key:
                raise ValueError("WebSocket 승인키가 필요합니다")
            
            logging.info(f"🔑 Approval Key로 WebSocket 연결 시도: {approval_key[:8]}...")
            
            # WebSocket 연결
            headers = {
                "approval_key": approval_key,
                "custtype": "P",  # 개인
            }
            
            # websockets 라이브러리 버전에 따른 헤더 처리
            try:
                self._connection = await websockets.connect(
                    self._api_url,
                    extra_headers=headers
                )
            except TypeError:
                # extra_headers 파라미터가 지원되지 않는 경우, additional_headers 사용
                try:
                    self._connection = await websockets.connect(
                        self._api_url,
                        additional_headers=headers
                    )
                except TypeError:
                    # 헤더 없이 연결 시도
                    logging.warning("헤더를 설정할 수 없어 기본 연결을 시도합니다")
                    self._connection = await websockets.connect(self._api_url)
            
            logging.info(f"✅ WebSocket 연결 성공: {self._api_url}")
            
            # 메트릭: WebSocket 연결 상태 업데이트
            metrics_service.set_websocket_status('krx', True)
            metrics_service.set_websocket_status('us', True)
            
        except Exception as e:
            logging.error(f"❌ WebSocket 연결 실패: {e}")
            metrics_service.set_websocket_status('krx', False)
            metrics_service.set_websocket_status('us', False)
            raise
    
    async def disconnect(self) -> None:
        """WebSocket 연결 해제"""
        try:
            self._is_running = False
            
            if self._connection:
                # websockets 라이브러리에서는 close_code로 연결 상태 확인
                if self._connection.close_code is None:  # None이면 아직 연결됨
                    await self._connection.close()
                logging.info("✅ WebSocket 연결 해제 완료")
            
            self._connection = None
            self._subscribed_stocks = []
            
        except Exception as e:
            logging.error(f"❌ WebSocket 연결 해제 실패: {e}")
    
    async def subscribe_stocks(self, stocks: List[StockInfo]) -> None:
        """종목들에 대한 실시간 데이터 구독
        
        Args:
            stocks: 구독할 종목 리스트
        """
        if not self._connection:
            raise RuntimeError("WebSocket이 연결되지 않았습니다")
        
        try:
            # 시장별로 종목 분류
            krx_stocks = [s for s in stocks if self._is_krx_stock(s)]
            us_stocks = [s for s in stocks if self._is_us_stock(s)]
            
            # KRX 종목 구독
            if krx_stocks:
                await self._subscribe_market_stocks(krx_stocks, "KRX")
            
            # US 종목 구독
            if us_stocks:
                await self._subscribe_market_stocks(us_stocks, "US")
            
            self._subscribed_stocks.extend(stocks)
            
            # 메트릭: 구독 종목 수 업데이트
            krx_count = len([s for s in self._subscribed_stocks if self._is_krx_stock(s)])
            us_count = len([s for s in self._subscribed_stocks if self._is_us_stock(s)])
            metrics_service.set_active_subscriptions('krx', krx_count)
            metrics_service.set_active_subscriptions('us', us_count)
            
            stock_codes = [s.code for s in stocks]
            logging.info(f"✅ 종목 구독 완료: {', '.join(stock_codes)}")
            
        except Exception as e:
            logging.error(f"❌ 종목 구독 실패: {e}")
            raise
    
    async def _subscribe_market_stocks(self, stocks: List[StockInfo], market: str) -> None:
        """특정 시장의 종목들 구독"""
        failed_stocks = []
        
        try:
            # RequestBuilder를 사용한 구독 요청 생성
            # 단일 종목씩 처리하는 방식으로 변경
            for stock in stocks:
                try:
                    # 단일 종목 리스트로 요청 생성
                    single_stock = [stock]
                    
                    # RequestBuilder의 올바른 메서드 사용
                    request_data = self._request_builder.build_subscription_request(single_stock)
                    
                    # 시장별로 요청 데이터 처리
                    for market_key, market_request in request_data.items():
                        if market_request and 'packet' in market_request:
                            # 단일 packet 처리
                            packet = market_request['packet']
                            
                            # RequestPacket 객체를 딕셔너리로 변환
                            if hasattr(packet, 'to_json_packet'):
                                # RequestPacket의 to_json_packet 메서드 사용
                                message = packet.to_json_packet()
                            else:
                                # 수동으로 JSON 변환
                                packet_dict = {
                                    'header': {
                                        'approval_key': packet.header.approval_key,
                                        'custtype': packet.header.custtype,
                                        'tr_type': packet.header.tr_type,
                                        'content-type': packet.header.content_type
                                    },
                                    'body': {
                                        'input': {
                                            'tr_id': packet.body.input.tr_id,
                                            'tr_key': packet.body.input.tr_key
                                        }
                                    }
                                }
                                message = json.dumps(packet_dict) + '\n'
                            
                            # 간소화된 구독 요청 로그
                            tr_id = packet.body.input.tr_id
                            market_type = "KRX" if tr_id.startswith("H0") else "US"
                            logging.debug(f"📡 [{market_type}] {stock.code} 구독 요청")
                            
                            # 연결 상태 확인 후 전송
                            if self._connection and self.is_connected():
                                await self._connection.send(message)
                            else:
                                logging.warning(f"WebSocket 연결이 끊어진 상태에서 {stock.code} 구독 요청 실패")
                                failed_stocks.append(stock.code)
                                continue
                                
                            await asyncio.sleep(0.1)  # KIS API 안정성
                            
                            # 데이터 매핑 정보 미리 초기화
                            columns = self._get_columns_for_tr_id(tr_id)
                            self._data_map[tr_id] = {
                                "columns": columns,
                                "encrypt": "N",
                                "key": None,
                                "iv": None
                            }
                
                except ValueError as ve:
                    # WebSocket 채널이 닫혀있는 경우 (운영시간 외)
                    if "채널이 닫혀있는" in str(ve) or "WebSocket" in str(ve):
                        logging.warning(f"⚠️  [{market}] {stock.code}: {ve}")
                        failed_stocks.append(stock.code)
                    else:
                        # 기타 ValueError
                        logging.error(f"❌ [{market}] {stock.code} 구독 실패: {ve}")
                        failed_stocks.append(stock.code)
                except Exception as e:
                    logging.error(f"❌ [{market}] {stock.code} 구독 실패: {e}")
                    failed_stocks.append(stock.code)
            
            # 구독 실패 요약
            if failed_stocks:
                logging.warning(
                    f"⚠️  {market} 시장: {len(failed_stocks)}개 종목 구독 실패 "
                    f"({', '.join(failed_stocks[:3])}{'...' if len(failed_stocks) > 3 else ''})"
                )
            
        except Exception as e:
            logging.error(f"❌ {market} 시장 구독 실패: {e}")
            # 전체 실패해도 예외를 던지지 않음 (soft error)
    
    async def unsubscribe_stocks(self, stocks: List[StockInfo]) -> None:
        """종목들의 실시간 데이터 구독 해제"""
        if not self._connection or not self.is_connected():
            logging.warning("WebSocket 연결이 없어 구독 해제를 건너뜁니다")
            return
        
        for stock in stocks:
            # 구독 해제 요청 (tr_type="2")
            try:
                # 임시 구독 해제 로직 (나중에 개선)
                logging.info(f"종목 구독 해제: {stock.code}")
            except Exception as e:
                logging.warning(f"종목 {stock.code} 구독 해제 실패: {e}")
        
        # 구독 목록에서 제거
        self._subscribed_stocks = [s for s in self._subscribed_stocks if s not in stocks]
    
    def is_connected(self) -> bool:
        """WebSocket 연결 상태 확인"""
        if self._connection is None:
            return False
        try:
            # websockets 라이브러리에서는 close_code로 연결 상태 확인
            return self._connection.close_code is None
        except AttributeError:
            # close_code 속성이 없는 경우 connection이 있으면 연결된 것으로 간주
            return True
    
    async def start_data_stream(self, data_handler: Callable) -> None:
        """데이터 스트림 시작
        
        Args:
            data_handler: 실시간 데이터 처리 콜백 함수
        """
        if not self._connection:
            raise RuntimeError("WebSocket이 연결되지 않았습니다")
        
        self._data_handler = data_handler
        self._is_running = True
        
        logging.info("🚀 실시간 데이터 스트림 시작...")
        
        try:
            async for raw_message in self._connection:
                if not self._is_running:
                    break
                
                # 원시 메시지 처리
                await self._process_raw_message(raw_message)
                
        except websockets.exceptions.ConnectionClosed:
            logging.warning("WebSocket 연결이 닫혔습니다")
        except Exception as e:
            logging.error(f"데이터 스트림 처리 중 오류: {e}")
        finally:
            self._is_running = False
            logging.info("📊 데이터 스트림 종료")
    
    async def _process_raw_message(self, raw_message) -> None:
        """원시 메시지 처리"""
        try:
            # 메시지 타입에 따른 처리 (간소화)
            if isinstance(raw_message, bytes):
                message_str = raw_message.decode('utf-8')
            else:
                message_str = str(raw_message)
    
            # 실시간 데이터 파싱
            if message_str.startswith(('0', '1')):
                await self._handle_realtime_data(message_str)
            else:
                # 시스템 응답
                await self._handle_system_response(message_str)
                
        except Exception as e:
            logging.error(f"메시지 처리 실패: {e}")
    
    async def _handle_realtime_data(self, message: str) -> None:
        """실시간 데이터 처리"""
        try:
            parts = message.split("|")
            if len(parts) < 4:
                logging.warning(f"잘못된 데이터 형식: {len(parts)}개 파트 (최소 4개 필요)")
                return
            
            tr_id = parts[1]
            data_part = parts[3]
            
            # TR_ID별 데이터 매핑 정보 확인
            if tr_id not in self._data_map:
                logging.warning(f"❌ TR_ID {tr_id} 매핑 정보 없음")
                return
                
            dm = self._data_map[tr_id]
            
            # 암호화된 데이터인 경우 복호화 필요
            if dm.get("encrypt", "N") == "Y":
                logging.warning(f"🔐 암호화된 데이터 ({tr_id}) - 복호화 미구현")
                return
            
            # CSV 형태의 데이터를 DataFrame으로 변환
            try:
                columns = dm.get("columns", [])
                if not columns:
                    logging.warning(f"TR_ID {tr_id}의 컬럼 정보가 없음")
                    return
                
                df = pd.read_csv(
                    StringIO(data_part), 
                    header=None, 
                    sep="^", 
                    names=columns, 
                    dtype=object
                )
                
                if len(df) == 0:
                    logging.warning(f"빈 데이터프레임 ({tr_id})")
                    return
                
                # 첫 번째 행 데이터 추출
                row_data = df.iloc[0].to_dict()
                
                # 표준화된 데이터 구조 생성
                standardized_data = {
                    "code": "",
                    "price": 0.0,
                    "rate": 0.0,
                    "vol_tick": 0,
                    "vol_total": 0
                }
                
                # 시장별 데이터 매핑
                if tr_id == "H0UNCNT0":  # KRX 통합 (정규 + 시간외)
                    stock_code = row_data.get("유가증권_단축_종목코드", "N/A")
                    current_price = row_data.get("주식_현재가", "N/A")
                    change_rate = row_data.get("전일_대비율", "N/A")
                    
                    # 표준화된 구조에 데이터 매핑
                    try:
                        standardized_data["code"] = str(stock_code)
                        standardized_data["price"] = float(current_price) if current_price != "N/A" else 0.0
                        standardized_data["rate"] = float(change_rate) if change_rate != "N/A" else 0.0
                        standardized_data["vol_tick"] = int(row_data.get("체결거래량", 0))
                        standardized_data["vol_total"] = int(row_data.get("누적거래량", 0))
                    except (ValueError, TypeError):
                        # 변환 실패 시 기본값 유지
                        pass
                    
                    # 메트릭: 틱 데이터 수집 기록
                    if stock_code != "N/A":
                        metrics_service.record_tick('krx', str(stock_code))
                    
                    logging.debug(f"📈 [KRX] {stock_code}: {current_price}원 ({change_rate}%)")
                    
                elif tr_id == "HDFSCNT0":  # 해외주식
                    stock_code = row_data.get("SYMB", "N/A")
                    current_price = row_data.get("LAST", "N/A")
                    change_rate = row_data.get("RATE", "N/A")
                    
                    # 표준화된 구조에 데이터 매핑
                    try:
                        standardized_data["code"] = str(stock_code)
                        standardized_data["price"] = float(current_price) if current_price != "N/A" else 0.0
                        standardized_data["rate"] = float(change_rate) if change_rate != "N/A" else 0.0
                        standardized_data["vol_tick"] = int(row_data.get("EVOL", 0))
                        standardized_data["vol_total"] = int(row_data.get("TVOL", 0))
                    except (ValueError, TypeError):
                        # 변환 실패 시 기본값 유지
                        pass
                    
                    # 메트릭: 틱 데이터 수집 기록
                    if stock_code != "N/A":
                        metrics_service.record_tick('us', str(stock_code))
                    
                    logging.info(f"📈 [US] {stock_code}: ${current_price} ({change_rate}%)")
                
                # 콜백 함수에 전달할 데이터 생성 (통일된 구조)
                if self._data_handler:
                    parsed_data = {
                        "tr_id": tr_id,
                        "data": standardized_data,           # 통일된 구조
                        "raw_data": row_data,               # 원시 데이터 보존
                        "timestamp": pd.Timestamp.now().isoformat(),
                        "stock_code": standardized_data["code"],     # 호환성 유지
                        "current_price": str(standardized_data["price"])  # 호환성 유지
                    }
                    
                    await self._data_handler(parsed_data)
                    
            except Exception as parse_error:
                logging.error(f"❌ [{tr_id}] 파싱 실패: {parse_error}")
                
                # 파싱 실패 시 빈 표준화된 구조로 에러 데이터 전달
                if self._data_handler:
                    error_data = {
                        "tr_id": tr_id,
                        "data": {
                            "code": "",
                            "price": 0.0,
                            "rate": 0.0,
                            "vol_tick": 0,
                            "vol_total": 0
                        },
                        "raw_data": data_part,
                        "timestamp": pd.Timestamp.now().isoformat(),
                        "stock_code": "",
                        "current_price": "0",
                        "error": f"파싱 실패: {parse_error}"
                    }
                    await self._data_handler(error_data)
                
        except Exception as e:
            logging.error(f"❌ 실시간 데이터 처리 실패: {e}")
    
    async def _handle_system_response(self, message: str) -> None:
        """시스템 응답 처리 (암호화 키, 연결 상태 등)"""
        try:
            # JSON 파싱
            if message.startswith('{"'):
                response_data = json.loads(message)
                
                # 기본 정보 추출
                tr_id = response_data.get('header', {}).get('tr_id')
                tr_key = response_data.get('header', {}).get('tr_key')
                encrypt = response_data.get('header', {}).get('encrypt', 'N')
                
                # PINGPONG 처리 (로그 없이)
                if tr_id == "PINGPONG":
                    return
                
                # SUBSCRIBE SUCCESS 응답 처리
                body = response_data.get('body', {})
                if body.get('rt_cd') == '0' and body.get('msg1') == 'SUBSCRIBE SUCCESS':
                    symbol = tr_key[-4:] if tr_key and len(tr_key) > 4 else tr_key
                    market_type = "KRX" if tr_id.startswith("H0") else "US"
                    
                    logging.debug(f"✅ [{market_type}] {symbol} 구독 성공")
                    
                    # 암호화 키 정보 추출 및 업데이트
                    output = body.get('output', {})
                    iv = output.get('iv')
                    key = output.get('key')
                    
                    if tr_id in self._data_map:
                        self._data_map[tr_id].update({
                            "encrypt": encrypt,
                            "key": key,
                            "iv": iv
                        })
                    else:
                        columns = self._get_columns_for_tr_id(tr_id)
                        self._data_map[tr_id] = {
                            "columns": columns,
                            "encrypt": encrypt,
                            "key": key,
                            "iv": iv
                        }
                else:
                    # 오류 응답 처리
                    if body.get('rt_cd') != '0':
                        error_msg = body.get('msg1', 'Unknown error')
                        error_code = body.get('rt_cd')
                        
                        # 채널 닫힘 오류인지 확인
                        is_channel_closed = 'channel' in error_msg.lower() and 'closed' in error_msg.lower()
                        is_invalid_approval = 'invalid approval' in error_msg.lower()
                        
                        if is_channel_closed:
                            # 채널이 닫혀있는 경우 - soft error (경고만)
                            symbol = tr_key[-4:] if tr_key and len(tr_key) > 4 else tr_key
                            market_type = "KRX" if tr_id and tr_id.startswith("H0") else "US"
                            logging.warning(
                                f"⚠️  [{market_type}] {symbol} 구독 실패: {error_msg} "
                                f"(운영시간 외이거나 채널이 닫혀있음, 다른 구독은 계속 진행)"
                            )
                        elif is_invalid_approval:
                            # 승인 키 만료 - 재발급 시도 (기존 로직)
                            logging.error(f"❌ 승인 키 오류: {error_msg} (tr_id: {tr_id})")
                            logging.warning("⚠️  승인 키가 만료되었습니다. 재발급 시도...")
                            await self._handle_invalid_approval(tr_id, tr_key)
                        else:
                            # 기타 오류 - 로깅만 하고 계속 진행
                            logging.error(
                                f"❌ 구독 실패: {error_msg} (tr_id: {tr_id}, rt_cd: {error_code})"
                            )
                    
            # 기타 시스템 응답은 무시
            
        except Exception as e:
            logging.warning(f"시스템 응답 처리 실패: {e}")
    
    async def _handle_invalid_approval(self, tr_id: str, tr_key: str) -> None:
        """승인 키 만료 시 재발급 및 재구독 처리"""
        try:
            if not self._auth_manager:
                logging.error("AuthManager가 없어 승인 키를 재발급할 수 없습니다")
                return
            
            logging.info("🔄 승인 키 재발급 중...")
            
            # 강제로 새로운 승인 키 발급
            new_approval_key = self._auth_manager.get_approval_key(force_refresh=True)
            
            logging.info(f"✅ 새로운 승인 키 발급됨: {new_approval_key[:8]}...")
            
            # RequestBuilder의 approval key 업데이트
            if hasattr(self._request_builder, '_approval_key'):
                self._request_builder._approval_key = new_approval_key
                logging.info("RequestBuilder의 승인 키 업데이트 완료")
            
            # WebSocket 재연결 (새로운 승인 키로)
            logging.info("🔄 WebSocket 재연결 중...")
            await self.disconnect()
            await asyncio.sleep(1)  # 짧은 대기
            await self.connect()
            
            # 기존 구독 종목들을 다시 구독
            if self._subscribed_stocks:
                logging.info(f"🔄 {len(self._subscribed_stocks)}개 종목 재구독 중...")
                await self.subscribe_stocks(self._subscribed_stocks.copy())
            
        except Exception as e:
            logging.error(f"❌ 승인 키 재발급 실패: {e}")
    
    def _get_columns_for_tr_id(self, tr_id: str) -> List[str]:
        """TR_ID에 해당하는 컬럼 정보 반환"""
        try:
            if tr_id == "H0UNCNT0":  # KRX 통합 (정규장 + 시간외)
                return [
                    "유가증권_단축_종목코드", "주식_체결_시간", "주식_현재가", "전일_대비_기호", "전일_대비", 
                    "전일_대비율", "가중_평균_주식_가격", "주식_시가", "주식_최고가", "주식_최저가", 
                    "매도호가1", "매수호가1", "체결거래량", "누적거래량", "누적거래대금", "매도체결건수", 
                    "매수체결건수", "순매수체결건수", "체결강도", "총_매도_수량", "총_매수_수량", 
                    "체결구분코드", "매수비율", "전일_거래량_대비_등락율", "시가_시간", "시가대비구분", 
                    "시가대비", "최고가_시간", "고가대비구분", "고가대비", "최저가_시간", "저가대비구분", 
                    "저가대비", "영업_일자", "신_장운영_구분코드", "거래정지_여부", "매도호가잔량", 
                    "매수호가잔량", "총_매도호가_잔량", "총_매수호가_잔량", "거래량_회전율", 
                    "전일_동시간_누적거래량", "전일_동시간_누적거래량_비율", "시간_구분_코드", 
                    "임의종료구분코드", "정적VI발동기준가"
                ]
            elif tr_id == "HDFSCNT0":  # 해외주식
                return [
                    "RSYM", "SYMB", "ZDIV", "TYMD", "XYMD", "XHMS", "KYMD", "KHMS",
                    "OPEN", "HIGH", "LOW", "LAST", "SIGN", "DIFF", "RATE", "PBID", 
                    "PASK", "VBID", "VASK", "EVOL", "TVOL", "TAMT", "BIVL", "ASVL",
                    "STRN", "MTYP"
                ]
            else:
                logging.warning(f"알 수 없는 TR_ID: {tr_id}")
                return []
                
        except Exception as e:
            logging.error(f"컬럼 정보 조회 실패 ({tr_id}): {e}")
            return []
    
    def _is_krx_stock(self, stock: StockInfo) -> bool:
        """KRX 종목인지 확인"""
        # 6자리 숫자이면 KRX
        return len(stock.code) == 6 and stock.code.isdigit()
    
    def _is_us_stock(self, stock: StockInfo) -> bool:
        """US 종목인지 확인"""
        # 알파벳이면 US
        return stock.code.isalpha()
    
    async def stop_data_stream(self) -> None:
        """데이터 스트림 중지"""
        self._is_running = False
        logging.info("📡 데이터 스트림 중지됨")
