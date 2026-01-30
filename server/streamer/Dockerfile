# Dockerfile - Streaming Service
FROM node:20-alpine AS base

# Install curl for health check
RUN apk add --no-cache curl

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./
RUN npm ci --only=production

# Build stage
FROM base AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 streamer

# Copy built application
COPY --from=builder --chown=streamer:nodejs /app/dist ./dist
COPY --from=deps --chown=streamer:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=streamer:nodejs /app/package.json ./package.json

USER streamer

EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8082/health || exit 1

CMD ["npm", "start"]
