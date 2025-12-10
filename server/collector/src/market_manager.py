# market_manager.py

from datetime import datetime, time
from typing import List, Optional, Dict, Any
import logging
from market_config import (
    MarketSession, MarketType, DataType, FieldMapping,
    KRX_SESSIONS, US_SESSIONS, FIELD_MAPPINGS
)
from stock_manager import get_stock_manager


class MarketManager:
    """시장별 세션 및 데이터 관리"""
    
    def __init__(self, stock_manager=None):
        self.sessions = KRX_SESSIONS + US_SESSIONS
        self.field_mappings = FIELD_MAPPINGS
        self.stock_manager = stock_manager or get_stock_manager()
    
    def get_current_session(self, market_filter: Optional[List[str]] = None) -> Optional[MarketSession]:
        """현재 시간에 활성화된 시장 세션 반환"""
        current_time = datetime.now().time()
        
        for session in self.sessions:
            if self._is_time_in_session(current_time, session):
                if market_filter:
                    market_name = session.market_type.value.split('_')[0]
                    if market_name not in market_filter:
                        continue
                return session
        
        return None
    
    def _is_time_in_session(self, current_time: time, session: MarketSession) -> bool:
        """시간이 세션 범위 내에 있는지 확인"""
        start = session.start_time
        end = session.end_time
        
        if start <= end:
            return start <= current_time <= end
        else:
            return current_time >= start or current_time <= end
    
    def get_session_by_tr_id(self, tr_id: str) -> Optional[MarketSession]:
        """TR_ID로 세션 찾기"""
        for session in self.sessions:
            if session.tr_id == tr_id:
                return session
        return None
    
    def get_field_mapping(self, tr_id: str) -> Optional[FieldMapping]:
        """TR_ID에 해당하는 필드 매핑 반환"""
        return self.field_mappings.get(tr_id)
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """종목 정보 반환 (StockManager 사용)"""
        return self.stock_manager.get_stock_info(stock_code)
    
    def get_active_sessions(self, market_filter: Optional[List[str]] = None) -> List[MarketSession]:
        """활성화 가능한 세션들 반환"""
        if market_filter:
            return [s for s in self.sessions 
                   if s.market_type.value.split('_')[0] in market_filter]
        return self.sessions
    
    def should_switch_session(self, current_tr_id: Optional[str]) -> Optional[MarketSession]:
        """세션 전환이 필요한지 확인하고 새 세션 반환"""
        current_session = self.get_current_session()
        
        if not current_session:
            return None
            
        if current_tr_id != current_session.tr_id:
            logging.info(f"Session switch needed: {current_tr_id} -> {current_session.tr_id}")
            return current_session
            
        return None
    
    def format_market_data(self, tr_id: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """원시 데이터를 표준 형식으로 변환"""
        field_mapping = self.get_field_mapping(tr_id)
        if not field_mapping:
            return raw_data
        
        session = self.get_session_by_tr_id(tr_id)
        stock_code = raw_data.get(field_mapping.essential_fields["stock_code"])
        
        # 해외주식의 경우 SYMB에서 실제 종목코드 추출
        if tr_id == "HDFSCNT0" and stock_code:
            # DNAS,AAPL 형식에서 AAPL만 추출
            if "," in stock_code:
                stock_code = stock_code.split(",")[1]
        
        stock_info = self.get_stock_info(stock_code) if stock_code else None
        
        formatted_data = {
            "tr_id": tr_id,
            "market_type": session.market_type.value if session else "unknown",
            "data_type": session.data_type.value if session else "execution",
            "timestamp": datetime.now().isoformat(),
            "stock_code": stock_code,
            "stock_name": stock_info["name"] if stock_info else f"Unknown({stock_code})",
            "market": stock_info["market"] if stock_info else "Unknown",
            "currency": stock_info["currency"] if stock_info else "Unknown"
        }
        
        # 핵심 필드 매핑
        for internal_field, external_field in field_mapping.essential_fields.items():
            formatted_data[internal_field] = raw_data.get(external_field)
        
        # 해외주식 특화 필드 추가
        if tr_id == "HDFSCNT0":
            mtyp = raw_data.get("MTYP")
            formatted_data["market_status_desc"] = self._get_market_status_desc(mtyp or "")
            formatted_data["local_time"] = raw_data.get("XHMS")  # 현지 시간
            formatted_data["korea_time"] = raw_data.get("KHMS")  # 한국 시간
        
        # 원시 데이터 유지 (디버깅용)
        formatted_data["raw_data"] = raw_data
        
        return formatted_data
    
    def _get_market_status_desc(self, mtyp: str) -> str:
        """시장 상태 코드를 설명으로 변환"""
        status_map = {
            "1": "장중",
            "2": "장전", 
            "3": "장후"
        }
        return status_map.get(mtyp, f"Unknown({mtyp})")
