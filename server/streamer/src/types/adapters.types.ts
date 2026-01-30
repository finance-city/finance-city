// types/adapters.types.ts - 어댑터 인터페이스 정의

import type { RedisStockMessage, ClientStockData } from './domain.types.js';

/**
 * 메시지 브로커(Redis, Kafka 등) 추상화
 */
export interface IMessageBroker {
    connect(): Promise<void>;
    disconnect(): Promise<void>;
    subscribe(
        channel: string, 
        onMessage: (message: RedisStockMessage) => void
    ): Promise<void>;
}

/**
 * WebSocket 서버 추상화
 */
export interface IWebSocketServer {
    start(): void;
    broadcast(event: string, payload: any): void;
    stop(): void;
}

/**
 * 배치 처리 및 스로틀링 추상화
 */
export interface IThrottler {
    push(stockCode: string, data: ClientStockData): void;
    flush(): ClientStockData[];
    shouldUpdate(stockCode: string, newData: ClientStockData): boolean;
}
