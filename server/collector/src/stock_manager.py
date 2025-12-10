# stock_manager.py

import os
import csv
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StockInfo:
    """종목 정보"""
    code: str
    name: str
    market: str
    currency: str
    active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "market": self.market,
            "currency": self.currency,
            "active": self.active
        }


class StockManager:
    """종목 정보를 CSV 파일과 환경변수에서 관리"""
    
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = csv_path or self._get_default_csv_path()
        self.stocks: Dict[str, StockInfo] = {}
        self._load_stocks()
    
    def _get_default_csv_path(self) -> str:
        """기본 CSV 파일 경로"""
        current_dir = Path(__file__).parent.parent
        return str(current_dir / "stocks.csv")
    
    def _load_stocks(self):
        """CSV 파일에서 종목 정보 로드"""
        try:
            if os.path.exists(self.csv_path):
                self._load_from_csv()
            else:
                logging.warning(f"CSV file not found: {self.csv_path}")
                self._create_default_csv()
                self._load_from_csv()
        except Exception as e:
            logging.error(f"Failed to load stocks from CSV: {e}")
            self._load_fallback_stocks()
    
    def _load_from_csv(self):
        """CSV 파일에서 종목 정보 읽기"""
        with open(self.csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                active = row.get('active', 'true').lower() == 'true'
                stock_info = StockInfo(
                    code=row['stock_code'],
                    name=row['name'],
                    market=row['market'],
                    currency=row['currency'],
                    active=active
                )
                self.stocks[stock_info.code] = stock_info
        
        logging.info(f"Loaded {len(self.stocks)} stocks from CSV")
    
    def _create_default_csv(self):
        """기본 CSV 파일 생성"""
        default_stocks = [
            {'stock_code': '005930', 'name': '삼성전자', 'market': 'KRX', 'currency': 'KRW', 'active': 'true'},
            {'stock_code': '000660', 'name': 'SK하이닉스', 'market': 'KRX', 'currency': 'KRW', 'active': 'true'},
            {'stock_code': '035420', 'name': 'NAVER', 'market': 'KRX', 'currency': 'KRW', 'active': 'true'},
            {'stock_code': '035720', 'name': '카카오', 'market': 'KRX', 'currency': 'KRW', 'active': 'true'},
            {'stock_code': '051910', 'name': 'LG화학', 'market': 'KRX', 'currency': 'KRW', 'active': 'true'},
        ]
        
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as file:
            fieldnames = ['stock_code', 'name', 'market', 'currency', 'active']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(default_stocks)
        
        logging.info(f"Created default CSV file: {self.csv_path}")
    
    def _load_fallback_stocks(self):
        """CSV 로드 실패 시 폴백 데이터"""
        fallback_stocks = {
            "005930": StockInfo("005930", "삼성전자", "KRX", "KRW"),
            "000660": StockInfo("000660", "SK하이닉스", "KRX", "KRW"),
            "035420": StockInfo("035420", "NAVER", "KRX", "KRW"),
            "035720": StockInfo("035720", "카카오", "KRX", "KRW"),
            "051910": StockInfo("051910", "LG화학", "KRX", "KRW"),
            "AAPL": StockInfo("AAPL", "Apple Inc.", "NASDAQ", "USD"),
            "MSFT": StockInfo("MSFT", "Microsoft Corp.", "NASDAQ", "USD"),
            "TSLA": StockInfo("TSLA", "Tesla Inc.", "NASDAQ", "USD"),
            "GOOGL": StockInfo("GOOGL", "Alphabet Inc.", "NASDAQ", "USD"),
            "AMZN": StockInfo("AMZN", "Amazon.com Inc.", "NASDAQ", "USD"),
            "JPM": StockInfo("JPM", "JPMorgan Chase & Co.", "NYSE", "USD"),
        }
        self.stocks = fallback_stocks
        logging.warning("Using fallback stock data")
    
    def get_active_stock_codes(self) -> List[str]:
        """활성화된 종목 코드 리스트 반환 (CSV 기준)"""
        return [code for code, stock in self.stocks.items() if stock.active]
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """종목 정보 반환"""
        stock = self.stocks.get(stock_code)
        return stock.to_dict() if stock else None
    
    def get_all_stocks(self) -> Dict[str, Dict[str, Any]]:
        """모든 종목 정보 반환"""
        return {code: stock.to_dict() for code, stock in self.stocks.items()}
    
    def add_stock(self, stock_code: str, name: str, market: str = "KRX", currency: str = "KRW", active: bool = True):
        """새 종목 추가 (CSV 파일에도 저장)"""
        stock_info = StockInfo(stock_code, name, market, currency, active)
        self.stocks[stock_code] = stock_info
        self._save_to_csv()
        logging.info(f"Added new stock: {stock_code} ({name})")
    
    def update_stock_status(self, stock_code: str, active: bool):
        """종목 활성화 상태 변경"""
        if stock_code in self.stocks:
            self.stocks[stock_code].active = active
            self._save_to_csv()
            logging.info(f"Updated {stock_code} active status to {active}")
        else:
            logging.warning(f"Stock code not found: {stock_code}")
    
    def _save_to_csv(self):
        """현재 종목 정보를 CSV에 저장"""
        try:
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as file:
                fieldnames = ['stock_code', 'name', 'market', 'currency', 'active']
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                
                for code, stock in self.stocks.items():
                    writer.writerow({
                        'stock_code': code,
                        'name': stock.name,
                        'market': stock.market,
                        'currency': stock.currency,
                        'active': str(stock.active).lower()
                    })
            
            logging.info("Stock data saved to CSV")
        except Exception as e:
            logging.error(f"Failed to save stocks to CSV: {e}")
    
    def reload_stocks(self):
        """CSV 파일에서 종목 정보 다시 로드"""
        self.stocks.clear()
        self._load_stocks()
        logging.info("Stock data reloaded from CSV")


# 전역 인스턴스
_stock_manager = None

def get_stock_manager(csv_path: Optional[str] = None) -> StockManager:
    """StockManager 싱글톤 인스턴스 반환"""
    global _stock_manager
    if _stock_manager is None:
        _stock_manager = StockManager(csv_path=csv_path)
    return _stock_manager
