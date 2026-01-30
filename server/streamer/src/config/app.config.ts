// config/app.config.ts - 설정 로더 (타입은 types에서 import)

import type { AppConfig } from '../types/index.js';

export const loadConfig = (): AppConfig => ({
    redis: {
        host: process.env.REDIS_HOST || 'localhost',
        port: Number(process.env.REDIS_PORT) || 6379,
        channels: (process.env.REDIS_CHANNELS || 'stock:realtime').split(','),
        channel: process.env.REDIS_CHANNEL || 'stock:realtime', // 호환성
    },
    websocket: {
        port: Number(process.env.WS_PORT) || 8081,
        maxConnections: Number(process.env.MAX_CONNECTIONS) || 1000,
    },
    throttler: {
        flushIntervalMs: Number(process.env.FLUSH_INTERVAL_MS) || 100,
    },
    logging: {
        level: (process.env.LOG_LEVEL as 'debug' | 'info' | 'warn' | 'error') || 'info',
    },
});