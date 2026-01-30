// adapters/redis-broker.ts

import { Redis } from 'ioredis';
import type { IMessageBroker } from '../core/interfaces.ts';
import type { RedisStockMessage } from '../types/index.ts';

export class RedisBroker implements IMessageBroker {
    private subscriber: Redis;

    constructor() {
        // 환경변수에서 Redis 호스트와 포트 가져오기(없을 시 기본값 사용)
        const host = process.env.REDIS_HOST || 'localhost';
        const port = Number(process.env.REDIS_PORT) || 6379;

        // Redis 클라이언트 초기화
        // lazyConnect: true 로 설정하여 명시적으로 connect() 호출 시 연결
        this.subscriber = new Redis({
            host,
            port,
            lazyConnect: true,
            retryStrategy: (times: number) => Math.min(times * 50, 2000),
        });
    }

    async connect(): Promise<void> {
        try {
            await this.subscriber.connect();
            console.log('Connected to Redis server');
        } catch (error) {
            console.error('Failed to connect to Redis server:', error);
            throw error;
        }
    }
    
    async disconnect(): Promise<void> {
        await this.subscriber.quit();
        console.log('Disconnected from Redis server');
    }

    async subscribe(
        channel: string, 
        onMessage: (message: RedisStockMessage) => void
    ): Promise<void> {

        // 1. 채널 구독
        try {
            await this.subscriber.subscribe(channel);
            console.log(`Subscribed successfully to channel: ${channel}`);
        } catch (err) {
            console.error('Failed to subscribe: ', err);
            throw err;
        }

        // 2. 메시지 수신 이벤트 리스너 등록
        this.subscriber.on('message', (subChannel: string, message: string) => {
            if (subChannel !== channel) return;

            try {
                // NaN 값을 null로 교체하여 유효한 JSON으로 만들기
                const sanitizedMessage = message.replace(/:\s*NaN/g, ': null');
                
                // 수신한 JSON 문자열을 객체로 변환
                const parsedMessage: RedisStockMessage = JSON.parse(sanitizedMessage);
                
                // 콜백 함수 호출
                onMessage(parsedMessage);
            } catch (error) {
                console.error(`❌ Error parsing Redis message on ${subChannel}:`, error);
                console.error(`📄 Raw message preview: ${message.substring(0, 200)}...`);
                // JSON 파싱 오류는 로깅 후 넘어갑니다.
            }
        });

    }
}