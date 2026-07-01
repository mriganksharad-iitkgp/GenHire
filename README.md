Backend README (python-backend/README.md) 


Markdown


# Product Prototyping Lab - Python Backend

This is the backend for the Product Prototyping Lab application, a comprehensive platform for managing job postings, candidate applications, and AI-powered interviews. It is built with Python using the Flask framework and utilizes MongoDB for data storage.

## Features

* **User Authentication:** Secure user registration and login for both candidates and recruiters, with JWT-based authentication to protect routes.
* **Job Management:** Recruiters can create, read, update, and delete job postings. Candidates can view and search for available jobs.
* **Application Tracking:** Candidates can apply for jobs, and recruiters can view and manage the applications for their job postings.
* **Profile Management:** Users can create and update their profiles. Candidates can upload CVs and profile photos, while recruiters can manage their company profiles.
* **File Uploads:** A robust file upload system for handling CVs, profile pictures, and other necessary documents, with secure file serving.
* **CV Scoring:** An automated system to score candidate CVs against job descriptions, helping recruiters to identify the most suitable candidates quickly.
* **AI-Powered Interviews:** The platform can conduct automated, interactive interviews with candidates using AI, providing a consistent and unbiased initial screening process.

## Technology Stack

* **Framework:** Flask
* **Database:** MongoDB
* **Authentication:** JWT (JSON Web Tokens)
* **Real-time Communication:** Flask-SocketIO
* **AI & Machine Learning:**
    * **LLMs:** OpenAI, Google Generative AI, Groq
    * **Embeddings & Search:** Sentence-Transformers
    * **Computer Vision:** OpenCV, DeepFace, MediaPipe
* **File Handling:** LlamaParse
* **Deployment:** Gunicorn

For a complete list of dependencies, see the `requirements.txt` file.

## Getting Started

### Prerequisites

* Python 3.12+
* MongoDB instance (local or cloud-hosted)
* `pip` for package installation

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/adityapandey100/product-prototyping-lab.git](https://github.com/adityapandey100/product-prototyping-lab.git)
    cd product-prototyping-lab/python-backend
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**

    Create a `.env` file in the `python-backend` directory by copying the example file:

    ```bash
    cp .env.example .env
    ```

    Now, open the `.env` file and update it with your specific configuration details:

    ```env
    # OPENAI API Configuration
    OPENAI_API_KEY=your-openai-api-key-here

    # LANGCHAIN Configuration
    LANGCHAIN_API_KEY=your-langchain-api-key-here
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_ENDPOINT=[https://api.smith.langchain.com](https://api.smith.langchain.com)

    # MongoDB Configuration
    MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority&appName=YourApp
    DATABASE_NAME=your_database_name

    # JWT Configuration
    JWT_SECRET_KEY=your-secure-secret-key-here-change-this
    JWT_EXPIRATION_DAYS=1

    # Flask Configuration
    FLASK_ENV=development
    FLASK_SECRET_KEY=your-flask-secret-key-change-this
    FLASK_DEBUG=False

    # Server Configuration
    HOST=127.0.0.1
    PORT=5000

    # API Keys
    GROQ_API_KEY=your-groq-api-key-here
    GOOGLE_API_KEY=your-google-gemini-api-key-here
    parser_api_key=your-llama-parse-api-key-here

    # Upload Configuration
    UPLOAD_FOLDER=uploads
    MAX_CONTENT_LENGTH=16777216
    ALLOWED_EXTENSIONS=pdf,jpg,jpeg,png,gif

    # File Paths
    JD_FOLDER=uploads/jd
    CV_FOLDER=uploads/cv
    PROCTORING_FOLDER=uploads/proctoring
    PHOTOS_FOLDER=uploads/photos

    # CORS Configuration
    CORS_ORIGINS=[http://127.0.0.1:3000](http://127.0.0.1:3000),http://localhost:3000
    ```

### Running the Application

To start the backend server, run the following command in the `python-backend` directory:

```bash
flask run


The API will be available at http://127.0.0.1:5000.

API Endpoints

All endpoints are prefixed with /api.

Authentication

POST /register: Register a new user (candidate or recruiter).
POST /login: Log in a user and receive a JWT token.
GET /me: Get the current authenticated user's information (requires token).

Jobs

GET /jobs: Get all jobs.
POST /jobs: Create a new job posting (recruiter only, requires token).
GET /jobs/<job_id>: Get details for a specific job.
PUT /jobs/<job_id>: Update an existing job posting (recruiter only, requires token).
DELETE /jobs/<job_id>: Delete a job posting (recruiter only, requires token).
GET /jobs/<job_id>/applications: Get all applications for a specific job (recruiter only, requires token).

Applications

POST /jobs/<job_id>/apply: Apply for a job (candidate only, requires token).
DELETE /jobs/<job_id>/withdraw: Withdraw an application for a job (candidate only, requires token).
GET /applications: Get all applications for the current user (candidate or recruiter, requires token).
PUT /applications/<application_id>/status: Update the status of an application (recruiter only, requires token).
GET /applications/<application_id>/cv: Get the CV for a specific application (recruiter only, requires token).
GET /applications/<application_id>: Get a single application by its ID.
GET /applications/<application_id>/interview-report: Get the interview report for an application.
POST /applications/<application_id>/recalculate-score: Recalculate the CV score for an application.

Profile

GET /profile: Get the profile of the current authenticated user.
PUT /profile: Update the profile of the current authenticated user.
PUT /company-profile: Update the company profile (recruiter only).
GET /cv-details: Get the CV details for the current user.
PUT /cv-details: Update the CV details for the current user.

Files

POST /upload: Upload a job description and a CV file.
POST /upload-cv: Upload a CV for the current user (requires token).
POST /upload-photo: Upload a profile photo for the current user (requires token).
GET /view-file: View a file from the server by providing its path.
GET /download-cv: Download the current user's CV (requires token).
GET /view-cv: View the current user's CV in the browser (requires token).
GET /view-photo: View the current user's profile photo (requires token).

Project Structure




python-backend/
├── config/             # Configuration files (e.g., database connection)
├── controllers/        # Business logic for handling requests
├── cv_jd_processing/   # Scripts for processing and matching CVs and JDs
├── evaluation_model/   # AI models for evaluating interviews
├── interview/          # Logic for the AI-powered interview process
├── middleware/         # Custom middleware (e.g., authentication)
├── models/             # Data models (e.g., User, Job, Application)
├── routes/             # API route definitions
├── services/           # Services used by controllers (e.g., CV scoring)
├── uploads/            # Directory for storing uploaded files
├── utils/              # Utility functions and helpers
├── app.py              # Main application file
├── requirements.txt    # Project dependencies
└── .env.example        # Example environment variables





### Frontend README (`react-frontend/README.md`)

```markdown
# Product Prototyping Lab - React Frontend

This is the frontend for the Product Prototyping Lab application, a modern, user-friendly interface for managing job applications and AI-powered interviews. It is built with React and communicates with the Python backend.

## Features

* **User-Friendly Interface:** A clean and intuitive design for a seamless user experience.
* **User Authentication:** Secure registration and login for both candidates and recruiters.
* **Job Listings:** Candidates can browse, search, and view details for available jobs.
* **Application Submission:** A simple process for candidates to apply for jobs and upload their CVs.
* **Candidate Dashboard:** Candidates can track the status of their job applications.
* **Recruiter Dashboard:** Recruiters can manage their job postings, view candidate applications, and access AI-generated CV scores and interview reports.
* **AI-Powered Interviews:** An interactive video interview interface where candidates can interact with an AI interviewer.
* **Responsive Design:** The application is designed to work on various screen sizes, from desktops to mobile devices.

## Technology Stack

* **Core Library:** React
* **Routing:** React Router
* **HTTP Client:** Axios
* **Real-time Communication:** Socket.IO Client
* **Charting:** Chart.js
* **Styling:** CSS Modules, standard CSS

For a complete list of dependencies, see the `package.json` file.

## Getting Started

### Prerequisites

* Node.js (v14 or later)
* `npm` or `yarn`

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/adityapandey100/product-prototyping-lab.git](https://github.com/adityapandey100/product-prototyping-lab.git)
    cd product-prototyping-lab/react-frontend
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```
    or
    ```bash
    yarn install
    ```

3.  **Set up environment variables:**

    Create a `.env` file in the `react-frontend` directory by copying the example file:

    ```bash
    cp .env.example .env
    ```

    Now, open the `.env` file and configure it as needed. The default values are set up to work with the backend running on `http://127.0.0.1:5000`.

    ```env
    # API Configuration
    REACT_APP_API_BASE=[http://127.0.0.1:5000/api](http://127.0.0.1:5000/api)
    REACT_APP_API_URL=[http://127.0.0.1:5000](http://127.0.0.1:5000)
    REACT_APP_WEBSOCKET_URL=[http://127.0.0.1:5000](http://127.0.0.1:5000)

    # Application Configuration
    REACT_APP_COMPANY_NAME=YourCompanyName
    REACT_APP_TOKEN_KEY=your-company-token
    REACT_APP_USER_KEY=your-company-user

    # Development Configuration
    REACT_APP_ENV=development
    REACT_APP_DEBUG=true

    # File Upload Configuration
    REACT_APP_MAX_FILE_SIZE=16777216
    REACT_APP_ALLOWED_FILE_TYPES=pdf,jpg,jpeg,png,gif
    ```

## Available Scripts

In the `react-frontend` directory, you can run the following scripts:

### `npm start` or `npm run dev`

Runs the app in development mode. Open [http://localhost:3000](http://localhost:3000) to view it in your browser. The page will reload when you make changes.

### `npm test`

Launches the test runner in interactive watch mode.

### `npm run build`

Builds the app for production to the `build` folder. It correctly bundles React in production mode and optimizes the build for the best performance.

### `npm run eject`

**Note: This is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can eject at any time. This command will remove the single build dependency from your project.

## Project Structure



react-frontend/
├── public/ # Public assets and the main HTML file
├── src/
│ ├── assets/ # Images, fonts, and other static assets
│ ├── components/ # Reusable React components
│ ├── hooks/ # Custom React hooks
│ ├── pages/ # Page components for different routes
│ ├── services/ # API communication and other services
│ ├── App.jsx # Main application component
│ ├── index.js # Entry point of the application
│ └── ...
├── .env.example # Example environment variables
├── package.json # Project dependencies and scripts
└── ...
Sources
1. https://github.com/Deepak-032/Upchaar



