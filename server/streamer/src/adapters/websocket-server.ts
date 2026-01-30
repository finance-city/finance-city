// adapters/websocket-server.ts

import {WebSocket, WebSocketServer as WSS} from 'ws';
import type {IWebSocketServer} from '../core/interfaces.js';
import type {WebSocketMessage} from '../types/index.js';
import { IncomingMessage } from 'node:http';

export class WebSocketServer implements IWebSocketServer {
    private wss: WSS | null = null;
    private port: number;

    constructor() {
        this.port = Number(process.env.WS_PORT) || 8081;
    }

    start(): void {
        // 서버 시작
        this.wss = new WSS({port: this.port});
        this.wss.on('connection', (ws: WebSocket, req: IncomingMessage) => {
            this.handleConnection(ws, req);
        });
        console.log(`WebSocket server started on ws://localhost:${this.port}`);
    }

    private handleConnection(ws: WebSocket, req: IncomingMessage): void {
        const ip = req.socket.remoteAddress;
        console.log(`📱 Client connected: ${ip}`);

        // 현재 접속자 수 로깅
        this.logClientCount();

        // TODO: snapshot 전송 

        // 연결 해제 처리
        ws.on('close', () => {
            console.log(`📱 Client disconnected: ${ip}`);
            this.logClientCount();
        });

        // 에러 처리
        ws.on('error', (err) => {
            console.error(`❌ WebSocket error from ${ip}:`, err);
        });
    }

    /**
     * 모든 접속한 클라이언트에게 메시지 전송
     * @param event 이벤트 이름('stock_data', 'market_status', 'error' 등)
     * @param payload 보낼 데이터
     * @returns 
     */
    broadcast(event: string, payload: any): void {
        if (!this.wss) return;

        const message: WebSocketMessage = {
            type: event as 'stock_data' | 'market_status' | 'error',
            payload,
            timestamp: Date.now(),
        };

        const messageStr = JSON.stringify(message);

        // 접속한 모든 클라이언트를 순회하며 전송
        this.wss.clients.forEach((client) => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(messageStr);
            }
        });
    }

    stop(): void {
        if (this.wss) {
            this.wss.close(() => {
                console.log('WebSocket server stopped');
            });
            this.wss = null;
        }
    }

    // 현재 접속한 클라이언트 수 로깅
    private logClientCount() {
        if (this.wss) {
            console.log(`Current connected clients: ${this.wss.clients.size}`);
        }
    }


}