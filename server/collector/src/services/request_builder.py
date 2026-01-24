"""
KIS API 요청을 위한 요청 빌더 서비스.

이 서비스는 동적 TR_ID 선택 및 주식 코드 포맷팅을 포함하여
KIS WebSocket API를 위한 요청 패킷 구성을 처리합니다.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, cast
import json
from datetime import datetime

from core import IRequestBuilder, StockInfo, IMarketManager, ITimeCalculator


@dataclass
class RequestHeader:
    """KIS API용 요청 헤더."""
    approval_key: str
    custtype: str
    tr_type: str
    content_type: str = "utf-8"


@dataclass  
class RequestInput:
    """요청 입력 매개변수."""
    tr_id: str
    tr_key: str


@dataclass
class RequestBody:
    """입력 매개변수를 포함하는 요청 본문."""
    input: RequestInput


@dataclass
class RequestPacket:
    """KIS API용 완전한 요청 패킷."""
    header: RequestHeader
    body: RequestBody

    def to_json_packet(self) -> str:
        """KIS API에서 요구하는 JSON 형식으로 변환합니다."""
        data_dict: Dict[str, Any] = asdict(self)
        
        # KIS API 호환성을 위한 헤더 필드명 수정
        header_dict = data_dict['header']
        if 'content_type' in header_dict:
            content_value = header_dict.pop('content_type')
            header_dict['content-type'] = content_value
            
        return json.dumps(data_dict) + '\n'


class RequestBuilderService(IRequestBuilder):
    """KIS API 요청을 빌드하는 서비스."""
    
    def __init__(
        self,
        market_manager: IMarketManager,
        time_calculator: ITimeCalculator,
        approval_key: Optional[str] = None
    ):
        self._market_manager = market_manager
        self._time_calculator = time_calculator
        self._approval_key = approval_key
    
    def build_subscription_request(self, stocks: List[StockInfo]) -> Dict[str, Any]:
        """주어진 주식들에 대한 구독 요청을 빌드합니다.
        
        Args:
            stocks: 구독할 주식 목록
            
        Returns:
            마켓/TR_ID별로 구성된 요청 데이터를 포함하는 딕셔너리
        """
        # 마켓별로 주식 분류
        stocks_by_market = self._market_manager.classify_stocks_by_market(stocks)
        
        requests = {}
        
        for market_name, market_stocks in stocks_by_market.items():
            try:
                market_provider = self._market_manager.get_market_provider(market_name)
                tr_id = market_provider.get_tr_id()
                
                # 이 마켓용 주식 코드 포맷팅
                formatted_codes = []
                for stock in market_stocks:
                    try:
                        if market_name == "US":
                            # 미국 주식은 거래 세션에 따른 특별한 포맷팅이 필요
                            formatted_code = self._format_us_stock_code(stock.code)
                        else:
                            # KRX 및 기타 마켓은 주식 코드를 그대로 사용
                            formatted_code = market_provider.format_stock_code(stock.code)
                        formatted_codes.append(formatted_code)
                    except ValueError as e:
                        print(f"Warning: Skipping invalid stock code {stock.code}: {e}")
                        continue
                
                if formatted_codes:
                    # 이 마켓용 요청 생성
                    request_packet = self._create_request_packet(
                        tr_id=tr_id,
                        stock_codes=formatted_codes,
                        tr_type="1"  # 구독
                    )
                    
                    requests[f"{market_name}_{tr_id}"] = {
                        "packet": request_packet,
                        "stocks": market_stocks,
                        "market": market_name,
                        "tr_id": tr_id
                    }
            
            except Exception as e:
                print(f"Error building request for {market_name}: {e}")
                continue
        
        return requests
    
    def build_unsubscription_request(self, stocks: List[StockInfo]) -> Dict[str, Any]:
        """주어진 주식들에 대한 구독 해제 요청을 빌드합니다.
        
        Args:
            stocks: 구독 해제할 주식 목록
            
        Returns:
            구독 해제 요청 데이터를 포함하는 딕셔너리
        """
        # 구독과 유사한 로직이지만 tr_type="2" 사용
        stocks_by_market = self._market_manager.classify_stocks_by_market(stocks)
        
        requests = {}
        
        for market_name, market_stocks in stocks_by_market.items():
            try:
                market_provider = self._market_manager.get_market_provider(market_name)
                tr_id = market_provider.get_tr_id()
                
                # 주식 코드 포맷팅
                formatted_codes = []
                for stock in market_stocks:
                    try:
                        if market_name == "US":
                            formatted_code = self._format_us_stock_code(stock.code)
                        else:
                            formatted_code = market_provider.format_stock_code(stock.code)
                        formatted_codes.append(formatted_code)
                    except ValueError:
                        continue
                
                if formatted_codes:
                    request_packet = self._create_request_packet(
                        tr_id=tr_id,
                        stock_codes=formatted_codes,
                        tr_type="2"  # 구독 해제
                    )
                    
                    requests[f"{market_name}_{tr_id}"] = {
                        "packet": request_packet,
                        "stocks": market_stocks,
                        "market": market_name,
                        "tr_id": tr_id
                    }
                    
            except Exception as e:
                print(f"Error building unsubscription request for {market_name}: {e}")
                continue
        
        return requests
    
    def _create_request_packet(self, tr_id: str, stock_codes: List[str], tr_type: str) -> RequestPacket:
        """주어진 매개변수에 대한 요청 패킷을 생성합니다.
        
        Args:
            tr_id: 트랜잭션 ID
            stock_codes: 포맷된 주식 코드 목록
            tr_type: 트랜잭션 타입 (구독은 "1", 구독 해제는 "2")
            
        Returns:
            전송 준비가 된 RequestPacket
        """
        # 주식 코드들을 결합하여 tr_key 생성
        tr_key = '^'.join(stock_codes)
        
        # approval_key가 있으면 사용, 없으면 테스트용으로 빈 문자열 사용
        approval_key = self._approval_key if self._approval_key is not None else ""
        
        header = RequestHeader(
            approval_key=approval_key,
            custtype="P",  # 개인 고객 타입
            tr_type=tr_type
        )
        
        input_data = RequestInput(
            tr_id=tr_id,
            tr_key=tr_key
        )
        
        body = RequestBody(input=input_data)
        
        return RequestPacket(header=header, body=body)
    
    def _format_us_stock_code(self, stock_code: str) -> str:
        """현재 거래 세션을 기반으로 미국 주식 코드를 포맷합니다.
        
        Args:
            stock_code: 원시 미국 주식 심볼 (예: AAPL)
            
        Returns:
            KIS API용 포맷된 주식 코드 (예: DNASAAPL, RBAYAAPL)
        """
        try:
            us_provider = self._market_manager.get_market_provider("US")
            
            # 세션 기반 포맷팅을 지원하는 미국 마켓 프로바이더인지 확인
            if hasattr(us_provider, 'format_stock_code_with_session'):
                # 특정 메서드에 액세스하기 위한 타입 캐스팅
                from markets.us import USMarketProvider
                us_provider_typed = cast(USMarketProvider, us_provider)
                return us_provider_typed.format_stock_code_with_session(stock_code)
            else:
                # 폴백: 수동으로 세션을 결정하고 표준 메서드 사용
                current_time = datetime.now()
                is_night = self._time_calculator.is_trading_hours("US", current_time)
                return us_provider.format_stock_code(stock_code, is_night_trading=not is_night)
                
        except Exception as e:
            # 시간 계산이 실패할 경우 기본 포맷팅으로 최종 폴백
            print(f"Warning: Using fallback formatting for {stock_code}: {e}")
            us_provider = self._market_manager.get_market_provider("US")
            return us_provider.format_stock_code(stock_code, is_night_trading=False)
    
    def get_formatted_stock_codes(self, stocks: List[StockInfo]) -> Dict[str, List[str]]:
        """마켓별로 그룹화된 포맷된 주식 코드를 가져옵니다.
        
        Args:
            stocks: 포맷할 주식 목록
            
        Returns:
            마켓명을 포맷된 코드 목록에 매핑하는 딕셔너리
        """
        stocks_by_market = self._market_manager.classify_stocks_by_market(stocks)
        result = {}
        
        for market_name, market_stocks in stocks_by_market.items():
            try:
                market_provider = self._market_manager.get_market_provider(market_name)
                formatted_codes = []
                
                for stock in market_stocks:
                    try:
                        if market_name == "US":
                            formatted_code = self._format_us_stock_code(stock.code)
                        else:
                            formatted_code = market_provider.format_stock_code(stock.code)
                        formatted_codes.append(formatted_code)
                    except ValueError:
                        continue
                
                result[market_name] = formatted_codes
                
            except Exception as e:
                print(f"Error formatting codes for {market_name}: {e}")
                result[market_name] = []
        
        return result
    
    def get_current_tr_id(self, market_filter: Optional[List[str]] = None) -> Dict[str, str]:
        """마켓들의 현재 TR ID를 가져옵니다.
        
        Args:
            market_filter: 필터링할 마켓명 목록 (선택사항)
            
        Returns:
            마켓명을 TR ID에 매핑하는 딕셔너리
        """
        result = {}
        
        # 모든 시장이나 필터된 시장들의 TR_ID를 가져오기
        available_markets = self._market_manager.get_available_markets()
        
        for market_name in available_markets:
            # market_filter가 있으면 해당 시장만 포함
            if market_filter and market_name.lower() not in [m.lower() for m in market_filter]:
                continue
                
            try:
                market_provider = self._market_manager.get_market_provider(market_name)
                tr_id = market_provider.get_tr_id()
                result[market_name.lower()] = tr_id
            except Exception as e:
                print(f"Warning: Could not get TR_ID for market {market_name}: {e}")
                continue
        
        return result
    
    def validate_market_configuration(self) -> bool:
        """필요한 모든 마켓이 적절히 구성되어 있는지 검증합니다.
        
        Returns:
            모든 마켓이 유효하면 True, 그렇지 않으면 False
        """
        try:
            available_markets = self._market_manager.get_available_markets()
            if not available_markets:
                print("Error: No markets available")
                return False
            
            # 각 시장의 TR_ID 확인
            for market_name in available_markets:
                try:
                    market_provider = self._market_manager.get_market_provider(market_name)
                    tr_id = market_provider.get_tr_id()
                    print(f"✅ Market {market_name}: TR_ID = {tr_id}")
                except Exception as e:
                    print(f"❌ Market {market_name}: Error = {e}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error validating market configuration: {e}")
            return False
