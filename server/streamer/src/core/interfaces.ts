import { RedisStockMessage } from "../types/index.js";


/**
 * 메시지 브로커(Redis, Kafka 등)가 수행해야할 기능 정의
 */
export interface IMessageBroker {
    // 연결 및 해제
    connect(): Promise<void>;
    disconnect(): Promise<void>;

    // 구독 (채널명, 그리고 데이터가 오면 실행할 콜백함수)
    subscribe(
        channel: string, 
        onMessage: (message: RedisStockMessage) => void
    ): Promise<void>;

}