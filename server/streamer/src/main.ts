// main.ts

import { RedisBroker } from './adapters/RedisBroker.js';
import type { RedisStockMessage } from './types/index.js';

async function main(): Promise<void> {
    console.log("Streamer server is starting...");
    
    // Redis Broker 인스턴스 생성
    const redisBroker = new RedisBroker();
    
    try {
        // Redis 서버에 연결
        await redisBroker.connect();
        
        // 주식 데이터 채널 구독
        const channel = 'stock:realtime';
        
        await redisBroker.subscribe(channel, (message: RedisStockMessage) => {
            console.log('Received stock data:', {
                stock_code: message.stock_code,
                current_price: message.current_price,
                timestamp: message.timestamp,
                tr_id: message.tr_id,
                data: message.data,
                // 전체 메시지 구조 확인용
                // fullMessage: message
            });
        });
        
        console.log(`✅ Streamer server is running and listening for messages on channel: ${channel}`);
        
        // 프로세스 종료 시 정리
        process.on('SIGINT', async () => {
            console.log('\nShutting down gracefully...');
            await redisBroker.disconnect();
            process.exit(0);
        });
        
        process.on('SIGTERM', async () => {
            console.log('\nShutting down gracefully...');
            await redisBroker.disconnect();
            process.exit(0);
        });
        
    } catch (error) {
        console.error('❌ Failed to start streamer server:', error);
        process.exit(1);
    }
}

main().catch(console.error);