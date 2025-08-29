# 🚀 FRM-AI: Financial Risk Management with AI

## 🌟 Tổng Quan

**FRM-AI** là một nền tảng mạng xã hội tài chính hoàn chỉnh, được tối ưu hóa cho thương mại hóa với các công nghệ miễn phí. Hệ thống bao gồm:

- 📊 **Phân tích tài chính AI-powered**
- 💬 **Chat system real-time như Twitter**
- 👥 **Social network features hoàn chỉnh**
- 💰 **FRM Coin wallet system**
- 📈 **Portfolio optimization**
- 📰 **AI news analysis**

## 🏗️ Kiến Trúc Hệ Thống

### Backend Architecture
- **FastAPI**: High-performance Python web framework
- **Supabase**: PostgreSQL database với real-time capabilities
- **WebSocket**: Real-time chat và notifications
- **Redis**: Caching và session management
- **JWT**: Secure authentication
- **Nginx**: Reverse proxy và load balancing

### Frontend Ready
- **Next.js Compatible**: API-first design
- **Real-time Integration**: WebSocket support
- **Responsive Design**: Mobile-first approach

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone repository
git clone <your-repo-url>
cd FRM-AI

# Copy environment template
cp .env.example .env

# Update .env with your configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
JWT_SECRET=your_jwt_secret
```

### 2. Database Setup

```sql
-- Run chat_schema.sql in your Supabase project
-- This creates tables for conversations, messages, participants
```

### 3. Docker Deployment (Recommended)

```bash
# Make deployment script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

### 4. Manual Installation

```bash
# Install dependencies
pip install -r requirements_fastapi.txt

# Start application
uvicorn app_fastapi:app --host 0.0.0.0 --port 8000 --reload
```

## 📡 API Endpoints

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user
- `POST /api/auth/logout` - User logout

### Social Features
- `GET /api/posts` - Get all posts
- `POST /api/posts` - Create new post
- `POST /api/posts/{id}/like` - Like/unlike post
- `POST /api/posts/{id}/comments` - Add comment
- `POST /api/users/{id}/follow` - Follow/unfollow user

### Chat System
- `GET /api/chat/conversations` - Get user conversations
- `POST /api/chat/conversations` - Create conversation
- `GET /api/chat/conversations/{id}/messages` - Get messages
- `WS /ws/chat` - Real-time chat WebSocket

### Financial Analysis
- `POST /api/analysis/stock` - Stock analysis
- `POST /api/analysis/technical` - Technical analysis
- `POST /api/analysis/news` - News sentiment analysis
- `POST /api/portfolio/optimize` - Portfolio optimization

### Wallet System
- `GET /api/wallet/balance` - Get FRM Coin balance
- `POST /api/wallet/transfer` - Transfer coins
- `GET /api/wallet/transactions` - Transaction history

## 🔧 Configuration

### Environment Variables

```bash
# Required
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_anon_key
JWT_SECRET=your_secret_key

# Optional
REDIS_URL=redis://localhost:6379/0
ALPHA_VANTAGE_API_KEY=your_key
NEWS_API_KEY=your_key
```

### Docker Configuration

The `docker-compose.yml` includes:
- **FastAPI Backend**: Main application
- **Redis**: Caching layer
- **Nginx**: Reverse proxy
- **Prometheus**: Monitoring
- **Grafana**: Dashboards

## 🌐 Frontend Integration

### Next.js Integration

```typescript
// API client configuration
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// WebSocket connection
const socket = new WebSocket(`ws://localhost:8000/ws/chat?token=${token}&user_id=${userId}`);

// API calls example
const response = await fetch(`${API_BASE}/api/posts`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
});
```

### Required Next.js Dependencies

```json
{
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.0.0",
    "socket.io-client": "^4.7.0",
    "axios": "^1.6.0",
    "@tanstack/react-query": "^5.0.0"
  }
}
```

## 💡 Key Features

### 1. Real-time Chat System
- Group và private conversations
- Typing indicators
- Message read receipts
- WebSocket-based real-time updates

### 2. Social Network Features
- User profiles với avatar upload
- Post creation với media support
- Like, comment, share functionality
- Follow/unfollow system
- Real-time notifications

### 3. Financial Analysis Tools
- Stock price analysis
- Technical indicators (RSI, MACD, Bollinger Bands)
- News sentiment analysis
- Portfolio optimization algorithms
- Risk assessment metrics

### 4. FRM Coin Wallet
- Digital wallet system
- Coin transfers between users
- Transaction history
- Service package purchases
- Loyalty rewards

## 📊 Monitoring & Analytics

### System Health
- `/api/system/health` - Basic health check
- `/api/system/metrics` - Performance metrics
- `/api/system/status` - Comprehensive status

### Monitoring Stack
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **Nginx**: Access logs
- **Application logs**: Structured logging

## 🔒 Security Features

### Authentication & Authorization
- JWT-based authentication
- Role-based access control
- Secure password hashing with bcrypt
- Session management với Redis

### API Security
- Rate limiting
- CORS configuration
- Security headers
- Input validation
- SQL injection protection

### Infrastructure Security
- Docker container isolation
- Nginx reverse proxy
- SSL/TLS encryption
- Security headers
- Database connection encryption

## 🚀 Production Deployment

### VPS Deployment

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Clone and deploy
git clone <your-repo>
cd FRM-AI
./deploy.sh
```

### Cloud Deployment Options

1. **Railway**: `railway deploy`
2. **DigitalOcean App Platform**: Connect GitHub repo
3. **AWS ECS**: Use provided Docker configurations
4. **Google Cloud Run**: Deploy containerized application

## 📈 Performance Optimization

### Caching Strategy
- Redis for session data
- API response caching
- Static file caching
- Database query optimization

### Database Optimization
- Proper indexing
- Connection pooling
- Query optimization
- Real-time subscriptions

### WebSocket Optimization
- Connection management
- Message queuing
- Graceful disconnection handling
- Scalable architecture

## 🛠️ Development

### Local Development

```bash
# Install development dependencies
pip install -r requirements_fastapi.txt

# Run with hot reload
uvicorn app_fastapi:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Code formatting
black .
```

### Project Structure

```
FRM-AI/
├── app_fastapi.py          # Main FastAPI application
├── chat_manager.py         # Chat system management
├── auth_manager.py         # Authentication logic
├── wallet_manager.py       # Wallet operations
├── social_manager.py       # Social features
├── stock_analysis.py       # Financial analysis
├── docker-compose.yml      # Docker services
├── nginx.conf              # Nginx configuration
├── requirements_fastapi.txt # Python dependencies
└── templates/              # HTML templates (legacy)
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation
- API Documentation: `/docs` (when running)
- Technical Guide: `COMMERCIAL_OPTIMIZATION_GUIDE.md`

### Community
- GitHub Issues for bug reports
- Discussions for feature requests
- Email support for commercial inquiries

## 🎯 Roadmap

### Phase 1 (Current)
- ✅ Core API development
- ✅ Chat system implementation
- ✅ Social features
- ✅ Wallet system

### Phase 2 (Next)
- 📱 Mobile app development
- 🤖 Advanced AI features
- 📊 Advanced analytics
- 🌍 Multi-language support

### Phase 3 (Future)
- 🏢 Enterprise features
- 🔌 Third-party integrations
- 📈 Advanced trading tools
- 🌐 Global expansion

---

**Made with ❤️ by FRM-AI Team**

*Empowering financial decisions with AI and social connectivity*
