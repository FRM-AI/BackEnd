#!/bin/bash

# FRM-AI Production Deployment Script
# Kịch bản triển khai sản phẩm thương mại hóa với các công nghệ miễn phí

set -e

echo "🚀 Starting FRM-AI Production Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${YELLOW}📁 Creating necessary directories...${NC}"
mkdir -p logs ssl grafana/provisioning

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating template...${NC}"
    cat > .env << EOF
# Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here

# JWT Configuration
JWT_SECRET=your_super_secret_jwt_key_here

# Application Configuration
ENVIRONMENT=production
DEBUG=false

# Database Configuration (if using local PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/frm_ai

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Email Configuration (for notifications)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# External API Keys
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
NEWS_API_KEY=your_news_api_key
EOF
    echo -e "${RED}❌ Please update the .env file with your actual configuration values.${NC}"
    exit 1
fi

# Build and start services
echo -e "${YELLOW}🔨 Building Docker images...${NC}"
docker-compose build

echo -e "${YELLOW}🚀 Starting services...${NC}"
docker-compose up -d

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 30

# Health check
echo -e "${YELLOW}🔍 Performing health checks...${NC}"

# Check backend health
if curl -f http://localhost:8000/api/system/health &> /dev/null; then
    echo -e "${GREEN}✅ Backend is healthy${NC}"
else
    echo -e "${RED}❌ Backend health check failed${NC}"
    docker-compose logs frm-ai-backend
fi

# Check Redis
if docker exec frm-ai-redis redis-cli ping | grep -q PONG; then
    echo -e "${GREEN}✅ Redis is healthy${NC}"
else
    echo -e "${RED}❌ Redis health check failed${NC}"
fi

# Check Prometheus
if curl -f http://localhost:9090/-/healthy &> /dev/null; then
    echo -e "${GREEN}✅ Prometheus is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Prometheus health check failed (this is optional)${NC}"
fi

# Display service status
echo -e "${GREEN}🎉 Deployment completed!${NC}"
echo ""
echo "📊 Service URLs:"
echo "• API Backend: http://localhost:8000"
echo "• API Documentation: http://localhost:8000/docs"
echo "• Prometheus Metrics: http://localhost:9090"
echo "• Grafana Dashboard: http://localhost:3001 (admin/admin123)"
echo ""
echo "📋 Service Status:"
docker-compose ps

# Show logs
echo ""
echo -e "${YELLOW}📝 Recent logs:${NC}"
docker-compose logs --tail=20 frm-ai-backend

echo ""
echo -e "${GREEN}✅ FRM-AI is ready for production!${NC}"
echo -e "${YELLOW}💡 Don't forget to:${NC}"
echo "• Update your domain in nginx.conf"
echo "• Set up SSL certificates in ssl/ directory"
echo "• Configure your Next.js frontend to use this backend"
echo "• Set up monitoring alerts"
echo "• Configure backup strategies"
