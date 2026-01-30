// types/domain.types.ts - 도메인 데이터 타입

// Redis에서 수신하는 전체 데이터 구조
export interface RedisStockMessage {
    tr_id: string;
    data: StockData;
    raw_data: Record<string, any>;
    timestamp: string;
    stock_code: string;
    current_price: string;
}

// 핵심 주식 데이터 (Redis data 필드)
export interface StockData {
    code: string;       // 종목코드
    price: number;      // 현재가
    rate: number;       // 등락율
    vol_tick: number;   // 체결량
    vol_total: number;  // 누적거래량
}

// 클라이언트(WebSocket)로 전송하는 데이터
export interface ClientStockData {
    c: string;    // code - 종목코드
    p: number;    // price - 현재가  
    r: number;    // rate - 등락율
    vt: number;   // vol_tick - 체결량
    vl: number;   // vol_total - 누적거래량
    t?: number;   // timestamp - 선택적 타임스탬프 (Unix timestamp)
}
