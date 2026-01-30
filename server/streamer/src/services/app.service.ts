// services/app.service.ts - 메인 애플리케이션 서비스

import { RedisBroker } from '../adapters/redis-broker.js';
import { WebSocketServer } from '../adapters/websocket-server.js';
import { Throttler } from '../domain/throttler.js';
import { LoggerService } from './logger.service.js';
import { DataTransformerService } from './data-transformer.service.js';
import type { RedisStockMessage, AppConfig } from '../types/index.js';

export class AppService {
    private readonly logger = LoggerService.create('AppService');
    private readonly redisBroker: RedisBroker;
    private readonly wsServer: WebSocketServer;
    private readonly throttler: Throttler;
    private readonly dataTransformer: DataTransformerService;
    private readonly config: AppConfig;
    
    private flushTimer?: NodeJS.Timeout | undefined;
    private isRunning = false;
    private startTime?: Date;

    constructor(config: AppConfig) {
        this.config = config;

        this.redisBroker = new RedisBroker();
        this.wsServer = new WebSocketServer();
        this.throttler = new Throttler(this.config.throttler.flushIntervalMs);
        this.dataTransformer = new DataTransformerService();

        this.logger.info('AppService initialized', {
            config: this.config
        });
    }

    /**
     * 애플리케이션 시작
     */
    async start(): Promise<void> {
        if (this.isRunning) {
            this.logger.warn('Service already running');
            return;
        }

        try {
            this.logger.info('Starting Finance City Streamer...');
            this.startTime = new Date();

            // 1. WebSocket 서버 시작
            await this.startWebSocketServer();
            
            // 2. Redis 연결 및 구독
            await this.startRedisConnection();
            
            // 3. 배치 처리 시작
            this.startBatchProcessor();
            
            // 4. 프로세스 종료 핸들러 등록
            this.setupGracefulShutdown();

            this.isRunning = true;
            
            this.logger.info('🚀 Finance City Streamer is running!', {
                websocket_port: this.config.websocket.port,
                redis_channel: this.config.redis.channel || this.config.redis.channels[0],
                throttler_interval: this.config.throttler.flushIntervalMs + 'ms',
                startup_time: Date.now() - this.startTime.getTime() + 'ms'
            });

        } catch (error) {
            this.logger.error('Failed to start application', error as Error);
            await this.stop();
            throw error;
        }
    }

    /**
     * 애플리케이션 종료
     */
    async stop(): Promise<void> {
        if (!this.isRunning) {
            return;
        }

        this.logger.info('Stopping Finance City Streamer...');

        try {
            // 1. 배치 처리 중지
            if (this.flushTimer) {
                clearInterval(this.flushTimer);
                this.flushTimer = undefined;
            }

            // 2. 마지막 배치 처리
            this.flushBatch();

            // 3. 서버들 종료
            this.wsServer.stop();
            await this.redisBroker.disconnect();

            this.isRunning = false;

            const uptime = this.startTime ? Date.now() - this.startTime.getTime() : 0;
            this.logger.info('✅ Finance City Streamer stopped gracefully', {
                uptime_ms: uptime,
                uptime_formatted: this.formatUptime(uptime)
            });

        } catch (error) {
            this.logger.error('Error during shutdown', error as Error);
        }
    }

    /**
     * 헬스체크
     */
    getHealth(): {
        status: 'healthy' | 'unhealthy';
        uptime_ms: number;
        services: Record<string, boolean>;
        stats: any;
    } {
        const services = {
            websocket: this.isRunning, // WebSocket 서버 상태는 앱 실행 상태와 동일
            redis: this.isRunning, // Redis 연결 상태도 앱 실행 상태와 동일  
            throttler: this.isRunning
        };

        const allHealthy = Object.values(services).every(Boolean);
        const uptime = this.startTime ? Date.now() - this.startTime.getTime() : 0;

        return {
            status: allHealthy ? 'healthy' : 'unhealthy',
            uptime_ms: uptime,
            services,
            stats: {
                throttler: { pending: 0, flushed: 0 }, // 기본 통계
                websocket_clients: 0 // 기본값
            }
        };
    }

    /**
     * WebSocket 서버 시작
     */
    private async startWebSocketServer(): Promise<void> {
        this.logger.info('Starting WebSocket server...');
        this.wsServer.start();
        this.logger.health('WebSocket', 'healthy', {
            port: this.config.websocket.port
        });
    }

    /**
     * Redis 연결 및 구독
     */
    private async startRedisConnection(): Promise<void> {
        this.logger.info('Connecting to Redis...');
        
        await this.redisBroker.connect();
        this.logger.health('Redis', 'healthy');

        await this.redisBroker.subscribe(
            this.config.redis.channel || this.config.redis.channels[0] || 'stock:realtime', 
            this.handleStockMessage.bind(this)
        );
        
        this.logger.info('Subscribed to Redis channel', {
            channel: this.config.redis.channel || this.config.redis.channels[0] || 'stock:realtime'
        });
    }

    /**
     * 배치 처리기 시작
     */
    private startBatchProcessor(): Promise<void> {
        this.logger.info('Starting batch processor...');
        
        this.flushTimer = setInterval(() => {
            this.flushBatch();
        }, this.config.throttler.flushIntervalMs);

        this.logger.health('Throttler', 'healthy', {
            interval_ms: this.config.throttler.flushIntervalMs
        });

        return Promise.resolve();
    }

    /**
     * Redis 메시지 처리
     */
    private handleStockMessage(message: RedisStockMessage): void {
        try {
            // 데이터 변환
            const clientData = this.dataTransformer.transformToClientData(message);
            
            // Throttler에 추가
            this.throttler.push(clientData.c, clientData);
            
            this.logger.stock('received', clientData.c, {
                price: clientData.p,
                volume_tick: clientData.vt
            });

        } catch (error) {
            this.logger.error('Failed to process stock message', error as Error, {
                stock_code: message.stock_code,
                message
            });
        }
    }

    /**
     * 배치 데이터 플러시 및 브로드캐스트
     */
    private flushBatch(): void {
        try {
            const batchData = this.throttler.flush();
            
            if (batchData.length > 0) {
                this.wsServer.broadcast('batch_stock_data', batchData);
                
                this.logger.info('Batch broadcasted', {
                    stock_count: batchData.length,
                    stocks: batchData.map(s => s.c).join(', ')
                });

                // 개별 주식 로깅 (DEBUG 레벨)
                batchData.forEach(stock => {
                    this.logger.stock('broadcast', stock.c, {
                        price: stock.p,
                        accumulated_volume: stock.vt
                    });
                });
            }

        } catch (error) {
            this.logger.error('Failed to flush batch', error as Error);
        }
    }

    /**
     * Graceful shutdown 설정
     */
    private setupGracefulShutdown(): void {
        const shutdownHandler = async (signal: string) => {
            this.logger.info(`Received ${signal}, shutting down gracefully...`);
            await this.stop();
            process.exit(0);
        };

        process.on('SIGINT', () => shutdownHandler('SIGINT'));
        process.on('SIGTERM', () => shutdownHandler('SIGTERM'));
    }

    /**
     * 업타임 포맷팅
     */
    private formatUptime(ms: number): string {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
        if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
        return `${seconds}s`;
    }
}
