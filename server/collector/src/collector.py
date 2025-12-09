# collector.py

import os
import logging
import redis
import pandas as pd
import json
from typing import Dict
from dotenv import load_dotenv

from kis_websocket import KISWebSocket
from data_fetch import get_realtime_request
from auth import get_auth_manager

REDIS_CLIENT = None
REDIS_CHANNEL = "stock:raw"


def handle_realtime_data(ws, tr_id: str, df: pd.DataFrame, tr_meta: Dict):
    """KISWebSocket에서 데이터 수신 시 호출되는 콜백 함수"""
    if df.empty:
        return

    try:
        if tr_id in ["H0STCNT0", "H0NXCNT0"]:
            market_type = "정규장" if tr_id == "H0STCNT0" else "애프터마켓"
            
            for index, row in df.iterrows():
                stock_code = row.get("MKSC_SHRN_ISCD", "")
                stock_name = STOCK_NAMES.get(stock_code, f"Unknown({stock_code})")
                
                processed_data = {
                    "TRID": tr_id,
                    "시장구분": market_type,
                    "종목코드": stock_code,
                    "종목명": stock_name,
                    "체결가격": row.get("STCK_PRPR"),
                    "체결시간": row.get("STCK_CNTG_HOUR"),
                    "체결량": row.get("CNTG_VOL"),
                    "누적체결량": row.get("ACML_VOL"),
                }
                
                json_data = json.dumps(processed_data, ensure_ascii=False)
                
                if REDIS_CLIENT is not None:
                    REDIS_CLIENT.publish(REDIS_CHANNEL, json_data)
                    logging.info(f"[{stock_name}] {processed_data['체결가격']}원 @ {processed_data['체결시간']}")

    except Exception as e:
        logging.error(f"데이터 처리 오류: {e}")


if __name__ == '__main__':
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # 환경변수 로드
    KIS_WS_URL = os.getenv("KIS_WS_URL", "ws://ops.koreainvestment.com:21000")
    STOCK_CODES_STR = os.getenv("STOCK_CODE", "005930")
    STOCK_CODES = [code.strip() for code in STOCK_CODES_STR.split(',')]
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REVOKE_TOKEN_ON_EXIT = os.getenv("REVOKE_TOKEN_ON_EXIT", "false").lower() == "true"
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    # 종목 매핑
    STOCK_NAMES = {
        "005930": "삼성전자",
        "000660": "SK하이닉스", 
        "035420": "NAVER",
        "035720": "카카오",
        "051910": "LG화학"
    }

    try:
        # Redis 연결
        REDIS_CLIENT = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        REDIS_CLIENT.ping()
        print(f"Redis 연결: {REDIS_HOST}:{REDIS_PORT}")
        
        # 환경설정 표시
        if ENVIRONMENT == "development" and not REVOKE_TOKEN_ON_EXIT:
            print("개발모드: 토큰 유지")
        else:
            print("운영모드: 종료 시 토큰 파기")
        
        # 인증 관리자 초기화
        auth_manager = get_auth_manager()
        auth_manager.add_shutdown_handler(lambda: logging.info("WebSocket 연결 정리"))
        
    except Exception as e:
        print(f"초기화 실패: {e}")
        exit()

    try:
        ws_client = KISWebSocket(api_url=KIS_WS_URL)
        ws_client.subscribe(request=get_realtime_request, data=STOCK_CODES)
        
        stock_names = [f"{code}({STOCK_NAMES.get(code, 'Unknown')})" for code in STOCK_CODES]
        print(f"구독 완료: {', '.join(stock_names)}")
        print(f"실시간 데이터 수집 중... (Ctrl+C로 종료)")

        ws_client.start(on_result=handle_realtime_data)

    except KeyboardInterrupt:
        logging.info("사용자 종료")
    except Exception as e:
        logging.error(f"실행 오류: {e}")
    finally:
        logging.info("프로그램 종료")