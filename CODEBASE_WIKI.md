# HR Tech Product Prototyping Lab - Codebase Wiki

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Technology Stack](#technology-stack)
4. [Directory Structure](#directory-structure)
5. [Frontend (React)](#frontend-react)
6. [Backend (Python Flask)](#backend-python-flask)
7. [Database Schema](#database-schema)
8. [API Endpoints](#api-endpoints)
9. [Key Features](#key-features)
10. [AI/ML Components](#aiml-components)
11. [Authentication & Security](#authentication--security)
12. [Development Setup](#development-setup)
13. [File Upload System](#file-upload-system)
14. [Real-time Features](#real-time-features)
15. [Interview System](#interview-system)
16. [Troubleshooting](#troubleshooting)

---

## 🎯 Project Overview

The HR Tech Product Prototyping Lab is a comprehensive job application and interview management platform that combines traditional HR workflows with advanced AI capabilities. The system serves two primary user types:

- **Candidates**: Create profiles, apply for jobs, take AI-powered interviews
- **Recruiters**: Post jobs, manage applications, conduct interviews, view AI-generated reports

### Core Value Proposition

- **AI-Powered Interviews**: Automated question generation based on CV and job descriptions
- **CV-JD Matching**: Semantic similarity scoring between candidate CVs and job descriptions
- **Proctoring Integration**: Real-time interview monitoring and security
- **Comprehensive Analytics**: Detailed candidate evaluation and reporting

---

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend│    │  Python Backend │    │   MongoDB Atlas │
│   (Port 3000)   │◄──►│   (Port 5000)   │◄──►│    Database     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Static Assets │    │  File Storage   │    │  AI/ML Services │
│   (Build/Public)│    │  (Upload Dirs)  │    │  (Groq, BERT)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Communication Patterns

- **HTTP/REST API**: Primary communication between frontend and backend
- **WebSocket (Socket.IO)**: Real-time features for interviews and notifications
- **File Streaming**: Secure file uploads and downloads with token authentication

---

## 🛠️ Technology Stack

### Frontend Stack

- **React 19.0.0**: Modern React with latest features
- **React Router DOM 7.1.5**: Client-side routing
- **CSS Modules**: Scoped styling with dynamic themes
- **Axios**: HTTP client for API calls
- **Socket.IO Client**: Real-time communication
- **FFmpeg**: Video/audio processing capabilities

### Backend Stack

- **Flask 3.1.1**: Lightweight Python web framework
- **Flask-SocketIO**: WebSocket support
- **Flask-CORS**: Cross-origin resource sharing
- **PyMongo**: MongoDB integration
- **PyJWT**: JSON Web Token authentication

### AI/ML Stack

- **LlamaIndex**: Document indexing and retrieval
- **Groq**: Large language model API
- **Transformers**: BERT models for embeddings
- **Sentence Transformers**: Semantic similarity
- **OpenCV**: Computer vision for proctoring
- **NLTK**: Natural language processing
- **Scikit-learn**: Machine learning utilities

### Database & Storage

- **MongoDB Atlas**: Cloud NoSQL database
- **Local File System**: Structured file storage for uploads

---

## 📁 Directory Structure

```
product-prototyping-lab/
├── react-frontend/                 # Frontend application
│   ├── public/                    # Static assets
│   │   ├── index.html            # Main HTML template
│   │   ├── favicon.ico           # Application icon
│   │   └── sampleChatData.json   # Mock data for development
│   ├── src/                      # Source code
│   │   ├── components/           # Reusable UI components
│   │   │   ├── candidate/        # Candidate-specific components
│   │   │   ├── recruiter/        # Recruiter-specific components
│   │   │   ├── JobEditModal.jsx  # Job editing interface
│   │   │   ├── JobCreationModal.jsx # Job creation interface
│   │   │   ├── CVViewer.jsx      # CV viewing component
│   │   │   ├── Navbar.jsx        # Navigation component
│   │   │   └── Layout.jsx        # Layout wrapper
│   │   ├── pages/                # Page components
│   │   │   ├── Dashboard.jsx     # Candidate dashboard
│   │   │   ├── RecruiterDashboard.jsx # Recruiter dashboard
│   │   │   ├── Profile.jsx       # User profile management
│   │   │   ├── Login.jsx         # Authentication page
│   │   │   ├── Register.jsx      # User registration
│   │   │   ├── JobDetails.jsx    # Job detail view
│   │   │   ├── ApplicationView.jsx # Application timeline
│   │   │   └── Chat.jsx          # Interview chat interface
│   │   ├── hooks/                # Custom React hooks
│   │   │   ├── useAuth.js        # Authentication logic
│   │   │   ├── useJobs.js        # Job management
│   │   │   └── useApplications.js # Application management
│   │   ├── services/             # API services
│   │   │   └── api.js            # Centralized API calls
│   │   ├── App.jsx               # Main application component
│   │   └── index.js              # Application entry point
│   ├── package.json              # Dependencies and scripts
│   └── README.md                 # Frontend documentation
├── python-backend/                # Backend application
│   ├── uploads/                  # File storage
│   │   ├── cv/                   # Candidate CVs
│   │   ├── jd/                   # Job descriptions
│   │   └── proctoring/           # Interview recordings
│   ├── sentence_index/           # AI model indices
│   ├── app.py                    # Main Flask application
│   ├── interview_system.py       # AI interview engine
│   ├── qa.py                     # Question-answer processing
│   ├── security_check.py         # Proctoring and security
│   ├── migrate_max_status.py     # Database migrations
│   ├── requirements.txt          # Python dependencies
│   └── Eric Ries - The Lean Startup.pdf # Reference document
└── .git/                         # Git version control
```

---

## ⚛️ Frontend (React)

### Key Components Architecture

#### Authentication Flow

- **Login.jsx** / **Register.jsx**: Handle user authentication with role-based access
- **useAuth.js**: Manages authentication state and token storage
- **Token Storage**: Local storage with "companyxyz-token" key

#### Dashboard Components

- **Dashboard.jsx**: Candidate interface for job browsing and applications
- **RecruiterDashboard.jsx**: Recruiter interface with tabs for jobs, candidates, analytics
- **Profile.jsx**: User profile management with photo/CV uploads

#### Job Management

- **JobCreationModal.jsx**: Rich job creation interface with AI suggestions
- **JobEditModal.jsx**: Job editing with status management
- **JobDetails.jsx**: Detailed job view with application functionality

#### Application Management

- **ApplicationView.jsx**: Timeline view of application status
- **ApplicationsList.jsx**: List view with status-based actions
- **CVViewer.jsx**: Secure CV viewing with download capabilities

### Styling Architecture

- **CSS Modules**: Scoped styling prevents conflicts
- **Dark Mode Support**: Theme variables for light/dark modes
- **Responsive Design**: Mobile-first approach with breakpoints
- **Animation**: CSS animations for enhanced UX

### State Management

- **Custom Hooks**: Centralized business logic
- **Local Storage**: Persistent authentication and preferences
- **API Integration**: Centralized in `services/api.js`

---

## 🐍 Backend (Python Flask)

### Core Application Structure

#### Main Application (`app.py`)

- **Flask Setup**: CORS, SocketIO configuration
- **Database**: MongoDB Atlas connection
- **Authentication**: JWT-based with role verification
- **File Handling**: Secure upload/download with validation

#### AI/ML Modules

##### Interview System (`interview_system.py`)

```python
class InterviewQuestionGenerator:
    - generate_initial_questions(): CV+JD based questions
    - query_with_sentence_window(): Context-aware follow-ups
    - get_random_non_contextual_question(): General questions
```

##### Document Processing (`qa.py`)

```python
class PDFProcessor:
    - extract_text_from_pdf(): Text extraction
    - compute_cosine_similarity(): CV-JD matching
    - query_with_sentence_window(): Semantic search
```

#### Security Features (`security_check.py`)

- **Proctoring**: Real-time face detection and behavior analysis
- **Anomaly Detection**: Unusual activity monitoring
- **Session Management**: Secure interview sessions

### Database Collections

#### Users Collection

```javascript
{
  _id: ObjectId,
  name: String,
  email: String,
  password: String (hashed),
  user_type: "candidate" | "recruiter",
  company_name: String, // recruiters only
  bio: String,
  skills: Array,
  cv_path: String,
  photo_path: String,
  created_at: DateTime,
  updated_at: DateTime
}
```

#### Jobs Collection

```javascript
{
  _id: ObjectId,
  title: String,
  company: String,
  location: String,
  type: String,
  experience: String,
  salary: String,
  description: String,
  skills: Array,
  status: "active" | "inactive",
  created_by: ObjectId,
  applicants: Number,
  pending: Number,
  interviewed: Number,
  selected: Number,
  rejected: Number,
  created_at: DateTime
}
```

#### Applications Collection

```javascript
{
  _id: ObjectId,
  student_id: ObjectId,
  job_id: ObjectId,
  status: "pending" | "shortlisted" | "interviewed" | "selected" | "rejected",
  cv_score: Number,
  interview_score: Number,
  applied_at: DateTime,
  updated_at: DateTime,
  student_profile: Object
}
```

#### Interviews Collection

```javascript
{
  _id: ObjectId,
  session_id: String,
  application_id: ObjectId,
  user_id: ObjectId,
  status: "active" | "completed" | "cancelled",
  questions: Array,
  responses: Array,
  proctoring_score: Number,
  final_score: Number,
  evaluation: Object,
  created_at: DateTime,
  updated_at: DateTime
}
```

---

## 🔌 API Endpoints

### Authentication Endpoints

```
POST /api/register          - User registration
POST /api/login             - User authentication
```

### Profile Management

```
GET  /api/profile           - Get user profile
PUT  /api/profile           - Update user profile
PUT  /api/company-profile   - Update company profile (recruiters)
POST /api/upload-cv         - Upload CV file
POST /api/upload-photo      - Upload profile photo
GET  /api/view-cv           - Download CV file
GET  /api/view-photo        - Download profile photo
```

### Job Management

```
GET    /api/jobs            - List all jobs
POST   /api/jobs            - Create new job (recruiters)
GET    /api/jobs/:id        - Get job details
PUT    /api/jobs/:id        - Update job (recruiters)
DELETE /api/jobs/:id        - Delete job (recruiters)
POST   /api/jobs/:id/apply  - Apply for job (candidates)
DELETE /api/jobs/:id/withdraw - Withdraw application
```

### Application Management

```
GET /api/applications                           - List applications
GET /api/applications/:id                       - Get application details
PUT /api/applications/:id/status                - Update application status
GET /api/applications/:id/interview-report      - Get interview report
GET /api/applications/:id/cv                    - Download application CV
```

### Interview System

```
POST /api/interviews/start                      - Start interview session
GET  /api/interviews/:session_id/questions      - Get interview questions
POST /api/interviews/:session_id/response       - Submit interview response
POST /api/interviews/:session_id/complete       - Complete interview
```

### Debug/Utility Endpoints

```
POST /api/seed-jobs                            - Seed sample jobs
GET  /api/test-jobs                           - Test job retrieval
POST /api/debug/create-test-interview         - Create test interview
GET  /api/debug/interviews                    - List all interviews
```

---

## 🌟 Key Features

### 1. Intelligent Job Matching

- **Semantic Analysis**: Uses BERT embeddings for CV-JD similarity
- **Skill Extraction**: NLP-based skill identification
- **Score Calculation**: Cosine similarity for matching scores

### 2. AI-Powered Interviews

- **Dynamic Questions**: Generated based on CV and JD analysis
- **Context Awareness**: Follow-up questions based on previous responses
- **Reference Integration**: Uses external documents for domain knowledge

### 3. Real-time Proctoring

- **Face Detection**: OpenCV-based candidate monitoring
- **Behavior Analysis**: Anomaly detection during interviews
- **Security Scoring**: Comprehensive proctoring score calculation

### 4. Comprehensive Analytics

- **Application Tracking**: Complete application lifecycle
- **Performance Metrics**: CV scores, interview scores, proctoring scores
- **Recruiter Dashboard**: Overview of hiring pipeline

### 5. File Management System

- **Secure Uploads**: Token-based file access
- **Format Validation**: PDF support for CVs and JDs
- **Storage Organization**: Structured directory layout

---

## 🤖 AI/ML Components

### Text Processing Pipeline

1. **PDF Extraction**: PyPDF-based text extraction
2. **Preprocessing**: NLTK tokenization, stopword removal, POS tagging
3. **Embedding Generation**: BERT-based embeddings
4. **Similarity Calculation**: Cosine similarity for matching

### Question Generation System

1. **Document Analysis**: CV and JD content analysis
2. **Context Extraction**: Relevant experience and skill identification
3. **Question Templates**: Structured question generation
4. **Dynamic Follow-ups**: Context-aware conversation flow

### Interview Evaluation

1. **Response Analysis**: Natural language understanding
2. **Scoring Algorithm**: Multi-factor evaluation
3. **Report Generation**: Comprehensive candidate assessment

### Model Configuration

```python
# BERT Model for Embeddings
model_name = "bert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(model_name)

# Sentence Transformer for Similarity
sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")

# Groq LLM for Question Generation
llm = Groq(model="mixtral-8x7b-32768", api_key=groq_api_key)
```

---

## 🔐 Authentication & Security

### JWT Implementation

- **Token Generation**: 24-hour expiration
- **Header Format**: `Authorization: Bearer <token>`
- **Route Protection**: `@token_required` decorator

### File Security

- **Access Control**: Token-based file access
- **Path Validation**: Secure filename handling
- **Upload Restrictions**: File type and size limits

### Proctoring Security

- **Real-time Monitoring**: Face detection and tracking
- **Anomaly Detection**: Unusual behavior identification
- **Session Management**: Secure interview sessions

---

## 🚀 Development Setup

### Prerequisites

- **Node.js**: v14+ for React frontend
- **Python**: v3.8+ for Flask backend
- **MongoDB**: Atlas account or local instance

### Frontend Setup

```bash
cd react-frontend
npm install
npm start  # Runs on http://localhost:3000
```

### Backend Setup

```bash
cd python-backend
pip install -r requirements.txt
python app.py  # Runs on http://localhost:5000
```

### Environment Variables

```bash
# Backend (.env)
MONGO_URI=mongodb+srv://...
GROQ_API_KEY=gsk_...
SECRET_KEY=your-secret-key

# Frontend (.env)
REACT_APP_API_BASE=http://localhost:5000/api
```

### Database Initialization

```bash
# Create sample jobs
curl -X POST http://localhost:5000/api/seed-jobs

# Test connection
curl -X GET http://localhost:5000/api/test-jobs
```

---

## 📁 File Upload System

### Upload Structure

```
uploads/
├── cv/           # Candidate CVs (PDF)
├── jd/           # Job descriptions (PDF)
└── proctoring/   # Interview recordings
```

### Security Features

- **File Validation**: PDF format enforcement
- **Secure Filenames**: `secure_filename()` sanitization
- **Access Control**: Token-based download protection
- **Size Limits**: Configurable upload size restrictions

### API Integration

```javascript
// Upload CV
const formData = new FormData();
formData.append("cv", file);
await api.uploadCV(formData);

// Download CV (with token)
const blob = await api.viewCV();
const url = URL.createObjectURL(blob);
```

---

## 🔄 Real-time Features

### Socket.IO Implementation

- **Connection Management**: User session tracking
- **Event Broadcasting**: Real-time updates
- **Interview Sessions**: Live communication during interviews

### Event Types

```javascript
// Client Events
socket.emit("join_interview", { session_id });
socket.emit("interview_response", { response });

// Server Events
socket.on("question_generated", { question });
socket.on("interview_completed", { report });
```

---

## 🎯 Interview System

### Interview Flow

1. **Session Initialization**: Create interview session
2. **Question Generation**: AI-based questions from CV/JD
3. **Real-time Interaction**: Socket.IO communication
4. **Response Evaluation**: AI-powered assessment
5. **Report Generation**: Comprehensive evaluation

### Question Types

- **Experience-based**: Derived from CV content
- **Role-specific**: Based on job requirements
- **Behavioral**: Standard behavioral questions
- **Follow-up**: Dynamic based on responses

### Evaluation Metrics

- **Technical Competency**: Role-specific skills assessment
- **Communication**: Response clarity and structure
- **Experience Relevance**: Past experience alignment
- **Cultural Fit**: Behavioral assessment

---

## 🔧 Troubleshooting

### Common Issues

#### Frontend Issues

```bash
# Module not found errors
npm install
npm audit fix

# CORS issues
# Check backend CORS configuration
# Verify API_BASE environment variable
```

#### Backend Issues

```bash
# MongoDB connection errors
# Check MONGO_URI in environment
# Verify Atlas network access

# Import errors
pip install -r requirements.txt
# Check Python version compatibility
```

#### File Upload Issues

```bash
# Permission errors
chmod 755 uploads/
mkdir -p uploads/{cv,jd,proctoring}

# Large file uploads
# Check Flask configuration for file size limits
```

### Development Tips

- **Hot Reload**: Both frontend and backend support hot reload
- **Debug Mode**: Enable Flask debug mode for development
- **Browser DevTools**: Use React DevTools for component debugging
- **API Testing**: Use Postman/curl for API endpoint testing

### Performance Optimization

- **Database Indexing**: Add indexes for frequent queries
- **File Caching**: Implement caching for frequently accessed files
- **API Pagination**: Implement pagination for large datasets
- **Image Optimization**: Compress images for better performance

---

## 📊 Monitoring & Analytics

### Application Metrics

- **User Activity**: Login patterns, session duration
- **Job Performance**: Application rates, success rates
- **Interview Analytics**: Completion rates, scores distribution
- **System Performance**: API response times, error rates

### Business Intelligence

- **Recruitment Funnel**: Application to hire conversion
- **Candidate Quality**: Score distributions and trends
- **Recruiter Efficiency**: Time to hire metrics
- **Platform Usage**: Feature adoption and engagement

---

## 🛣️ Future Roadmap

### Planned Features

- **Video Interviews**: WebRTC integration for live video
- **Advanced Analytics**: Machine learning insights
- **API Integration**: Third-party HR systems integration
- **Mobile App**: React Native mobile application
- **Multilingual Support**: Internationalization (i18n)

### Technical Improvements

- **Microservices**: Service decomposition for scalability
- **Container Deployment**: Docker and Kubernetes setup
- **CI/CD Pipeline**: Automated testing and deployment
- **API Documentation**: OpenAPI/Swagger integration
- **Performance Monitoring**: Application performance management

---

_This wiki serves as a comprehensive guide to understanding, developing, and maintaining the HR Tech Product Prototyping Lab codebase. For specific implementation details, refer to the individual source files and their inline documentation._
