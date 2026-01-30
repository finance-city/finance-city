#!/bin/bash
# scripts/build.sh - 전체 서비스 빌드 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 환경 확인
check_requirements() {
    log_info "Checking requirements..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    log_success "Requirements check passed"
}

# 개발 환경 빌드
build_dev() {
    log_info "Building development environment..."
    
    # .env 파일 확인
    if [ ! -f .env ]; then
        log_warn ".env file not found, copying from .env.example"
        cp .env.example .env
    fi
    
    # 개발용 빌드
    docker-compose build --no-cache
    log_success "Development build completed"
}

# 프로덕션 환경 빌드
build_prod() {
    log_info "Building production environment..."
    
    # 버전 확인
    VERSION=${1:-$(git rev-parse --short HEAD)}
    log_info "Building with version: $VERSION"
    
    # 프로덕션용 빌드
    VERSION=$VERSION docker-compose -f docker-compose.prod.yml build --no-cache
    log_success "Production build completed with version: $VERSION"
}

# ECR에 푸시 (AWS 배포용)
push_to_ecr() {
    local ECR_REGISTRY=$1
    local VERSION=$2
    
    if [ -z "$ECR_REGISTRY" ]; then
        log_error "ECR Registry URL is required"
        exit 1
    fi
    
    log_info "Pushing images to ECR: $ECR_REGISTRY"
    
    # AWS CLI 로그인
    aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin $ECR_REGISTRY
    
    # 태그 및 푸시
    docker tag finance-collector:latest $ECR_REGISTRY/finance-collector:$VERSION
    docker tag finance-streamer:latest $ECR_REGISTRY/finance-streamer:$VERSION
    
    docker push $ECR_REGISTRY/finance-collector:$VERSION
    docker push $ECR_REGISTRY/finance-streamer:$VERSION
    
    log_success "Images pushed to ECR"
}

# 메인 실행 로직
main() {
    case $1 in
        "dev")
            check_requirements
            build_dev
            ;;
        "prod")
            check_requirements
            build_prod $2
            ;;
        "push")
            push_to_ecr $2 $3
            ;;
        *)
            echo "Usage: $0 {dev|prod|push} [version] [ecr_registry]"
            echo ""
            echo "Examples:"
            echo "  $0 dev                     # Build for development"
            echo "  $0 prod v1.0.0            # Build for production with version"
            echo "  $0 push ECR_URL v1.0.0     # Push to ECR with version"
            exit 1
            ;;
    esac
}

# 스크립트가 직접 실행될 때만 main 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
