# HR Tech Product Prototyping Lab - Project Overview

## 🎯 Project Summary

This is a comprehensive HR technology platform that combines modern web technologies with AI-powered interview systems. The platform serves both **candidates** and **recruiters**, providing job search capabilities, application management, and advanced AI-driven interview assessments with proctoring features.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                         │
│  ┌─────────────────┬─────────────────┬─────────────────────┐ │
│  │   Candidate      │    Recruiter    │    Interview       │ │
│  │   Dashboard      │   Dashboard     │    System          │ │
│  └─────────────────┴─────────────────┴─────────────────────┘ │
└─────────────────────────────┬───────────────────────────────┘
                              │ HTTP/WebSocket
┌─────────────────────────────┴───────────────────────────────┐
│                Backend (Flask + SocketIO)                   │
│  ┌─────────────────┬─────────────────┬─────────────────────┐ │
│  │   REST APIs     │   Real-time     │   AI Interview      │ │
│  │   (CRUD Ops)    │   Proctoring    │   Engine            │ │
│  └─────────────────┴─────────────────┴─────────────────────┘ │
└─────────────────────────────┬───────────────────────────────┘
                              │ Database Queries
┌─────────────────────────────┴───────────────────────────────┐
│                    MongoDB Database                         │
│       (Users, Jobs, Applications, Interviews)               │
└─────────────────────────────────────────────────────────────┘
```

## 🛠️ Technology Stack

### Frontend (`react-frontend/`)

- **Framework**: React 19.0.0 with React Router DOM 7.1.5
- **Styling**: CSS Modules for component-specific styles
- **API Communication**: Axios for HTTP requests
- **Real-time Features**: Socket.IO Client for live proctoring
- **Media Processing**: FFmpeg for video/audio processing
- **Build Tool**: React Scripts (Create React App)

### Backend (`python-backend/`)

- **Framework**: Flask 3.1.1 with Flask-SocketIO 5.5.1
- **Database**: MongoDB with PyMongo 4.13.2
- **Authentication**: JWT tokens with PyJWT 2.10.1
- **AI/ML Stack**:
  - **LLMs**: Groq API with Llama 3.3-70B model
  - **Embeddings**: Sentence Transformers, BERT
  - **Document Processing**: PyPDF for CV/JD analysis
  - **Computer Vision**: OpenCV, MediaPipe, DeepFace for proctoring
  - **RAG System**: LlamaIndex for contextual question generation
- **File Handling**: Werkzeug for secure file uploads
- **Environment**: Python-dotenv for configuration

## 📁 Project Structure

### Frontend Structure

```
react-frontend/
├── public/                     # Static assets
├── src/
│   ├── components/             # Reusable UI components
│   │   ├── candidate/          # Candidate-specific components
│   │   ├── recruiter/          # Recruiter-specific components
│   │   ├── Layout.jsx          # Main layout wrapper
│   │   ├── Navbar.jsx          # Navigation component
│   │   └── Toast.jsx           # Notification system
│   ├── hooks/                  # Custom React hooks
│   │   ├── candidate/          # Candidate data hooks
│   │   ├── useAuth.js          # Authentication hook
│   │   ├── useJobs.js          # Jobs management hook
│   │   └── useApplications.js  # Applications hook
│   ├── pages/                  # Route components
│   │   ├── Dashboard.jsx       # Candidate job search
│   │   ├── RecruiterDashboard.jsx  # Recruiter management
│   │   ├── Interview.jsx       # AI interview interface
│   │   ├── Profile.jsx         # User profile management
│   │   └── Login.jsx           # Authentication
│   ├── services/
│   │   └── api.js              # Centralized API layer
│   └── App.jsx                 # Main application router
├── package.json                # Dependencies and scripts
└── build/                      # Production build output
```

### Backend Structure

```
python-backend/
├── config/
│   └── database.py             # MongoDB connection setup
├── controllers/                # Business logic layer
│   ├── auth_controller.py      # Authentication logic
│   ├── job_controller.py       # Job management
│   ├── application_controller.py # Application processing
│   ├── profile_controller.py   # User profile management
│   └── file_controller.py      # File upload/download
├── middleware/                 # Request processing middleware
│   ├── auth_middleware.py      # JWT validation
│   └── cors_middleware.py      # Cross-origin setup
├── models/                     # Data models
│   ├── user.py                 # User schema
│   ├── job.py                  # Job posting schema
│   └── application.py          # Application schema
├── routes/                     # API endpoints
│   ├── auth_routes.py          # /api/auth/* endpoints
│   ├── job_routes.py           # /api/jobs/* endpoints
│   ├── application_routes.py   # /api/applications/* endpoints
│   ├── profile_routes.py       # /api/profile/* endpoints
│   └── file_routes.py          # /api/upload*, /api/view* endpoints
├── utils/                      # Helper functions
│   ├── helpers.py              # General utilities
│   └── validators.py           # Input validation
├── app.py                      # Main Flask application
├── interview_system.py         # AI interview engine
└── requirements.txt            # Python dependencies
```

## 🔄 User Workflows

### Candidate Journey

1. **Registration/Login** → Create account or authenticate
2. **Profile Setup** → Upload CV, add personal details, skills
3. **Job Discovery** → Browse/filter available positions
4. **Application** → Apply to jobs with one-click
5. **Interview** → Take AI-powered interviews with proctoring
6. **Status Tracking** → Monitor application progress

### Recruiter Journey

1. **Registration/Login** → Create recruiter account
2. **Company Profile** → Set up company information
3. **Job Posting** → Create and manage job listings
4. **Candidate Review** → Browse applications, view CVs
5. **Interview Management** → Schedule and review AI interviews
6. **Decision Making** → Update application statuses

## 🤖 AI Interview System

### Core Features

- **CV-JD Matching**: Cosine similarity analysis between candidate CV and job description
- **Dynamic Question Generation**: Context-aware questions using LlamaIndex RAG system
- **Real-time Proctoring**: Computer vision-based monitoring using OpenCV and MediaPipe
- **Answer Evaluation**: Semantic similarity scoring with sentence transformers
- **Adaptive Questioning**: Follow-up questions based on previous answers

### Technical Components

- **LLM Engine**: Groq API with Llama 3.3-70B for natural language processing
- **Document Processing**: PyPDF extraction and BERT embeddings
- **Proctoring Engine**: Face detection, movement tracking, attention monitoring
- **Evaluation System**: Multi-metric assessment (relevance, depth, completeness)

## 🗄️ Database Schema

### Collections Structure

```javascript
// users
{
  _id: ObjectId,
  name: String,
  email: String,
  user_type: "candidate" | "recruiter",
  profile_photo: String,
  cv_path: String,
  cv_details: Object,
  company_name: String, // for recruiters
  created_at: Date,
  updated_at: Date
}

// jobs
{
  _id: ObjectId,
  title: String,
  description: String,
  company: String,
  location: String,
  type: "Full-time" | "Part-time" | "Contract",
  salary: String,
  skills: [String],
  experience: String,
  recruiter_id: ObjectId,
  created_at: Date
}

// applications
{
  _id: ObjectId,
  candidate_id: ObjectId,
  job_id: ObjectId,
  status: "pending" | "reviewed" | "interviewed" | "hired" | "rejected",
  cover_letter: String,
  interview_score: Number,
  applied_at: Date,
  updated_at: Date
}

// interviews
{
  _id: ObjectId,
  user_id: ObjectId,
  session_id: String,
  application_id: ObjectId,
  status: "active" | "completed",
  cv_path: String,
  jd_path: String,
  proctoring_score: Number,
  evaluation: Object,
  created_at: Date
}
```

## 🚀 Getting Started

### Prerequisites

- Node.js 16+ and npm
- Python 3.12+
- MongoDB instance
- Groq API key for AI features

### Environment Setup

#### Backend Environment Variables

```bash
# .env file in python-backend/
MONGODB_URI=mongodb://localhost:27017/
DATABASE_NAME=hrtech
FLASK_SECRET_KEY=your-secret-key
GROQ_API_KEY=your-groq-api-key
UPLOAD_FOLDER=uploads
```

#### Frontend Environment Variables

```bash
# .env file in react-frontend/
REACT_APP_API_URL=process.env.REACT_APP_API_URL
REACT_APP_TOKEN_KEY=companyxyz-token
```

### Installation & Running

#### Backend Setup

```bash
cd python-backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
python app.py
```

#### Frontend Setup

```bash
cd react-frontend
npm install
npm run dev
```

### Access Points

- **Frontend**: http://localhost:3000
- **Backend API**: process.env.REACT_APP_API_URL/api
- **Socket.IO**: ws://localhost:5000

## 🔐 Authentication & Security

### Authentication Flow

1. User credentials validated against MongoDB
2. JWT token generated with user ID and type
3. Token stored in localStorage on frontend
4. Backend middleware validates token on protected routes
5. Token includes user permissions (candidate/recruiter)

### Security Features

- JWT-based stateless authentication
- CORS middleware for cross-origin protection
- File upload validation and secure filename handling
- Input sanitization and validation
- Environment-based configuration management

## 🧪 Testing & Development

### API Testing

The backend provides comprehensive REST endpoints:

- `POST /api/auth/login` - Authentication
- `GET /api/jobs` - Job listings
- `POST /api/jobs/{id}/apply` - Job application
- `POST /api/interviews/start` - Begin AI interview
- `GET /api/profile` - User profile data

### Development Tools

- **Backend**: Flask debug mode with hot reload
- **Frontend**: React Scripts with hot module replacement
- **Database**: MongoDB Compass for data inspection
- **API Testing**: Use Postman or curl for endpoint testing

## 🎨 UI/UX Features

### Design System

- **CSS Modules**: Component-scoped styling
- **Responsive Design**: Mobile-first approach
- **Theme Support**: Dark mode compatible
- **Component Library**: Reusable UI components

### User Experience

- **Real-time Updates**: Socket.IO for live features
- **Toast Notifications**: User feedback system
- **Loading States**: Smooth loading experiences
- **Error Handling**: Graceful error recovery

## 📈 Performance Considerations

### Frontend Optimizations

- Code splitting with React Router
- Lazy loading for large components
- Optimized bundle size with Create React App
- Efficient state management with hooks

### Backend Optimizations

- Database indexing on frequently queried fields
- File streaming for large uploads/downloads
- Connection pooling for MongoDB
- Async operations with Flask-SocketIO

## 🔮 Future Enhancements

### Planned Features

- **Advanced Analytics**: Interview performance metrics
- **Video Interviews**: Live video calling integration
- **Mobile App**: React Native implementation
- **Multi-language Support**: Internationalization
- **Advanced AI**: GPT-4 integration, voice analysis
- **Recruitment Pipeline**: Advanced workflow management

### Technical Improvements

- **Testing Suite**: Unit and integration tests
- **CI/CD Pipeline**: Automated deployment
- **Monitoring**: Application performance monitoring
- **Scalability**: Microservices architecture
- **Security**: Enhanced authentication (OAuth, 2FA)

## 🤝 Contributing

### Development Guidelines

1. **Code Style**: Follow PEP 8 for Python, ESLint for JavaScript
2. **Commit Messages**: Use conventional commit format
3. **Branch Strategy**: Feature branches from main
4. **Documentation**: Update relevant docs with changes
5. **Testing**: Add tests for new features

### Project Structure Conventions

- Keep components small and focused
- Use TypeScript for new React components
- Follow RESTful API design principles
- Maintain separation of concerns in backend layers

---

## 📞 Support

For questions or contributions, please refer to the project's repository issues or contact the development team. This overview should provide you with a solid foundation to understand and contribute to the HR Tech platform.
