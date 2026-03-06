"""
Market Manager Service

다중 시장을 관리하는 서비스 구현.
각 시장의 제공자(provider)를 관리하고 종목을 시장별로 분류하는 기능 제공.
"""

from typing import Dict, List, Set, Optional
import logging

from core import IMarketManager, IMarketProvider, StockInfo, MarketSession
from markets import KRXMarketProvider, USMarketProvider


class MarketManagerService(IMarketManager):
    """시장 관리 서비스 구현"""
    
    def __init__(self):
        """마켓 매니저 서비스 초기화"""
        self._providers: Dict[str, IMarketProvider] = {}
        self._initialize_providers()
        
    def _initialize_providers(self) -> None:
        """시장 제공자들 초기화"""
        try:
            # KRX (한국 주식시장) 제공자 - 통합 API 사용 (장중 + 장외)
            krx_provider = KRXMarketProvider()
            logging.info(f"🔄 KRX 통합 모드 (H0UNCNT0) - 정규장 + 시간외 거래")
                
            self._providers["KRX"] = krx_provider
            self._providers["KOSPI"] = krx_provider
            self._providers["KOSDAQ"] = krx_provider
            
            # US (미국 주식시장) 제공자  
            us_provider = USMarketProvider()
            self._providers["US"] = us_provider
            self._providers["NASDAQ"] = us_provider
            self._providers["NYSE"] = us_provider
            self._providers["AMEX"] = us_provider
            
            logging.info(f"✅ 시장 초기화 완료 ({len(self._providers)}개 시장)")
            
        except Exception as e:
            logging.error(f"❌ MarketManagerService 초기화 실패: {e}")
            raise
    
    def get_supported_markets(self) -> Set[str]:
        """지원되는 시장 이름들 반환"""
        return set(self._providers.keys())
    
    def get_available_markets(self) -> List[str]:
        """사용 가능한 시장 이름들을 리스트로 반환"""
        # 중복 제거를 위해 주 시장만 반환 (알리아스 제외)
        main_markets = []
        processed_providers = set()
        
        for market_name, provider in self._providers.items():
            provider_id = id(provider)
            if provider_id not in processed_providers:
                main_markets.append(market_name)
                processed_providers.add(provider_id)
        
        return sorted(main_markets)  # 정렬된 순서로 반환
    
    def get_market_provider(self, market: str) -> IMarketProvider:
        """지정된 시장의 제공자 반환"""
        market_upper = market.upper()
        if market_upper not in self._providers:
            raise ValueError(f"지원되지 않는 시장: {market}. 지원 시장: {list(self._providers.keys())}")
        
        return self._providers[market_upper]
    
    def classify_stocks_by_market(self, stocks: List[StockInfo]) -> Dict[str, List[StockInfo]]:
        """종목들을 시장별로 분류"""
        classified: Dict[str, List[StockInfo]] = {}
        
        for stock in stocks:
            # 종목의 market 속성이 있고 비어있지 않으면 사용
            if hasattr(stock, 'market') and stock.market and stock.market.strip():
                market = stock.market.upper()
                logging.debug(f"종목 {stock.code}: 명시된 시장 사용 -> {market}")
            else:
                # market 속성이 없거나 비어있으면 코드 패턴으로 추정
                market = self._detect_market_from_code(stock.code)
                logging.debug(f"종목 {stock.code}: 코드 패턴으로 감지 -> {market}")
            
            if market not in classified:
                classified[market] = []
            classified[market].append(stock)
        
        # 로그 간소화 - 디버그 레벨로 변경
        logging.debug(f"종목 분류 완료: {dict((k, len(v)) for k, v in classified.items())}")
        return classified
    
    def _detect_market_from_code(self, code: str) -> str:
        """종목 코드 패턴으로 시장 감지"""
        # 한국 주식: 6자리 숫자
        if len(code) == 6 and code.isdigit():
            return "KRX"
        
        # 미국 주식: 알파벳 심볼
        if code.isalpha() and len(code) <= 5:  # 미국 주식은 보통 1-5자리 알파벳
            return "US"
        
        # 기본값
        logging.warning(f"시장 감지 실패, 기본값 사용: {code} -> KRX")
        return "KRX"
    
    def get_active_sessions(self) -> Dict[str, MarketSession]:
        """현재 활성 시장 세션들 반환"""
        active_sessions: Dict[str, MarketSession] = {}
        
        for market_name, provider in self._providers.items():
            try:
                session = provider.get_session_config()
                # 중복 제거 (알리아스들) - provider의 market_name 사용
                provider_market = provider.get_market_name()
                if provider_market not in [self._providers[k].get_market_name() for k in active_sessions.keys()]:
                    active_sessions[market_name] = session
            except Exception as e:
                logging.warning(f"시장 {market_name} 세션 가져오기 실패: {e}")
        
        return active_sessions
    
    def get_session_by_tr_id(self, tr_id: str) -> Optional[MarketSession]:
        """TR ID로 세션 찾기 (레거시 호환성)"""
        for provider in self._providers.values():
            if provider.get_tr_id() == tr_id:
                return provider.get_session_config()
        return None
    
    def format_market_data(self, tr_id: str, raw_data: Dict) -> Optional[Dict]:
        """시장 데이터 포매팅 (레거시 호환성)"""
        # 이 기능은 DataParser 서비스로 이전될 예정
        # 임시로 기본 구조 반환
        return {
            "tr_id": tr_id,
            "data": raw_data,
            "formatted_at": "MarketManagerService"
        }
