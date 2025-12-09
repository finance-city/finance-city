import asyncio
import logging
import json
import pandas as pd
from io import StringIO
from typing import Callable, Dict, Any, List, Optional, Tuple, Union
import websockets

# 내부 모듈 임포트
from kis_crypto import aes_cbc_base64_dec
from kis_parser import system_resp, open_map, add_open_map, data_map, add_data_map

# 임시 더미 함수 정의 (공식 코드 의존성 제거)
def getTREnv():
    class Env:
        my_url_ws = "" 
    return Env()

def smart_sleep():
    pass

class KISWebSocket:
    api_url: str = ""
    on_result: Optional[Callable[
        [websockets.ClientConnection, str, pd.DataFrame, dict], None
    ]] = None
    result_all_data: bool = False

    retry_count: int = 0
    amx_retries: int = 0

    # init
    def __init__(self, api_url: str, max_retries: int = 3):
        self.api_url = api_url
        self.max_retries = max_retries

    # private
    async def __subscriber(self, ws: websockets.ClientConnection):
        async for raw in ws:
            # 웹소켓에서 받는 데이터를 문자열로 변환
            if isinstance(raw, bytes):
                raw_str = raw.decode('utf-8')
            else:
                raw_str = str(raw)
                
            show_result = False
            tr_id = "UNKNOWN"
            df = pd.DataFrame()

            if raw_str[0] in ["0", "1"]:
                d1 = raw_str.split("|")
                
                if len(d1) < 4:
                    logging.error(f"Invalid data format - expected at least 4 parts, got {len(d1)}")
                    raise ValueError("data not found...")

                tr_id = d1[1]
                
                if tr_id not in data_map:
                    logging.warning(f"TR_ID {tr_id} not found in data_map")
                    continue

                dm = data_map[tr_id]
                d = d1[3]
                
                if dm.get("encrypt", None) == "Y":
                    d = aes_cbc_base64_dec(dm["key"], dm["iv"], d)

                df = pd.read_csv(
                    StringIO(d), header=None, sep="^", names=dm["columns"], dtype=object
                )

                show_result = True

            else:
                rsp = system_resp(raw_str)

                tr_id = rsp.tr_id if hasattr(rsp, 'tr_id') else "UNKNOWN"
                
                if hasattr(rsp, 'tr_id'):
                    add_data_map(
                        tr_id=rsp.tr_id, encrypt=rsp.encrypt, key=rsp.ekey, iv=rsp.iv
                    )

                if hasattr(rsp, 'isPingPong') and rsp.isPingPong:
                    await ws.pong(raw_str.encode())

                if self.result_all_data:
                    show_result = True

            if show_result is True and self.on_result is not None:
                self.on_result(ws, tr_id, df, data_map.get(tr_id, {}))

    async def __runner(self):
        if len(open_map.keys()) > 40:
            raise ValueError("Subscription's max is 40")

        if self.api_url.startswith(('ws://', 'wss://')):
            url = self.api_url
        else:
            url = f"{getTREnv().my_url_ws}{self.api_url}"
        
        logging.info(f"Connecting to WebSocket: {url}")

        while self.retry_count < self.max_retries:
            try:
                async with websockets.connect(url) as ws:
                    logging.info("WebSocket connected")
                    
                    for name, obj in open_map.items():
                        await self.send_multiple(
                            ws, obj["func"], "1", obj["items"], obj["kwargs"]
                        )

                    await asyncio.gather(
                        self.__subscriber(ws),
                    )
            except Exception as e:
                logging.error(f"Connection error (attempt {self.retry_count + 1}): {e}")
                self.retry_count += 1
                await asyncio.sleep(1)

    # func
    @classmethod
    async def send(
            cls,
            ws: websockets.ClientConnection,
            request: Callable[[str, str], Tuple[Dict[str, Any], List[str]]],
            tr_type: str,
            data: str,
            kwargs: Optional[Dict[str, Any]] = None,
    ):
        k = {} if kwargs is None else kwargs
        msg, columns = request(tr_type, data, **k)

        tr_id = msg["body"]["input"]["tr_id"]
        add_data_map(tr_id=tr_id, columns=columns)

        await ws.send(json.dumps(msg))
        smart_sleep()

    async def send_multiple(
            self,
            ws: websockets.ClientConnection,
            request: Callable[[str, str], Tuple[Dict[str, Any], List[str]]],
            tr_type: str,
            data: Union[List[str], str],
            kwargs: Optional[Dict[str, Any]] = None,
    ):
        if type(data) is str:
            await self.send(ws, request, tr_type, data, kwargs)
        elif type(data) is list:
            for d in data:
                await self.send(ws, request, tr_type, d, kwargs)
        else:
            raise ValueError("data must be str or list")

    @classmethod
    def subscribe(
            cls,
            request: Callable[[str, str], Tuple[Dict[str, Any], List[str]]],
            data: Union[List[str], str],
            kwargs: Optional[Dict[str, Any]] = None,
    ):
        add_open_map(request.__name__, request, data, kwargs)

    async def unsubscribe(
            self,
            ws: websockets.ClientConnection,
            request: Callable[[str, str], Tuple[Dict[str, Any], List[str]]],
            data: Union[List[str], str],
    ):
        await self.send_multiple(ws, request, "2", data)

    # start
    def start(
            self,
            on_result: Callable[
                [websockets.ClientConnection, str, pd.DataFrame, dict], None
            ],
            result_all_data: bool = False,
    ):
        self.on_result = on_result
        self.result_all_data = result_all_data
        try:
            asyncio.run(self.__runner())
        except KeyboardInterrupt:
            print("Closing by KeyboardInterrupt")