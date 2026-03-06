"""
실시간 마켓 데이터를 위한 KIS 데이터 파서.

이 모듈은 KIS WebSocket API 응답에 대한 파싱 기능을 제공하여
원시 마켓 데이터를 구조화된 형식으로 변환합니다.
"""

import json
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from core import IDataParser, MarketData, IMarketManager, DataParsingError
from services.metrics_service import metrics_service


class KISDataParser(IDataParser):
    """KIS WebSocket API 데이터용 파서."""
    
    def __init__(self, market_manager: IMarketManager):
        """KIS 데이터 파서를 초기화합니다.
        
        Args:
            market_manager: 필드 매핑 및 포맷팅을 위한 마켓 매니저
        """
        self._market_manager = market_manager
        
        # TR_ID별 필드 매핑 캐시
        self._field_cache: Dict[str, Dict[str, str]] = {}
        
        # 마켓 탐지를 위한 알려진 TR_ID 패턴
        self._tr_id_market_map = {
            'H0UNCNT0': 'KRX',      # KRX 통합 (정규 + 시간외)
            'HDFSCNT0': 'US'        # US 마켓
        }
    
    def parse_realtime_data(self, message: str, market: str) -> Optional[MarketData]:
        """WebSocket 메시지에서 실시간 마켓 데이터를 파싱합니다.
        
        Args:
            message: 원시 WebSocket 메시지
            market: 마켓 식별자 힌트 (TR_ID 탐지에 의해 재정의될 수 있음)
            
        Returns:
            파싱된 MarketData 객체, 파싱 실패 시 None
        """
        start_time = time.perf_counter()
        
        try:
            # JSON 메시지 파싱
            data = json.loads(message.strip())
            
            # 헤더 정보 추출
            header = data.get('header', {})
            body = data.get('body', {})
            
            tr_id = header.get('tr_id')
            if not tr_id:
                return None
            
            # TR_ID에서 마켓 결정 (힌트를 재정의)
            detected_market = self._tr_id_market_map.get(tr_id, market)
            
            # 출력 데이터 가져오기
            output = body.get('output', {})
            if not output:
                return None
            
            # 마켓 데이터 파싱
            market_data = self._parse_market_data(output, detected_market, tr_id)
            
            # 메트릭: 처리 시간 기록
            duration = time.perf_counter() - start_time
            metrics_service.record_processing_time(detected_market.lower(), duration)
            
            # 메트릭: 틱 카운트 (파싱 성공 시)
            if market_data and market_data.stock_code:
                metrics_service.record_tick(detected_market.lower(), market_data.stock_code)
            
            return market_data
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # 메트릭: 파싱 에러
            metrics_service.record_error(market.lower(), 'parsing')
            raise DataParsingError(
                f"Failed to parse WebSocket message: {e}",
                raw_data=message[:500],  # 로깅을 위해 자르기
                parser_type="kis_realtime"
            )
        except Exception as e:
            # 메트릭: 기타 에러
            metrics_service.record_error(market.lower(), 'unknown')
            raise DataParsingError(
                f"Unexpected parsing error: {e}",
                raw_data=message[:500],
                parser_type="kis_realtime"
            )
    
    def parse_error_message(self, message: str) -> Optional[str]:
        """WebSocket 응답에서 에러 메시지를 파싱합니다.
        
        Args:
            message: 파싱할 WebSocket 메시지
            
        Returns:
            발견된 에러 메시지, 없으면 None
        """
        try:
            data = json.loads(message.strip())
            
            # 헤더에서 에러 확인
            header = data.get('header', {})
            if header.get('tr_cd') != '0':
                return f"Error {header.get('tr_cd')}: {header.get('tr_msg', 'Unknown error')}"
            
            # 바디에서 에러 확인
            body = data.get('body', {})
            if body.get('rt_cd') != '0':
                return f"Runtime Error {body.get('rt_cd')}: {body.get('rt_msg', 'Unknown error')}"
            
            return None
            
        except (json.JSONDecodeError, KeyError):
            # 일반 텍스트 메시지에서 에러 추출 시도
            if 'error' in message.lower() or 'fail' in message.lower():
                return message.strip()
            return None
    
    def _parse_market_data(self, output: Dict[str, Any], market: str, tr_id: str) -> Optional[MarketData]:
        """마켓별 데이터 형식을 파싱합니다.
        
        Args:
            output: WebSocket 메시지의 출력 데이터
            market: 마켓 식별자
            tr_id: 필드 매핑을 위한 트랜잭션 ID
            
        Returns:
            MarketData 객체 또는 파싱 실패 시 None
        """
        try:
            # 이 마켓/TR_ID에 대한 필드 매핑 가져오기
            field_config = self._get_field_config(market, tr_id)
            
            # 기본 정보 추출
            stock_code = self._extract_field_value(output, field_config, 'stock_code')
            stock_name = self._extract_field_value(output, field_config, 'stock_name')
            
            if not stock_code:
                return None
            
            # 종목 코드 정리 (KIS 포맷이 있다면 제거)
            clean_code = self._clean_stock_code(stock_code, market)
            
            # 가격 정보 추출
            price = self._extract_numeric_field(output, field_config, 'current_price', 0.0) or 0.0
            change = self._extract_numeric_field(output, field_config, 'change', 0.0) or 0.0
            change_rate = self._extract_numeric_field(output, field_config, 'change_rate', 0.0) or 0.0
            volume = int(self._extract_numeric_field(output, field_config, 'volume', 0, int) or 0)
            
            # 옵셔널 필드 추출
            ask_price = self._extract_numeric_field(output, field_config, 'ask_price')
            bid_price = self._extract_numeric_field(output, field_config, 'bid_price')
            high_price = self._extract_numeric_field(output, field_config, 'high_price')
            low_price = self._extract_numeric_field(output, field_config, 'low_price')
            open_price = self._extract_numeric_field(output, field_config, 'open_price')
            prev_close = self._extract_numeric_field(output, field_config, 'prev_close')
            
            # MarketData 객체 생성
            return MarketData(
                stock_code=clean_code,
                stock_name=stock_name or clean_code,
                market=market,
                timestamp=datetime.now(),
                price=price,
                change=change,
                change_rate=change_rate,
                volume=volume,
                ask_price=ask_price,
                bid_price=bid_price,
                high=high_price,
                low=low_price,
                open_price=open_price,
                prev_close=prev_close,
                raw_data=output
            )
            
        except Exception as e:
            raise DataParsingError(
                f"Failed to parse market data for {market}: {e}",
                parser_type=f"market_data_{market}"
            )
    
    def _get_field_config(self, market: str, tr_id: str) -> Dict[str, str]:
        """마켓과 TR_ID에 대한 필드 설정을 가져옵니다.
        
        Args:
            market: 마켓 식별자
            tr_id: 트랜잭션 ID
            
        Returns:
            필드 이름을 데이터 위치에 매핑하는 딕셔너리
        """
        cache_key = f"{market}_{tr_id}"
        
        if cache_key not in self._field_cache:
            try:
                market_provider = self._market_manager.get_market_provider(market)
                field_config = market_provider.get_field_config()
                self._field_cache[cache_key] = field_config.fields
            except Exception as e:
                print(f"Warning: Failed to get field config for {market}/{tr_id}: {e}")
                self._field_cache[cache_key] = {}
        
        return self._field_cache[cache_key]
    
    def _extract_field_value(self, output: Dict[str, Any], field_config: Dict[str, str], field_name: str) -> Optional[str]:
        """출력 데이터에서 필드 값을 추출합니다.
        
        Args:
            output: 출력 데이터 딕셔너리
            field_config: 필드 설정 매핑
            field_name: 추출할 필드의 이름
            
        Returns:
            문자열로 된 필드 값, 찾을 수 없으면 None
        """
        field_position = field_config.get(field_name)
        if field_position is None:
            return None
        
        return output.get(field_position, '').strip()
    
    def _extract_numeric_field(
        self, 
        output: Dict[str, Any], 
        field_config: Dict[str, str], 
        field_name: str, 
        default_value: Optional[float] = None,
        value_type: type = float
    ) -> Optional[float]:
        """출력 데이터에서 숫자 필드 값을 추출합니다.
        
        Args:
            output: 출력 데이터 딕셔너리
            field_config: 필드 설정 매핑
            field_name: 추출할 필드의 이름
            default_value: 필드가 없거나 유효하지 않으면 사용할 기본값
            value_type: 변환할 타입 (float 또는 int)
            
        Returns:
            숫자 값 또는 default_value
        """
        field_value = self._extract_field_value(output, field_config, field_name)
        
        if not field_value:
            return default_value
        
        try:
            # 일반적인 포맷 문자 제거
            cleaned_value = re.sub(r'[,\s%]', '', field_value)
            
            # 음수 값 처리
            if cleaned_value.startswith('-') or cleaned_value.endswith('-'):
                cleaned_value = cleaned_value.replace('-', '')
                sign = -1
            else:
                sign = 1
            
            # 숫자로 변환
            if value_type == int:
                return sign * int(float(cleaned_value))
            else:
                return sign * float(cleaned_value)
                
        except (ValueError, TypeError):
            return default_value
    
    def _clean_stock_code(self, raw_code: str, market: str) -> str:
        """KIS 포맷을 제거하여 종목 코드를 정리합니다.
        
        Args:
            raw_code: API에서 받은 원시 종목 코드
            market: 마켓 식별자
            
        Returns:
            정리된 종목 코드
        """
        if not raw_code:
            return raw_code
        
        if market == 'US':
            # US 주식에서 KIS 포맷 제거 (DNASAAPL -> AAPL)
            match = re.match(r'^[DR][A-Z]{3}([A-Z]+)$', raw_code.upper())
            if match:
                return match.group(1)
        
        return raw_code.strip()
    
    def validate_market_data(self, market_data: MarketData) -> bool:
        """파싱된 마켓 데이터를 검증합니다.
        
        Args:
            market_data: 검증할 MarketData 객체
            
        Returns:
            유효하면 True, 그렇지 않으면 False
        """
        # 기본 검증
        if not market_data.stock_code or not market_data.market:
            return False
        
        # 가격 검증
        if market_data.price < 0:
            return False
        
        # 거래량 검증 (일부 마켓에서는 0 허용)
        if market_data.volume < 0:
            return False
        
        return True
    
    def get_supported_tr_ids(self) -> List[str]:
        """지원되는 TR ID 목록을 가져옵니다.
        
        Returns:
            TR ID 문자열 목록
        """
        return list(self._tr_id_market_map.keys())
    
    def clear_field_cache(self) -> None:
        """필드 설정 캐시를 지웁니다."""
        self._field_cache.clear()
