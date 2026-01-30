// app.config.ts

export interface AppConfig {
    redis: {
        host: string;
        port: number;
        channels: string[];
    };
    websocket: {
        port: number;
        maxConnections: number;
    };
    logging: {
        level: 'debug' | 'info' | 'warn' | 'error';
    };
}

export const loadConfig = (): AppConfig => ({
    redis: {
        host: process.env.REDIS_HOST || 'localhost',
        port: Number(process.env.REDIS_PORT) || 6379,
        channels: (process.env.REDIS_CHANNELS || 'stock:realtime').split(','),
    },
    websocket: {
        port: Number(process.env.WS_PORT) || 8080,
        maxConnections: Number(process.env.MAX_CONNECTIONS) || 1000,
    },
    logging: {
        level: (process.env.LOG_LEVEL as 'debug' | 'info' | 'warn' | 'error') || 'info',
    },
})