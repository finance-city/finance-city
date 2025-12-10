# collector_main.py

import os
import logging
import redis
import pandas as pd
import json
from typing import Dict
from dotenv import load_dotenv

from kis_websocket import KISWebSocket
from data_fetch import RequestBuilder
from auth import get_auth_manager
from market_manager import MarketManager
from stock_manager import get_stock_manager


def main():
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # 상수 정의
    REDIS_CHANNEL = "stock:raw"

    # 환경변수 로드
    KIS_WS_URL = os.getenv("KIS_WS_URL", "ws://ops.koreainvestment.com:21000")
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REVOKE_TOKEN_ON_EXIT = os.getenv("REVOKE_TOKEN_ON_EXIT", "false").lower() == "true"
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    # StockManager와 MarketManager 초기화
    stock_manager = get_stock_manager()
    market_manager = MarketManager(stock_manager=stock_manager)
    request_builder = RequestBuilder()
    
    # 활성화된 종목 코드 가져오기
    STOCK_CODES = stock_manager.get_active_stock_codes()
    
    # 디버깅: 로드된 종목 정보 출력
    print(f"🔍 디버깅 정보:")
    print(f"   - STOCK_CODES: {STOCK_CODES}")
    print(f"   - CSV에서 로드된 전체 종목: {len(stock_manager.stocks)}개")
    print(f"   - 활성화된 종목: {len(STOCK_CODES)}개 - {STOCK_CODES}")
    
    if not STOCK_CODES:
        print("❌ 수집할 종목이 없습니다. stocks.csv 파일이나 환경변수를 확인하세요.")
        return

    # 종목을 시장별로 분류
    krx_stocks = []
    us_stocks = []
    
    for code in STOCK_CODES:
        stock_info = stock_manager.get_stock_info(code)
        print(f"   - {code}: {stock_info}")
        if stock_info and stock_info.get("market") in ["NASDAQ", "NYSE"]:
            us_stocks.append(code)
        else:
            krx_stocks.append(code)
    
    print(f"📊 종목 분류:")
    print(f"   - 한국 주식: {len(krx_stocks)}개 - {krx_stocks}")
    print(f"   - 미국 주식: {len(us_stocks)}개 - {us_stocks}")

    def handle_realtime_data(ws, tr_id: str, df: pd.DataFrame, tr_meta: Dict):
        """KISWebSocket에서 데이터 수신 시 호출되는 콜백 함수"""
        
        if df.empty:
            logging.warning(f"[{tr_id}] Empty DataFrame received")
            return

        try:
            session = market_manager.get_session_by_tr_id(tr_id)
            if not session:
                logging.warning(f"Unknown TR_ID: {tr_id}")
                return
            
            for index, row in df.iterrows():
                raw_data = row.to_dict()
                formatted_data = market_manager.format_market_data(tr_id, raw_data)
                
                json_data = json.dumps(formatted_data, ensure_ascii=False)
                
                if REDIS_CLIENT is not None:
                    REDIS_CLIENT.publish(REDIS_CHANNEL, json_data)
                    logging.info(f"[{formatted_data['stock_name']}] {formatted_data['price']}원 @ {formatted_data['time']}")

        except Exception as e:
            logging.error(f"데이터 처리 오류: {e}")
            logging.error(f"TR_ID: {tr_id}, DataFrame: {df.shape}")

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
        return

    try:
        ws_client = KISWebSocket(api_url=KIS_WS_URL)
        
        # 시장별 현재 세션 확인
        krx_tr_id = request_builder.get_current_tr_id(market_filter=["krx"]) if krx_stocks else None
        us_tr_id = request_builder.get_current_tr_id(market_filter=["us"]) if us_stocks else None
        
        print(f"현재 세션 정보:")
        if krx_tr_id:
            print(f"   - 한국 시장: {krx_tr_id}")
        else:
            print(f"   - 한국 시장: 세션 없음 (한국 주식 {len(krx_stocks)}개)")
        
        if us_tr_id:
            print(f"   - 미국 시장: {us_tr_id}")  
        else:
            print(f"   - 미국 시장: 세션 없음 (미국 주식 {len(us_stocks)}개)")
            
        if not krx_tr_id and not us_tr_id:
            print(f"   ⚠️  활성 세션 없음, 기본 설정 사용")
        
        # RequestBuilder를 사용한 구독
        def build_request_wrapper(tr_type: str, tr_key: str):
            return request_builder.build_request(tr_type, tr_key)
        
        # 모든 종목 구독 (RequestBuilder가 자동으로 시장 판단)
        ws_client.subscribe(request=build_request_wrapper, data=STOCK_CODES)
        
        # 종목 정보 표시
        stock_info_list = []
        for code in STOCK_CODES:
            stock_info = stock_manager.get_stock_info(code)
            if stock_info:
                stock_info_list.append(f"{code}({stock_info['name']})")
            else:
                stock_info_list.append(f"{code}(Unknown)")
        
        print(f"구독 완료: {', '.join(stock_info_list)}")
        print(f"실시간 데이터 수집 중... (Ctrl+C로 종료)")

        ws_client.start(on_result=handle_realtime_data)

    except KeyboardInterrupt:
        logging.info("사용자 종료")
    except Exception as e:
        logging.error(f"실행 오류: {e}")
    finally:
        logging.info("프로그램 종료")


if __name__ == '__main__':
    main()
