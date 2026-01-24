"""
주식 관리 서비스.

이 서비스는 CSV에서 로딩, 필터링, 마켓별 분류를 포함한
주식 정보 관리를 제공합니다.
"""

import csv
from pathlib import Path
from typing import List, Dict, Optional, Set, Any
from datetime import datetime

from core import IStockManager, StockInfo, ResourceError, ValidationError


class StockService(IStockManager):
    """주식 정보 관리 서비스."""
    
    def __init__(self, csv_file_path: str = "stocks.csv"):
        """주식 서비스를 초기화합니다.
        
        Args:
            csv_file_path: 주식 데이터를 포함하는 CSV 파일 경로
        """
        self._csv_file_path = Path(csv_file_path)
        self._stocks: Dict[str, StockInfo] = {}
        self._loaded_at: Optional[datetime] = None
    
    def load_stocks(self) -> None:
        """CSV 파일에서 주식 데이터를 로드합니다.
        
        Raises:
            ResourceError: CSV 파일을 읽을 수 없는 경우
            ValidationError: CSV 데이터가 유효하지 않은 경우
        """
        if not self._csv_file_path.exists():
            raise ResourceError(
                f"Stock CSV file not found: {self._csv_file_path}",
                resource_type="file",
                resource_path=str(self._csv_file_path)
            )
        
        try:
            stocks = {}
            
            with open(self._csv_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # CSV 헤더 검증
                expected_headers = {'stock_code', 'name', 'market', 'status'}
                actual_headers = set(reader.fieldnames or [])
                
                if not expected_headers.issubset(actual_headers):
                    missing_headers = expected_headers - actual_headers
                    raise ValidationError(
                        f"Missing required CSV headers: {missing_headers}",
                        validation_type="csv_headers",
                        invalid_data={"missing": list(missing_headers)}
                    )
                
                for row_num, row in enumerate(reader, start=2):  # 2부터 시작 (헤더가 1행)
                    try:
                        stock_info = self._parse_stock_row(row, row_num)
                        stocks[stock_info.code] = stock_info
                    except ValidationError as e:
                        print(f"Warning: Skipping invalid row {row_num}: {e}")
                        continue
            
            self._stocks = stocks
            self._loaded_at = datetime.now()
            
            print(f"Loaded {len(self._stocks)} stocks from {self._csv_file_path}")
            
        except (IOError, OSError) as e:
            raise ResourceError(
                f"Failed to read stock CSV file: {e}",
                resource_type="file",
                resource_path=str(self._csv_file_path)
            )
    
    def get_active_stocks(self) -> List[StockInfo]:
        """활성 주식 목록을 가져옵니다.
        
        Returns:
            활성 주식들의 StockInfo 객체 목록
        """
        return [stock for stock in self._stocks.values() if stock.is_active()]
    
    def get_stocks_by_market(self, market: str) -> List[StockInfo]:
        """마켓별로 필터링된 주식을 가져옵니다.
        
        Args:
            market: 마켓명 (예: 'KRX', 'US', 'NASDAQ', 'NYSE')
            
        Returns:
            지정된 마켓의 StockInfo 객체 목록
        """
        market_upper = market.upper()
        
        # 특정 미국 거래소 처리
        if market_upper in ['NASDAQ', 'NYSE', 'AMEX']:
            return [
                stock for stock in self._stocks.values()
                if stock.exchange and stock.exchange.upper() == market_upper
            ]
        
        # 광범위한 마켓 카테고리 처리
        return [
            stock for stock in self._stocks.values()
            if stock.market.upper() == market_upper
        ]
    
    def is_stock_active(self, code: str) -> bool:
        """주식이 활성 상태인지 확인합니다.
        
        Args:
            code: 확인할 주식 코드
            
        Returns:
            주식이 존재하고 활성 상태이면 True
        """
        stock = self._stocks.get(code)
        return stock is not None and stock.is_active()
    
    def add_stock(self, stock_info: StockInfo) -> None:
        """새로운 주식을 추가합니다.
        
        Args:
            stock_info: 추가할 주식 정보
        """
        self._stocks[stock_info.code] = stock_info
        print(f"Added stock: {stock_info.get_display_name()}")
    
    def remove_stock(self, code: str) -> None:
        """주식을 제거합니다.
        
        Args:
            code: 제거할 주식 코드
        """
        if code in self._stocks:
            removed_stock = self._stocks.pop(code)
            print(f"Removed stock: {removed_stock.get_display_name()}")
        else:
            print(f"Warning: Stock {code} not found for removal")
    
    def get_stock_info(self, code: str) -> Optional[StockInfo]:
        """코드로 주식 정보를 가져옵니다.
        
        Args:
            code: 조회할 주식 코드
            
        Returns:
            찾으면 StockInfo 객체, 그렇지 않으면 None
        """
        return self._stocks.get(code)
    
    def get_all_stocks(self) -> List[StockInfo]:
        """상태에 관계없이 모든 주식을 가져옵니다.
        
        Returns:
            모든 StockInfo 객체의 목록
        """
        return list(self._stocks.values())
    
    def get_stock_count(self) -> Dict[str, Any]:
        """주식 수 통계를 가져옵니다.
        
        Returns:
            수 통계를 포함하는 딕셔너리
        """
        all_stocks = list(self._stocks.values())
        active_stocks = [s for s in all_stocks if s.is_active()]
        
        market_counts = {}
        for stock in active_stocks:
            market = stock.market.upper()
            market_counts[market] = market_counts.get(market, 0) + 1
        
        return {
            "total": len(all_stocks),
            "active": len(active_stocks),
            "inactive": len(all_stocks) - len(active_stocks),
            "by_market": market_counts
        }
    
    def update_stock_status(self, code: str, status: str) -> bool:
        """주식 상태를 업데이트합니다.
        
        Args:
            code: 업데이트할 주식 코드
            status: 새로운 상태 ('active', 'inactive' 등)
            
        Returns:
            성공적으로 업데이트되면 True, 주식을 찾지 못하면 False
        """
        stock = self._stocks.get(code)
        if stock:
            stock.status = status.lower()
            return True
        return False
    
    def save_stocks_to_csv(self, file_path: Optional[str] = None) -> None:
        """현재 주식을 CSV 파일에 저장합니다.
        
        Args:
            file_path: 선택적 사용자 지정 파일 경로, 기본적으로 원본 CSV 경로 사용
        """
        output_path = Path(file_path) if file_path else self._csv_file_path
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['stock_code', 'name', 'market', 'status', 'exchange']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for stock in sorted(self._stocks.values(), key=lambda s: s.code):
                    writer.writerow({
                        'stock_code': stock.code,
                        'name': stock.name,
                        'market': stock.market,
                        'status': stock.status,
                        'exchange': stock.exchange or ''
                    })
            
            print(f"Saved {len(self._stocks)} stocks to {output_path}")
            
        except (IOError, OSError) as e:
            raise ResourceError(
                f"Failed to save stocks to CSV: {e}",
                resource_type="file",
                resource_path=str(output_path)
            )
    
    def _parse_stock_row(self, row: Dict[str, str], row_num: int) -> StockInfo:
        """단일 CSV 행을 StockInfo로 파싱합니다.
        
        Args:
            row: 딕셔너리로된 CSV 행 데이터
            row_num: 오류 보고용 행 번호
            
        Returns:
            StockInfo 객체
            
        Raises:
            ValidationError: 행 데이터가 유효하지 않은 경우
        """
        try:
            code = row.get('stock_code', '').strip()
            name = row.get('name', '').strip()
            market = row.get('market', '').strip().upper()
            status = row.get('status', 'active').strip().lower()
            exchange = row.get('exchange', '').strip().upper() or None
            
            # 필수 필드 검증
            if not code:
                raise ValidationError(
                    f"Empty stock_code in row {row_num}",
                    validation_type="required_field",
                    invalid_data={"row": row_num, "field": "stock_code"}
                )
            
            if not name:
                raise ValidationError(
                    f"Empty name in row {row_num}",
                    validation_type="required_field", 
                    invalid_data={"row": row_num, "field": "name"}
                )
            
            if not market:
                raise ValidationError(
                    f"Empty market in row {row_num}",
                    validation_type="required_field",
                    invalid_data={"row": row_num, "field": "market"}
                )
            
            # 마켓 값 검증
            valid_markets = {'KRX', 'US', 'NASDAQ', 'NYSE', 'AMEX'}
            if market not in valid_markets:
                raise ValidationError(
                    f"Invalid market '{market}' in row {row_num}. Valid markets: {valid_markets}",
                    validation_type="invalid_value",
                    invalid_data={"row": row_num, "field": "market", "value": market}
                )
            
            # 미국 거래소에 대한 마켓 정규화
            if market in {'NASDAQ', 'NYSE', 'AMEX'}:
                exchange = market
                market = 'US'
            
            return StockInfo(
                code=code,
                name=name,
                market=market,
                status=status,
                exchange=exchange
            )
            
        except KeyError as e:
            raise ValidationError(
                f"Missing field {e} in row {row_num}",
                validation_type="missing_field",
                invalid_data={"row": row_num, "missing_field": str(e)}
            )
    
    def get_load_info(self) -> Dict[str, Any]:
        """마지막 데이터 로드에 대한 정보를 가져옵니다.
        
        Returns:
            로드 정보를 포함하는 딕셔너리
        """
        return {
            "csv_file_path": str(self._csv_file_path),
            "loaded_at": self._loaded_at.isoformat() if self._loaded_at else None,
            "stock_count": len(self._stocks),
            "file_exists": self._csv_file_path.exists()
        }
    
    def reload_if_changed(self) -> bool:
        """CSV 파일이 수정된 경우 주식을 다시 로드합니다.
        
        Returns:
            다시 로드되면 True, 변경이 감지되지 않으면 False
        """
        if not self._csv_file_path.exists():
            return False
        
        try:
            file_modified = datetime.fromtimestamp(self._csv_file_path.stat().st_mtime)
            
            if self._loaded_at is None or file_modified > self._loaded_at:
                print(f"CSV file modified, reloading stocks...")
                self.load_stocks()
                return True
                
        except OSError as e:
            print(f"Warning: Failed to check file modification time: {e}")
        
        return False
