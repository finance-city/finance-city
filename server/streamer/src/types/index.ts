// types/index.ts - 모든 타입의 통합 export

// 설정 타입
export * from './config.types.js';

// 도메인 타입
export * from './domain.types.js';

// 어댑터 인터페이스
export * from './adapters.types.js';

// 시장 타입
export enum MarketType {
    KRX = 'KRX',
    US = 'US'
}

// WebSocket 메시지 타입
export interface WebSocketMessage<T = any> {
    type: 'stock_data' | 'market_status' | 'error';
    payload: T;
    timestamp: number;
}