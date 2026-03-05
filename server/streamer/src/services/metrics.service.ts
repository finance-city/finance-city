// services/metrics.service.ts - Prometheus 메트릭 관리

import { 
    Registry, 
    Counter, 
    Gauge, 
    Histogram, 
    collectDefaultMetrics 
} from 'prom-client';

/**
 * Prometheus 메트릭 서비스
 * 
 * Streamer의 모든 비즈니스 메트릭을 중앙 관리
 */
export class MetricsService {
    private static instance: MetricsService;
    private readonly registry: Registry;

    // ==========================================
    // 비즈니스 메트릭 정의
    // ==========================================

    /** 현재 연결된 WebSocket 클라이언트 수 */
    public readonly connectedClients: Gauge<string>;

    /** 클라이언트에게 전송된 총 메시지 수 (Counter) */
    public readonly broadcastMessagesTotal: Counter<string>;

    /** Node.js Event Loop 지연 시간 (ms) */
    public readonly eventLoopLag: Histogram<string>;

    /** 데이터 처리 지연 시간 (Collector → Streamer) */
    public readonly internalLatency: Histogram<string>;

    /** 스냅샷 생성/조회 소요 시간 (향후 구현) */
    public readonly snapshotDuration: Histogram<string>;

    /** Redis에서 수신한 메시지 수 */
    public readonly redisMessagesReceived: Counter<string>;

    /** Throttler에 누적된 메시지 수 */
    public readonly throttlerPendingMessages: Gauge<string>;

    private constructor() {
        this.registry = new Registry();

        // ==========================================
        // 기본 메트릭 수집 (Node.js 기본 메트릭)
        // ==========================================
        collectDefaultMetrics({ 
            register: this.registry,
            prefix: 'nodejs_',
            gcDurationBuckets: [0.001, 0.01, 0.1, 1, 2, 5],
        });

        // ==========================================
        // 비즈니스 메트릭 초기화
        // ==========================================

        // 연결된 클라이언트 수
        this.connectedClients = new Gauge({
            name: 'fc_streamer_connected_clients',
            help: 'Number of currently connected WebSocket clients',
            registers: [this.registry],
        });

        // 브로드캐스트 메시지 수 (Rate 계산용)
        this.broadcastMessagesTotal = new Counter({
            name: 'fc_streamer_broadcast_messages_total',
            help: 'Total number of messages broadcast to clients',
            labelNames: ['type'], // 'stock', 'snapshot', 'error' 등
            registers: [this.registry],
        });

        // Event Loop Lag
        this.eventLoopLag = new Histogram({
            name: 'fc_streamer_eventloop_lag_seconds',
            help: 'Event loop lag in seconds',
            buckets: [0.001, 0.01, 0.05, 0.1, 0.5, 1, 2, 5], // 1ms ~ 5s
            registers: [this.registry],
        });

        // 내부 처리 지연 시간 (Collector timestamp → 현재)
        this.internalLatency = new Histogram({
            name: 'fc_streamer_internal_latency_seconds',
            help: 'Latency between collector timestamp and current time (seconds)',
            buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5], // 10ms ~ 5s
            registers: [this.registry],
        });

        // 스냅샷 소요 시간 (향후 구현)
        this.snapshotDuration = new Histogram({
            name: 'fc_streamer_snapshot_duration_seconds',
            help: 'Time taken to create or retrieve snapshots (seconds)',
            labelNames: ['operation'], // 'create', 'retrieve'
            buckets: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
            registers: [this.registry],
        });

        // Redis 메시지 수신
        this.redisMessagesReceived = new Counter({
            name: 'fc_streamer_redis_messages_received_total',
            help: 'Total number of messages received from Redis',
            labelNames: ['channel'],
            registers: [this.registry],
        });

        // Throttler 누적 메시지
        this.throttlerPendingMessages = new Gauge({
            name: 'fc_streamer_throttler_pending_messages',
            help: 'Number of messages pending in throttler',
            registers: [this.registry],
        });

        this.startEventLoopMonitoring();
    }

    /**
     * 싱글톤 인스턴스 가져오기
     */
    public static getInstance(): MetricsService {
        if (!MetricsService.instance) {
            MetricsService.instance = new MetricsService();
        }
        return MetricsService.instance;
    }

    /**
     * 메트릭 텍스트 가져오기 (Prometheus 스크랩용)
     */
    public async getMetrics(): Promise<string> {
        return this.registry.metrics();
    }

    /**
     * 레지스트리 가져오기
     */
    public getRegistry(): Registry {
        return this.registry;
    }

    /**
     * Event Loop Lag 모니터링 시작
     * 
     * 100ms마다 이벤트 루프 지연을 측정하여 기록
     */
    private startEventLoopMonitoring(): void {
        const interval = 100; // 100ms
        let lastTime = Date.now();

        setInterval(() => {
            const currentTime = Date.now();
            const lag = (currentTime - lastTime - interval) / 1000; // 초 단위
            
            if (lag > 0) {
                this.eventLoopLag.observe(lag);
            }
            
            lastTime = currentTime;
        }, interval);
    }

    /**
     * 내부 지연 시간 기록
     * 
     * @param collectorTimestamp - Collector에서 데이터를 수집한 시각 (ms)
     */
    public recordInternalLatency(collectorTimestamp: number): void {
        const now = Date.now();
        const latencyMs = now - collectorTimestamp;
        const latencySeconds = latencyMs / 1000;

        // 음수이거나 비정상적으로 큰 값은 무시
        if (latencySeconds >= 0 && latencySeconds < 60) {
            this.internalLatency.observe(latencySeconds);
        }
    }

    /**
     * Redis 메시지 수신 카운트
     */
    public incrementRedisMessages(channel: string): void {
        this.redisMessagesReceived.inc({ channel });
    }

    /**
     * 브로드캐스트 메시지 카운트
     */
    public incrementBroadcastMessages(type: string = 'stock'): void {
        this.broadcastMessagesTotal.inc({ type });
    }

    /**
     * 연결된 클라이언트 수 설정
     */
    public setConnectedClients(count: number): void {
        this.connectedClients.set(count);
    }

    /**
     * Throttler 대기 메시지 수 설정
     */
    public setThrottlerPending(count: number): void {
        this.throttlerPendingMessages.set(count);
    }

    /**
     * 스냅샷 처리 시간 기록 (향후 구현)
     */
    public recordSnapshotDuration(operation: 'create' | 'retrieve', durationSeconds: number): void {
        this.snapshotDuration.observe({ operation }, durationSeconds);
    }
}

// 싱글톤 인스턴스 export
export const metricsService = MetricsService.getInstance();
