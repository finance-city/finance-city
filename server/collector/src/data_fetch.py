# data_fetch.py

from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple, List, Optional
import json
from auth import get_access_token, get_approval_key
from market_manager import MarketManager
from stock_manager import get_stock_manager


@dataclass
class RequestHeader:
    approval_key: str
    custtype: str
    tr_type: str
    content_type: str = "utf-8"

@dataclass
class RequestInput:
    tr_id: str
    tr_key: str

@dataclass
class RequestBody:
    input: RequestInput

@dataclass
class RequestPacket:
    header: RequestHeader
    body: RequestBody

    def to_json_packet(self) -> str:
        """KIS가 요구하는 JSON 구조 생성"""
        data_dict: Dict[str, Any] = asdict(self)
        
        header_dict = data_dict['header']
        if 'content_type' in header_dict:
            content_value = header_dict.pop('content_type')
            header_dict['content-type'] = content_value
            
        return json.dumps(data_dict) + '\n'


class RequestBuilder:
    """동적 요청 메시지 생성기"""
    
    def __init__(self):
        self.market_manager = MarketManager()
        self.stock_manager = get_stock_manager()
    
    def build_request(self, tr_type: str, tr_key: str, tr_id: Optional[str] = None, market_filter: Optional[List[str]] = None) -> Tuple[Dict[str, Any], List[str]]:
        """
        요청 메시지 생성
        
        Args:
            tr_type: 요청 타입 ("1" for subscribe, "2" for unsubscribe)
            tr_key: 종목 코드
            tr_id: TR ID (None이면 현재 활성 세션에서 자동 결정)
            market_filter: 시장 필터 (["krx", "us"] 등)
        """
        # 시장 필터 기본값 설정
        if market_filter is None:
            # tr_key 형식으로 시장 판단 (간단한 휴리스틱)
            if tr_key.isdigit() and len(tr_key) == 6:
                market_filter = ["krx"]  # 6자리 숫자면 한국 주식
            elif len(tr_key) <= 5 and tr_key.isalpha():
                market_filter = ["us"]   # 알파벳이면 미국 주식
            else:
                market_filter = ["krx"]  # 기본값은 한국
        
        # TR_ID 결정
        if tr_id is None:
            current_session = self.market_manager.get_current_session(market_filter=market_filter)
            if not current_session:
                # 시장별 기본값 설정
                if "us" in market_filter:
                    tr_id = "HDFSCNT0"  # 해외주식 기본
                else:
                    tr_id = "H0NXCNT0"  # 국내주식 애프터마켓 기본
            else:
                tr_id = current_session.tr_id
        
        # 필드 매핑 가져오기
        field_mapping = self.market_manager.get_field_mapping(tr_id)
        if not field_mapping:
            raise ValueError(f"No field mapping found for TR_ID: {tr_id}")
        
        # 인증 정보 가져오기
        token = get_access_token()
        approval_key = get_approval_key(token)
        
        # 해외주식의 경우 tr_key 형식 변환
        if tr_id == "HDFSCNT0":
            if not tr_key.startswith(("D", "R")):
                # 시간대와 거래소 코드를 한번에 결정
                tr_key = self._get_us_tr_key(tr_key)
        
        print(f"tr_key transformed to: {tr_key}")

        # 요청 메시지 구성
        header = RequestHeader(
            approval_key=approval_key,
            custtype="P",
            tr_type=tr_type,
        )
        request_input = RequestInput(
            tr_id=tr_id,
            tr_key=tr_key
        )
        body = RequestBody(input=request_input)
        packet = RequestPacket(header=header, body=body)
        
        msg_dict = asdict(packet)
        columns = field_mapping.columns
        
        return msg_dict, columns
    
    def _get_us_tr_key(self, stock_code: str) -> str:
        """미국 주식의 완전한 tr_key 생성 (시간대 + 거래소 + 종목코드)"""
        from datetime import datetime
        
        # CSV에서 거래소 정보 가져오기
        stock_info = self.stock_manager.get_stock_info(stock_code)
        if not stock_info:
            market = "NASDAQ"
        else:
            market = stock_info.get("market", "NASDAQ")
        
        # 현재 시간 확인
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        
        # 미국 써머타임 자동 계산
        is_dst = self._is_us_dst(now)
        
        # 미국 주간거래 시간 체크 (써머타임 자동 적용)
        if is_dst:
            # EDT (써머타임): 한국시간 22:30~05:00
            is_us_trading_hours = (
                (current_hour == 22 and current_minute >= 30) or
                (23 <= current_hour <= 23) or
                (0 <= current_hour <= 4) or
                (current_hour == 5 and current_minute == 0)
            )
            dst_info = "EDT (써머타임)"
        else:
            # EST (표준시): 한국시간 23:30~06:00  
            is_us_trading_hours = (
                (current_hour == 23 and current_minute >= 30) or
                (0 <= current_hour <= 5) or
                (current_hour == 6 and current_minute == 0)
            )
            dst_info = "EST (표준시)"
        
        # 시간대별 코드 매핑 (통합)
        if is_us_trading_hours:
            # 미국 야간거래 시간 → D + 기본 거래소 코드
            exchange_map = {"NASDAQ": "NAS", "NYSE": "NYS", "AMEX": "AMS"}
            prefix = "D"
            trading_type = "미국 야간거래"
        else:
            # 미국 주간거래 시간 → R + 주간거래 코드
            exchange_map = {"NASDAQ": "BAQ", "NYSE": "BAY", "AMEX": "BAA"}
            prefix = "R"
            trading_type = "미국 주간거래"
        
        exchange_code = exchange_map.get(market, "NAS")  # 기본값: NASDAQ
        tr_key = f"{prefix}{exchange_code}{stock_code}"
        
        print(f"🕐 {current_hour:02d}:{current_minute:02d} | {stock_code}({market}) → {tr_key} ({trading_type}) [{dst_info}]")
        
        return tr_key
    
    def _is_us_dst(self, dt) -> bool:
        """미국 써머타임(DST) 여부 판단"""
        from datetime import datetime
        
        year = dt.year
        month = dt.month
        day = dt.day
        
        # 3월 둘째 일요일 계산
        march_second_sunday = self._get_nth_weekday(year, 3, 6, 2)  # 3월, 일요일(6), 2번째
        
        # 11월 첫째 일요일 계산  
        november_first_sunday = self._get_nth_weekday(year, 11, 6, 1)  # 11월, 일요일(6), 1번째
        
        # 써머타임 기간: 3월 둘째 일요일 ~ 11월 첫째 일요일
        if month < 3 or month > 11:
            return False
        elif month > 3 and month < 11:
            return True
        elif month == 3:
            return day >= march_second_sunday
        elif month == 11:
            return day < november_first_sunday
        
        return False
    
    def _get_nth_weekday(self, year: int, month: int, weekday: int, n: int) -> int:
        """특정 월의 n번째 특정 요일 날짜 계산"""
        from datetime import datetime, timedelta
        
        # 해당 월 1일
        first_day = datetime(year, month, 1)
        
        # 첫 번째 해당 요일까지의 날짜 차이
        days_to_weekday = (weekday - first_day.weekday()) % 7
        
        # n번째 해당 요일
        target_date = first_day + timedelta(days=days_to_weekday + (n-1) * 7)
        
        return target_date.day
    
    def get_current_tr_id(self, market_filter: Optional[List[str]] = None) -> Optional[str]:
        """현재 시간에 적합한 TR_ID 반환"""
        if market_filter is None:
            market_filter = ["krx"]  # 기본값
        current_session = self.market_manager.get_current_session(market_filter=market_filter)
        return current_session.tr_id if current_session else None


# 기존 호환성을 위한 함수 (deprecated)
def get_realtime_request(tr_type: str, tr_key: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    레거시 호환성을 위한 함수
    새로운 코드에서는 RequestBuilder를 사용하세요.
    """
    builder = RequestBuilder()
    return builder.build_request(tr_type, tr_key)