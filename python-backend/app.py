import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS, cross_origin
# from qa import PDFProcessor
from werkzeug.utils import secure_filename
import uuid  # new import
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import jwt as pyjwt 
from functools import wraps
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import datetime
import threading
# from security_check import run_security_check
# Import interview system
# from interview_system import session_manager


# Add these imports with your other imports
import base64
# import cv2
import numpy as np
from flask_socketio import SocketIO
# from security_check import analyze_frame_for_proctoring # Use the new function


# Replace the old app initialization
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = 'your-secret-key-here'

mongo_uri='mongodb+srv://adityapandeygkp90:CgsSnvo0o1WoRMmQ@cluster0.yneajzv.mongodb.net/?retryWrites=true&w=majority&appName=hrtech'
client = MongoClient(mongo_uri)
career_portal = 'hrtech'  # Your database name
db = client[career_portal]  # Use the variable directly
users_collection = db['users']
interviews_collection = db['interviews']  # New collection for interviews
applications_collection = db['applications']  # New collection for job applications

document_pdf_path = "Eric Ries - The Lean Startup.pdf"  # Path to the document for querying
groq_api_key = "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"  # Replace with actual API key
# processor = PDFProcessor(document_pdf_path, groq_api_key)

# Add this dictionary after your interviews_collection setup
live_sessions = {}

# Define directories for storing files
UPLOAD_FOLDER = "uploads"
JD_FOLDER = os.path.join(UPLOAD_FOLDER, "jd")
CV_FOLDER = os.path.join(UPLOAD_FOLDER, "cv")
PROCTORING_FOLDER = os.path.join(UPLOAD_FOLDER, "proctoring")



# Ensure folders exist
os.makedirs(JD_FOLDER, exist_ok=True)
os.makedirs(CV_FOLDER, exist_ok=True)
os.makedirs(PROCTORING_FOLDER, exist_ok=True)

app.config["JD_FOLDER"] = JD_FOLDER
app.config["CV_FOLDER"] = CV_FOLDER
app.config["PROCTORING_FOLDER"] = PROCTORING_FOLDER
app.config["ALLOWED_EXTENSIONS"] = {"pdf"}

def generate_token(user_id):
    return pyjwt.encode({  # Use pyjwt instead of jwt
        'user_id': str(user_id),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }, app.config['SECRET_KEY'], algorithm='HS256')

# Replace your old token_required function with this one

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Support Authorization header or token passed via query parameter (for new-tab file views)
        token = request.headers.get('Authorization') or request.args.get('token')

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            # Check for the "Bearer " prefix and remove it if it exists.
            if isinstance(token, str) and token.startswith('Bearer '):
                token = token[7:]

            data = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = users_collection.find_one({'_id': ObjectId(data['user_id'])})

            if not current_user:
                return jsonify({'message': 'User not found!'}), 401

        except pyjwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)
    return decorated
# Auth routes
@app.route("/api/register", methods=["POST"])
@cross_origin()
def register():
    data = request.get_json()
    name = data.get('name')
    print(name)
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirmPassword')
    user_type = data.get('userType', 'candidate')  # Default to candidate

    # Validation
    if not all([name, email, password, confirm_password]):
        return jsonify({'error': 'All fields are required'}), 400
    
    if password != confirm_password:
        return jsonify({'error': 'Passwords do not match'}), 400
    
    if user_type not in ['candidate', 'recruiter']:
        return jsonify({'error': 'Invalid user type'}), 400
    
    # Check if user exists
    if users_collection.find_one({'email': email}):
        return jsonify({'error': 'Email already exists'}), 400
    
    # Create new user
    user_data = {
        'name': name,
        'email': email,
        'password': generate_password_hash(password),
        'user_type': user_type,
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow()
    }
    
    # Add default company information for recruiters
    if user_type == 'recruiter':
        user_data.update({
            'company_name': data.get('company_name', 'TechCorp Solutions'),
            'company_logo': data.get('company_logo', None),
            'company_description': data.get('company_description', 'A leading technology company focused on innovation.'),
            'company_website': data.get('company_website', None),
            'company_size': data.get('company_size', None),
            'company_industry': data.get('company_industry', 'Technology')
        })
    
    user_id = users_collection.insert_one(user_data).inserted_id
    
    # Generate token
    token = generate_token(user_id)
    
    return jsonify({
        'message': 'User registered successfully',
        'token': token,
        'user': {
            'id': str(user_id),
            'name': name,
            'email': email,
            'user_type': user_type
        }
    }), 201

@app.route("/api/login", methods=["POST"])
@cross_origin()
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user_type = data.get('userType', 'candidate')  # Default to candidate

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    if user_type not in ['candidate', 'recruiter']:
        return jsonify({'error': 'Invalid user type'}), 400
    
    user = users_collection.find_one({'email': email})
    
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Check if user type matches (if user_type is stored in database)
    stored_user_type = user.get('user_type', 'candidate')
    if stored_user_type != user_type:
        return jsonify({'error': f'Please login as {stored_user_type}'}), 401
    
    # Generate token
    token = generate_token(user['_id'])
    print("Logged in")
    return jsonify({
        'message': 'Logged in successfully',
        'token': token,
        'user': {
            'id': str(user['_id']),
            'name': user['name'],
            'email': user['email'],
            'user_type': stored_user_type
        }
    }), 200

@app.route("/api/me", methods=["GET"])
@cross_origin()
@token_required
def get_current_user(current_user):
    return jsonify({
        'id': str(current_user['_id']),
        'name': current_user['name'],
        'email': current_user['email'],
        'user_type': current_user.get('user_type', 'candidate')
    })


# Function to check allowed file types
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

# Route to handle file uploads
@app.route("/api/upload", methods=["POST"])
@cross_origin()
def upload_files():
    if "jd" not in request.files or "cv" not in request.files:
        return jsonify({"error": "Both JD and CV files are required"}), 400

    jd_file = request.files["jd"]
    cv_file = request.files["cv"]

    # Validate both files first; if either is invalid, return error without saving any file.
    if not jd_file or not allowed_file(jd_file.filename):
        return jsonify({"error": "Invalid JD file format"}), 400
    if not cv_file or not allowed_file(cv_file.filename):
        return jsonify({"error": "Invalid CV file format"}), 400

    # Generate random filenames while preserving original file extensions
    jd_ext = os.path.splitext(jd_file.filename)[1]
    jd_filename = secure_filename(str(uuid.uuid4()) + jd_ext)
    cv_ext = os.path.splitext(cv_file.filename)[1]
    cv_filename = secure_filename(str(uuid.uuid4()) + cv_ext)
    
    jd_path = os.path.join(app.config["JD_FOLDER"], jd_filename)
    cv_path = os.path.join(app.config["CV_FOLDER"], cv_filename)

    # Save both files now that they have passed validation.
    jd_file.save(jd_path)
    cv_file.save(cv_path)

    # similarity = float(processor.get_similarity(cv_path, jd_path))

    # interview_questions = processor.generate_initial_questions(cv_path, jd_path)
    
    return jsonify({
        "message": "Files uploaded successfully!",
        "jd_file_path": jd_path,
        "cv_file_path": cv_path,
        "similarity": 85.5,  # Mock similarity
        "interview_questions": ["Sample question 1", "Sample question 2", "Sample question 3"]
    }), 200

# New route to view a file from the server by given file path
@app.route("/api/view-file", methods=["GET"])
@cross_origin()
def view_file():
    file_path = request.args.get("path")
    if not file_path:
        return jsonify({"error": "Missing 'path' query parameter"}), 400

    base_dir = os.path.abspath(os.path.join(os.getcwd(), "uploads"))
    abs_file_path = os.path.abspath(file_path)
    if not abs_file_path.startswith(base_dir):
        return jsonify({"error": "Unauthorized file path"}), 403

    if not os.path.isfile(abs_file_path):
        return jsonify({"error": "File not found"}), 404

    return send_file(abs_file_path)

@app.route('/api/answer_question', methods=['POST'])
@cross_origin()
def answer_question():
    data = request.json
    question = data.get('question')
    history = data.get('history')
    jd_file_path = data.get('jd_file_path')
    cv_file_path = data.get('cv_file_path')

    if question is None:
        return jsonify({'error': 'Missing question parameter'}), 400
    if history is None:
        history = {}

    if jd_file_path is None or cv_file_path is None:
        return jsonify({'error': 'Missing JD or CV file path'}), 400

    # result = processor.query_document(question,history,jd_file_path,cv_file_path)
    # result = processor.query_document(question)

    return jsonify({'result': 'QA system temporarily disabled'})

# Interview System API Routes
@app.route('/api/interviews/start', methods=['POST'])
@cross_origin()
@token_required
def start_interview(current_user):
    data = request.json or {}
    
    # Get file paths (either from request or use defaults for testing)
    cv_path = data.get('cv_path', "uploads/cv/PeterConnollyResume-2.pdf")
    jd_path = data.get('jd_path', "uploads/jd/JD1.pdf")
    reference_path = data.get('reference_path', "Eric Ries - The Lean Startup.pdf")
    application_id = data.get('application_id')  # optional: link interview to application
    
    # Create a new interview session
    # session_data = session_manager.create_session(cv_path, jd_path, reference_path)
    
    session_data = {
        'session_id': str(uuid.uuid4()),
        'status': 'active',
        'current_question': 'Tell me about yourself'
    }
    
    # Store session info in the database
    interview_id = interviews_collection.insert_one({
        'user_id': str(current_user['_id']),
        'session_id': session_data['session_id'],
        'cv_path': cv_path,
        'jd_path': jd_path,
        'reference_path': reference_path,
        'application_id': application_id,
        'status': 'active',
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow()
    }).inserted_id
    
    return jsonify({
        'interview_id': str(interview_id),
        'session_id': session_data['session_id'],
        'initial_questions': ['Tell me about yourself', 'Why are you interested in this role?'],
    'similarity_score': 0.855
    })

@app.route('/api/interviews/<session_id>/question', methods=['GET'])
@cross_origin()
def get_interview_question(session_id):
    # Get session data
    # session_data = session_manager.get_session(session_id)
    
    # if not session_data:
    #     return jsonify({'error': 'Interview session not found'}), 404
    
    return jsonify({
        'current_questions': ['What are your strengths?', 'Describe a challenging project you worked on.']
    })

@app.route('/api/interviews/<session_id>/answer', methods=['POST'])
@cross_origin()
@token_required
def submit_answer(current_user, session_id):
    data = request.json
    question = data.get('question')
    answer = data.get('answer')
    
    if not question or not answer:
        return jsonify({'error': 'Question and answer are required'}), 400
    
    # Process the answer and get the next question
    # result = session_manager.submit_answer(session_id, question, answer)
    
    # if 'error' in result:
    #     return jsonify(result), 404
    
    result = {
        'status': 'answer_received',
        'next_question': 'Tell me about a time you overcame a challenge',
        'feedback': 'Good answer!'
    }
    
    return jsonify(result)

# Inside your end_interview function
@app.route('/api/interviews/<session_id>/end', methods=['POST'])
@token_required
def end_interview(current_user, session_id):
    # result = session_manager.end_session(session_id)
    # if 'error' in result:
    #     return jsonify(result), 404
    
    result = {
        'status': 'interview_ended',
        'final_score': 85.5,
        'summary': 'Interview completed successfully',
        # optional evaluation placeholder for compatibility
        'evaluation': {'summary': 'Evaluation not computed in this build.'}
    }
    
    # --- ADD THIS LINE ---
    final_score = live_sessions.get(session_id, {}).get('proctoring_score', 'N/A')
    
    # --- MODIFY THIS BLOCK ---
    # Update interview document with completion details
    interviews_collection.update_one(
        {'session_id': session_id, 'user_id': str(current_user['_id'])},
        {'$set': {
            'status': 'completed',
            'evaluation': result.get('evaluation'),
            'proctoring_score': final_score,  # Add the score here
            'updated_at': datetime.datetime.utcnow()
        }}
    )
    # Also update the related application with interview_score if linked
    session_doc = interviews_collection.find_one({'session_id': session_id, 'user_id': str(current_user['_id'])})
    if session_doc and session_doc.get('application_id'):
        try:
            applications_collection.update_one(
                {'_id': ObjectId(session_doc['application_id'])},
                {'$set': {
                    'interview_score': result.get('final_score'),
                    'status': 'interviewed',
                    'updated_at': datetime.datetime.utcnow()
                }}
            )
        except Exception:
            pass
    
    return jsonify(result)

@app.route('/api/interviews', methods=['GET'])
@cross_origin()
@token_required
def get_user_interviews(current_user):
    user_type = current_user.get('user_type', 'candidate')
    
    if user_type == 'recruiter':
        # Recruiters can see all interviews
        user_interviews = list(interviews_collection.find({}))
    else:
        # Candidates can only see their own interviews
        user_interviews = list(interviews_collection.find({'user_id': str(current_user['_id'])}))
    
    # Format the interviews for JSON response
    formatted_interviews = []
    for interview in user_interviews:
        formatted_interview = {
            'id': str(interview['_id']),
            'session_id': interview['session_id'],
            'status': interview['status'],
            'created_at': interview['created_at'].isoformat(),
            'updated_at': interview['updated_at'].isoformat(),
            'cv_path': interview.get('cv_path'),
            'jd_path': interview.get('jd_path')
        }
        
        # Include user info for recruiters
        if user_type == 'recruiter':
            user_info = users_collection.find_one({'_id': ObjectId(interview['user_id'])})
            if user_info:
                formatted_interview['candidate'] = {
                    'name': user_info['name'],
                    'email': user_info['email']
                }
        
        formatted_interviews.append(formatted_interview)
    
    return jsonify(formatted_interviews)



# Add this new route
@app.route('/api/interviews/<session_id>/register-face', methods=['POST'])
@token_required
def register_face(current_user, session_id):
    data = request.get_json()
    if 'image' not in data:
        return jsonify({'error': 'No image data provided'}), 400
    try:
        header, encoded = data['image'].split(",", 1)
        decoded_image = base64.b64decode(encoded)
        # frame = cv2.imdecode(np.frombuffer(decoded_image, np.uint8), cv2.IMREAD_COLOR)
        
        # Initialize the session in our live store
        live_sessions[session_id] = {
            'registered_face': 'face_data', 'proctoring_score': 100,
            'infractions': {}, 'sid': None
        }
        
        # Update the interview status in the database
        interviews_collection.update_one(
            {'session_id': session_id, 'user_id': str(current_user['_id'])},
            {'$set': {'status': 'active'}}
        )
        
        print(f"✅ Face registered for session: {session_id}. Interview is now active.")
        return jsonify({'message': 'Face registered successfully'}), 200
    except Exception as e:
        print(f"Error during face registration: {e}")
        return jsonify({'error': 'Failed to process image'}), 500
    
# Add this entire block for WebSocket event handling
@socketio.on('connect')
def handle_connect():
    print(f"🔌 Client connected with sid: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"🔌 Client disconnected with sid: {request.sid}")
    # Clean up session data to prevent memory leaks
    for session_id, data in list(live_sessions.items()):
        if data.get('sid') == request.sid:
            del live_sessions[session_id]
            print(f"🧹 Cleaned up live session data for {session_id}")
            break

@socketio.on('start_proctoring')
def handle_start_proctoring(data):
    session_id = data.get('session_id')
    if session_id and session_id in live_sessions:
        # Link the client's socket ID to the session
        live_sessions[session_id]['sid'] = request.sid
        print(f"▶️ Live proctoring stream started for session: {session_id}")
    else:
        print(f"⚠️ Attempted to start proctoring for invalid/unregistered session: {session_id}")

@socketio.on('proctoring_frame')
def handle_proctoring_frame(data):
    session_id = data.get('session_id')
    session_data = live_sessions.get(session_id)
    if not session_data or 'registered_face' not in session_data: return

    header, encoded = data['image'].split(",", 1)
    # frame = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), np.uint8), cv2.IMREAD_COLOR)

    # Call the analysis function from the other file
    # analysis_result = analyze_frame_for_proctoring(
    #     frame, session_data['registered_face'],
    #     session_data['proctoring_score'], session_data['infractions']
    # )
    
    # Mock analysis result
    analysis_result = {
        'score': session_data['proctoring_score'] - 1,
        'infractions': session_data['infractions'],
        'status': 'Status: OK'
    }
    
    # Update the session data in memory
    live_sessions[session_id]['proctoring_score'] = analysis_result['score']
    live_sessions[session_id]['infractions'] = analysis_result['infractions']

    if analysis_result['status'] != "Status: OK":
        print(f"🔴 Live Proctoring Alert [Session: {session_id}]: {analysis_result['status']} | Score: {analysis_result['score']:.1f}")


@app.route('/api/interviews/<session_id>/upload-recording', methods=['POST'])
@token_required
def upload_interview_recording(current_user, session_id):
    """
    Handles the upload of the final archival interview recording.
    This is called by the frontend after the interview is completed.
    """
    # 1. Check if the 'video' file is part of the request
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    video_file = request.files['video']

    # 2. Create a dedicated folder for this session's recordings if it doesn't exist
    session_folder = os.path.join(app.config["PROCTORING_FOLDER"], session_id)
    os.makedirs(session_folder, exist_ok=True)
    
    # 3. Create a secure filename and define the full path to save the video
    filename = secure_filename(f"recording_archive.mp4")
    video_path = os.path.join(session_folder, filename)
    
    # 4. Save the video file to the specified path
    video_file.save(video_path)
    
    # 5. Update the interview document in the database to include the path to this recording
    interviews_collection.update_one(
        {'session_id': session_id, 'user_id': str(current_user['_id'])},
        {'$push': {'recordings': {'path': video_path, 'timestamp': datetime.datetime.utcnow()}}}
    )
    
    print(f"✅ Final archival recording for session {session_id} saved to: {video_path}")
    
    # Note: The old background analysis thread is removed from here because
    # the proctoring analysis is now done live via WebSockets.
    
    return jsonify({'message': 'Archival recording saved successfully.'}), 200


# Profile Management Endpoints

@app.route('/api/profile', methods=['GET'])
@cross_origin()
@token_required
def get_profile(current_user):
    """Get user profile data"""
    profile_data = {
        'id': str(current_user['_id']),
        'name': current_user.get('name', ''),
        'email': current_user.get('email', ''),
        'phone': current_user.get('phone', ''),
        'location': current_user.get('location', ''),
        'title': current_user.get('title', ''),
        'about': current_user.get('about', ''),
        'skills': current_user.get('skills', []),
        'cv_path': current_user.get('cv_path', ''),
        'cv_details': current_user.get('cv_details', None),
        'profile_photo': current_user.get('profile_photo', ''),
        'user_type': current_user.get('user_type', 'candidate')
    }
    
    # Add company information for recruiters
    if current_user.get('user_type') == 'recruiter':
        profile_data.update({
            'company_name': current_user.get('company_name', 'TechCorp Solutions'),
            'company_logo': current_user.get('company_logo', ''),
            'company_description': current_user.get('company_description', ''),
            'company_website': current_user.get('company_website', ''),
            'company_size': current_user.get('company_size', ''),
            'company_industry': current_user.get('company_industry', 'Technology')
        })
    
    return jsonify(profile_data), 200

@app.route('/api/profile', methods=['PUT'])
@cross_origin()
@token_required
def update_profile(current_user):
    """Update user profile data"""
    data = request.get_json()
    
    # Update fields that are provided
    update_fields = {}
    for field in ['name', 'phone', 'location', 'title', 'about', 'skills']:
        if field in data:
            update_fields[field] = data[field]
    
    if update_fields:
        users_collection.update_one(
            {'_id': current_user['_id']},
            {'$set': update_fields}
        )
    
    return jsonify({'message': 'Profile updated successfully'}), 200

@app.route('/api/company-profile', methods=['PUT'])
@cross_origin()
@token_required
def update_company_profile(current_user):
    """Update company profile data for recruiters"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can update company profile.'}), 403
    
    data = request.get_json()
    
    # Update company fields that are provided
    update_fields = {}
    for field in ['company_name', 'company_logo', 'company_description', 'company_website', 'company_size', 'company_industry']:
        if field in data:
            update_fields[field] = data[field]
    
    if update_fields:
        users_collection.update_one(
            {'_id': current_user['_id']},
            {'$set': update_fields}
        )
    
    return jsonify({'message': 'Company profile updated successfully'}), 200

@app.route('/api/cv-details', methods=['GET'])
@cross_origin()
@token_required
def get_cv_details(current_user):
    """Get CV details for the current user"""
    cv_details = current_user.get('cv_details', None)
    return jsonify({'cv_details': cv_details}), 200

@app.route('/api/cv-details', methods=['PUT'])
@cross_origin()
@token_required
def update_cv_details(current_user):
    """Update CV details for the current user"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No CV details provided'}), 400
    
    # Update CV details
    users_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': {'cv_details': data}}
    )
    
    return jsonify({'message': 'CV details updated successfully'}), 200

@app.route('/api/upload-cv', methods=['POST'])
@cross_origin()
@token_required
def upload_cv(current_user):
    """Upload CV for a specific user"""
    if 'cv' not in request.files:
        return jsonify({'error': 'No CV file provided'}), 400
    
    cv_file = request.files['cv']
    if not cv_file or not allowed_file(cv_file.filename):
        return jsonify({'error': 'Invalid CV file format. Only PDF files are allowed.'}), 400
    
    # Generate unique filename
    cv_ext = os.path.splitext(cv_file.filename)[1]
    cv_filename = secure_filename(str(uuid.uuid4()) + cv_ext)
    cv_path = os.path.join(app.config["CV_FOLDER"], cv_filename)
    
    # Save file
    cv_file.save(cv_path)
    
    # Update user record with CV path
    users_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': {'cv_path': cv_path, 'cv_filename': cv_filename}}
    )
    
    return jsonify({
        'message': 'CV uploaded successfully',
        'cv_path': cv_path,
        'filename': cv_filename
    }), 200

@app.route('/api/upload-photo', methods=['POST'])
@cross_origin()
@token_required
def upload_photo(current_user):
    """Upload profile photo for a user"""
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo file provided'}), 400
    
    photo_file = request.files['photo']
    if not photo_file:
        return jsonify({'error': 'No photo file selected'}), 400
    
    # Check file extension
    allowed_photo_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    if not ('.' in photo_file.filename and 
            photo_file.filename.rsplit('.', 1)[1].lower() in allowed_photo_extensions):
        return jsonify({'error': 'Invalid photo format. Only PNG, JPG, JPEG, GIF allowed.'}), 400
    
    # Create photos directory if it doesn't exist
    photos_folder = os.path.join(UPLOAD_FOLDER, "photos")
    os.makedirs(photos_folder, exist_ok=True)
    
    # Generate unique filename
    photo_ext = os.path.splitext(photo_file.filename)[1]
    photo_filename = secure_filename(str(uuid.uuid4()) + photo_ext)
    photo_path = os.path.join(photos_folder, photo_filename)
    
    # Save file
    photo_file.save(photo_path)
    
    # Update user record with photo path
    users_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': {'profile_photo': photo_path, 'photo_filename': photo_filename}}
    )
    
    return jsonify({
        'message': 'Photo uploaded successfully',
        'photo_path': photo_path,
        'filename': photo_filename
    }), 200

@app.route('/api/download-cv', methods=['GET'])
@cross_origin()
@token_required
def download_cv(current_user):
    """Download user's CV"""
    cv_path = current_user.get('cv_path')
    if not cv_path or not os.path.exists(cv_path):
        return jsonify({'error': 'CV not found'}), 404
    
    return send_file(cv_path, as_attachment=True)

@app.route('/api/view-cv', methods=['GET'])
@cross_origin()
@token_required
def view_cv(current_user):
    """View user's CV in browser"""
    cv_path = current_user.get('cv_path')
    if not cv_path or not os.path.exists(cv_path):
        return jsonify({'error': 'CV not found'}), 404
    
    return send_file(cv_path)

@app.route('/api/view-photo', methods=['GET'])
@cross_origin()
@token_required
def view_photo(current_user):
    """View user's profile photo"""
    photo_path = current_user.get('profile_photo')
    if not photo_path or not os.path.exists(photo_path):
        return jsonify({'error': 'Photo not found'}), 404
    
    return send_file(photo_path)

# Job Management Endpoints for Recruiters

@app.route('/api/jobs', methods=['GET'])
@cross_origin()
@token_required
def get_jobs(current_user):
    """Get all jobs (for recruiters) or available jobs (for candidates)"""
    if current_user.get('user_type') == 'recruiter':
        # Return all jobs for recruiters
        jobs = list(db.jobs.find({'created_by': str(current_user['_id'])}))
        for job in jobs:
            job['_id'] = str(job['_id'])
        return jsonify(jobs), 200
    else:
        # For candidates: Show active jobs + jobs they have applied to (regardless of current status)
        user_id = str(current_user['_id'])
        
        # Get job IDs that the user has applied to
        user_applications = list(applications_collection.find({'student_id': user_id}))
        applied_job_ids = [app['job_id'] for app in user_applications]
        
        # Build query: active jobs OR jobs user has applied to
        query = {
            '$or': [
                {'status': 'active'},  # Always show active jobs
                {'_id': {'$in': [ObjectId(job_id) for job_id in applied_job_ids]}}  # Show jobs user applied to
            ]
        }
        
        jobs = list(db.jobs.find(query))
        for job in jobs:
            job['_id'] = str(job['_id'])
            # Remove sensitive recruiter info
            job.pop('created_by', None)
        return jsonify(jobs), 200

@app.route('/api/jobs', methods=['POST'])
@cross_origin()
@token_required
def create_job(current_user):
    """Create a new job posting (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can create jobs.'}), 403
    
    data = request.get_json()
    required_fields = ['title', 'department', 'location', 'type', 'experience', 'salary', 'description']
    
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Normalize/validate status with enhanced workflow - default to draft
    raw_status = (data.get('status') or 'draft').strip().lower()
    allowed_statuses = {'draft', 'active', 'paused', 'closed'}
    status = raw_status if raw_status in allowed_statuses else 'draft'

    # Helpers to normalize list-like fields possibly sent as strings
    def _to_list(val, sep=','):
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
        if isinstance(val, str):
            # Try both newline and comma separated values
            text = val.replace('\r', '').strip()
            parts = []
            for chunk in text.split('\n'):
                parts.extend([p.strip() for p in chunk.split(sep)])
            return [p for p in parts if p]
        return []

    # Get company information from recruiter's profile
    company_name = current_user.get('company_name') or data.get('company') or 'TechCorp Solutions'
    company_logo = current_user.get('company_logo') or data.get('logo') or None

    job_data = {
        'title': data['title'],
        'department': data['department'],
        'location': data['location'],
        'type': data['type'],
        'experience': data['experience'],
        'salary': data['salary'],
        'description': data['description'],
        'company': company_name,
        'logo': company_logo,
        'skills': _to_list(data.get('skills', [])),
        'responsibilities': _to_list(data.get('responsibilities', []), sep='\n'),
        'requirements': _to_list(data.get('requirements', []), sep='\n'),
        'benefits': _to_list(data.get('benefits', []), sep='\n'),
        'status': status,
        'created_by': str(current_user['_id']),
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow(),
        'deadline': data.get('deadline'),
        'applicants': 0,
        'interviewed': 0,
        'selected': 0,
        'rejected': 0,
        'pending': 0
    }
    
    result = db.jobs.insert_one(job_data)
    job_data['_id'] = str(result.inserted_id)
    
    return jsonify({'message': 'Job created successfully', 'job': job_data}), 201

@app.route('/api/jobs/<job_id>', methods=['PUT'])
@cross_origin()
@token_required
def update_job(current_user, job_id):
    """Update a job posting (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can update jobs.'}), 403
    
    # Validate job_id format
    if not job_id or job_id == 'undefined' or job_id == 'null':
        return jsonify({'error': 'Invalid job ID provided'}), 400
    
    try:
        job_object_id = ObjectId(job_id)
    except Exception as e:
        return jsonify({'error': f'Invalid job ID format: {job_id}'}), 400
    
    # Verify job belongs to current recruiter
    job = db.jobs.find_one({'_id': job_object_id, 'created_by': str(current_user['_id'])})
    if not job:
        return jsonify({'error': 'Job not found or unauthorized'}), 404
    
    data = request.get_json()
    update_fields = {}
    
    # Status progression validation
    def validate_status_progression(current_status, new_status):
        status_hierarchy = {'draft': 0, 'active': 1, 'paused': 2, 'closed': 3}
        current_level = status_hierarchy.get(current_status, 0)
        new_level = status_hierarchy.get(new_status, 0)
        return new_level >= current_level
    
    allowed_fields = ['title', 'department', 'location', 'type', 'experience', 'salary', 'description', 'skills', 'responsibilities', 'requirements', 'benefits', 'status', 'deadline']
    for field in allowed_fields:
        if field in data:
            if field == 'status':
                raw = str(data[field]).strip().lower()
                allowed_statuses = {'draft', 'active', 'paused', 'closed'}
                if raw in allowed_statuses:
                    current_status = job.get('status', 'draft')
                    if validate_status_progression(current_status, raw):
                        update_fields[field] = raw
                    else:
                        return jsonify({'error': f'Cannot change status from {current_status} to {raw}. Status can only progress forward.'}), 400
                else:
                    return jsonify({'error': f'Invalid status: {raw}. Allowed values: {list(allowed_statuses)}'}), 400
            elif field in {'skills'}:
                # Support comma-separated strings
                val = data.get(field, [])
                if isinstance(val, str):
                    update_fields[field] = [p.strip() for p in val.split(',') if p.strip()]
                elif isinstance(val, list):
                    update_fields[field] = [str(x).strip() for x in val if str(x).strip()]
            elif field in {'responsibilities','requirements','benefits'}:
                # Support newline/comma separated strings
                val = data.get(field, [])
                if isinstance(val, str):
                    lines = [p.strip() for part in val.replace('\r','').split('\n') for p in part.split(',') if p.strip()]
                    update_fields[field] = lines
                elif isinstance(val, list):
                    update_fields[field] = [str(x).strip() for x in val if str(x).strip()]
            else:
                update_fields[field] = data[field]
    
    if update_fields:
        update_fields['updated_at'] = datetime.datetime.utcnow()
        db.jobs.update_one({'_id': job_object_id}, {'$set': update_fields})
    
    return jsonify({'message': 'Job updated successfully'}), 200

@app.route('/api/jobs/<job_id>', methods=['DELETE'])
@cross_origin()
@token_required
def delete_job(current_user, job_id):
    """Delete a job posting (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can delete jobs.'}), 403
    
    # Verify job belongs to current recruiter
    result = db.jobs.delete_one({'_id': ObjectId(job_id), 'created_by': str(current_user['_id'])})
    if result.deleted_count == 0:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({'message': 'Job deleted successfully'}), 200

# ========== SEED DATA ENDPOINT ==========

@app.route('/api/seed-jobs', methods=['POST'])
@cross_origin()
def seed_jobs():
    """Seed some test jobs for testing"""
    sample_jobs = [
        {
            'title': 'Senior Business Development Manager',
            'department': 'Sales',
            'location': 'San Francisco, CA (Remote)',
            'type': 'Full-time',
            'experience': '5+ years',
            'salary': '$120,000 - $150,000',
            'description': 'We are looking for an experienced Business Development Manager with expertise in client acquisition to join our growing team.',
            'skills': ['Sales Strategy', 'Client Acquisition', 'Market Research', 'Negotiation'],
            'status': 'active',
            'created_by': 'system',
            'created_at': datetime.datetime.utcnow(),
            'applicants': 0,
            'interviewed': 0,
            'selected': 0,
            'rejected': 0,
            'pending': 0
        },
        {
            'title': 'Strategic Partnerships Manager',
            'department': 'Business Development',
            'location': 'New York, NY',
            'type': 'Full-time',
            'experience': '3+ years',
            'salary': '$110,000 - $140,000',
            'description': 'Join our business team to develop strategic partnerships and drive mutual growth with key stakeholders.',
            'skills': ['Partnership Development', 'Contract Negotiation', 'Relationship Management'],
            'status': 'active',
            'created_by': 'system',
            'created_at': datetime.datetime.utcnow(),
            'applicants': 0,
            'interviewed': 0,
            'selected': 0,
            'rejected': 0,
            'pending': 0
        },
        {
            'title': 'Market Research Analyst',
            'department': 'Marketing',
            'location': 'Boston, MA (Hybrid)',
            'type': 'Full-time',
            'experience': '2+ years',
            'salary': '$90,000 - $120,000',
            'description': 'Conduct comprehensive market research to identify opportunities and provide strategic insights for our business development team.',
            'skills': ['Market Analysis', 'Data Visualization', 'Industry Trends'],
            'status': 'active',
            'created_by': 'system',
            'created_at': datetime.datetime.utcnow(),
            'applicants': 0,
            'interviewed': 0,
            'selected': 0,
            'rejected': 0,
            'pending': 0
        }
    ]
    
    # Insert jobs into database
    for job_data in sample_jobs:
        existing_job = db.jobs.find_one({'title': job_data['title']})
        if not existing_job:
            db.jobs.insert_one(job_data)
    
    return jsonify({'message': f'Seeded {len(sample_jobs)} jobs successfully'}), 200

@app.route('/api/test-jobs', methods=['GET'])
@cross_origin()
def test_jobs():
    """Test endpoint to check jobs without authentication"""
    jobs = list(db.jobs.find())
    for job in jobs:
        job['_id'] = str(job['_id'])
    return jsonify({'jobs': jobs, 'count': len(jobs)}), 200

# ========== APPLICATION MANAGEMENT ENDPOINTS ==========

@app.route('/api/jobs/<job_id>/apply', methods=['POST'])
@cross_origin()
@token_required
def apply_for_job(current_user, job_id):
    """Apply for a job (candidates only)"""
    # Normalize user_type with backward compatibility (missing -> candidate)
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized. Only candidates can apply for jobs.'}), 403
    
    # Check if job exists
    job = db.jobs.find_one({'_id': ObjectId(job_id)})
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Check if already applied
    existing_application = applications_collection.find_one({
        'job_id': job_id,
        'student_id': str(current_user['_id'])
    })
    if existing_application:
        return jsonify({'error': 'You have already applied for this job'}), 400
    
    data = request.get_json() or {}
    
    application_data = {
        'job_id': job_id,
        'student_id': str(current_user['_id']),
        'student_name': current_user.get('name', ''),
        'student_email': current_user.get('email', ''),
        'cover_letter': data.get('cover_letter', ''),
        'status': 'pending',
    'applied_at': datetime.datetime.utcnow(),
    'updated_at': datetime.datetime.utcnow(),
        'job_title': job.get('title', ''),
        'recruiter_id': job.get('created_by', ''),
        # Optional scoring placeholders; populated by AI services when available
        'cv_score': 85.0,
        'interview_score': None,
        'student_profile': {
            'bio': current_user.get('bio', ''),
            'skills': current_user.get('skills', []),
            'experience': current_user.get('experience', ''),
            'education': current_user.get('education', ''),
            'phone': current_user.get('phone', ''),
            'location': current_user.get('location', '')
        }
    }
    
    # Insert application
    result = applications_collection.insert_one(application_data)
    
    # Update job applicant count
    db.jobs.update_one(
        {'_id': ObjectId(job_id)},
        {'$inc': {'applicants': 1, 'pending': 1}}
    )
    
    application_data['_id'] = str(result.inserted_id)
    
    return jsonify({
        'message': 'Application submitted successfully',
        'application': application_data
    }), 201

@app.route('/api/jobs/<job_id>/withdraw', methods=['DELETE'])
@cross_origin()
@token_required
def withdraw_application(current_user, job_id):
    """Withdraw application for a job (candidates only)"""
    # Normalize user_type with backward compatibility (missing -> candidate)
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized. Only candidates can withdraw applications.'}), 403
    
    # Check if application exists
    application = applications_collection.find_one({
        'job_id': job_id,
        'student_id': str(current_user['_id'])
    })
    if not application:
        return jsonify({'error': 'No application found for this job'}), 404
    
    # Check if application can be withdrawn (only pending or applied status)
    status = application.get('status', '').lower()
    if status not in ['pending', 'applied']:
        return jsonify({'error': 'Cannot withdraw application. Application is already being processed.'}), 400
    
    # Delete the application
    applications_collection.delete_one({
        'job_id': job_id,
        'student_id': str(current_user['_id'])
    })
    
    # Update job applicant count
    db.jobs.update_one(
        {'_id': ObjectId(job_id)},
        {'$inc': {'applicants': -1, 'pending': -1}}
    )
    
    return jsonify({'message': 'Application withdrawn successfully'}), 200

# Debug endpoint to check interviews data
# Debug endpoint to create test interview with proctoring score
@app.route('/api/debug/create-test-interview', methods=['POST'])
@cross_origin()
def create_test_interview():
    """Create a test interview with proctoring score"""
    # Get the first application to attach interview to
    application = applications_collection.find_one({})
    if not application:
        return jsonify({'error': 'No applications found'})
    
    # Create a test interview with proctoring score
    test_interview = {
        'session_id': 'test_session_123',
        'application_id': str(application['_id']),
        'user_id': application['student_id'],
        'status': 'completed',
        'proctoring_score': 85,
        'final_score': 88,
        'evaluation': {'summary': 'Test evaluation'},
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow(),
        'cv_path': 'test_cv.pdf',
        'jd_path': 'test_jd.pdf'
    }
    
    result = interviews_collection.insert_one(test_interview)
    
    # Also update the application with interview score
    applications_collection.update_one(
        {'_id': application['_id']},
        {'$set': {
            'interview_score': 88,
            'status': 'interviewed',
            'updated_at': datetime.datetime.utcnow()
        }}
    )
    
    return jsonify({
        'message': 'Test interview created',
        'interview_id': str(result.inserted_id),
        'application_id': str(application['_id']),
        'proctoring_score': 85
    })

@app.route('/api/debug/interviews', methods=['GET'])
@cross_origin()
def debug_interviews():
    """Debug endpoint to see what interviews exist"""
    interviews = list(interviews_collection.find({}))
    for interview in interviews:
        interview['_id'] = str(interview['_id'])
        if isinstance(interview.get('created_at'), datetime.datetime):
            interview['created_at'] = interview['created_at'].isoformat()
        if isinstance(interview.get('updated_at'), datetime.datetime):
            interview['updated_at'] = interview['updated_at'].isoformat()
    return jsonify({'interviews': interviews, 'count': len(interviews)})

# Debug endpoint to check applications
@app.route('/api/debug/applications', methods=['GET'])
@cross_origin()
def debug_applications():
    """Debug endpoint to see what applications exist"""
    applications = list(applications_collection.find({}))
    for app in applications:
        app['_id'] = str(app['_id'])
        if isinstance(app.get('applied_at'), datetime.datetime):
            app['applied_at'] = app['applied_at'].isoformat()
        if isinstance(app.get('updated_at'), datetime.datetime):
            app['updated_at'] = app['updated_at'].isoformat()
    return jsonify({'applications': applications, 'count': len(applications)})

@app.route('/api/applications', methods=['GET'])
@cross_origin()
@token_required
def get_applications(current_user):
    """Get applications - candidates see their own, recruiters see applications for their jobs"""
    # Normalize user_type with default for legacy users
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()

    if user_type in ['candidate', 'student']:
        # Students see their own applications
        applications = list(applications_collection.find({'student_id': str(current_user['_id'])}))
        
        # Convert ObjectId to string and fetch job details
        for app in applications:
            app['_id'] = str(app['_id'])
            # Normalize datetime serialization for frontend
            if isinstance(app.get('applied_at'), datetime.datetime):
                app['applied_at'] = app['applied_at'].isoformat()
            if isinstance(app.get('updated_at'), datetime.datetime):
                app['updated_at'] = app['updated_at'].isoformat()
            # Ensure scores exist for UI
            if app.get('cv_score') is None:
                app['cv_score'] = 85.0  # fallback placeholder for legacy data
            # expose interview_score if present (legacy docs may miss it)
            if 'interview_score' not in app:
                app['interview_score'] = None
            job = db.jobs.find_one({'_id': ObjectId(app['job_id'])})
            if job:
                app['job_details'] = {
                    'title': job.get('title'),
                    'company': job.get('company', 'TechCorp Solutions'),
                    'location': job.get('location'),
                    'type': job.get('type'),
                    'department': job.get('department'),
                    'logo': job.get('logo')
                }
            # Get proctoring score from most recent completed interview
            completed_interview = interviews_collection.find_one(
                {'application_id': app['_id'], 'status': 'completed'},
                sort=[('updated_at', -1)]
            )
            if completed_interview and completed_interview.get('proctoring_score'):
                proctoring_score = completed_interview.get('proctoring_score')
                # Handle both numeric and string values, exclude 'N/A'
                if isinstance(proctoring_score, (int, float)):
                    app['proctoring_score'] = proctoring_score
                elif isinstance(proctoring_score, str) and proctoring_score.replace('.', '', 1).isdigit():
                    app['proctoring_score'] = float(proctoring_score)
                else:
                    app['proctoring_score'] = None
            else:
                app['proctoring_score'] = None
            # Whether an interview report is available
            app['report_available'] = completed_interview is not None
        
        return jsonify(applications), 200
    elif user_type == 'recruiter':
        # Recruiters see applications for their jobs
        recruiter_jobs = list(db.jobs.find({'created_by': str(current_user['_id'])}, {'_id': 1}))
        job_ids = [str(job['_id']) for job in recruiter_jobs]
        
        applications = list(applications_collection.find({'job_id': {'$in': job_ids}}))
        
        # Convert ObjectId to string and add job details
        for app in applications:
            app['_id'] = str(app['_id'])
            # Normalize datetime serialization for frontend
            if isinstance(app.get('applied_at'), datetime.datetime):
                app['applied_at'] = app['applied_at'].isoformat()
            if isinstance(app.get('updated_at'), datetime.datetime):
                app['updated_at'] = app['updated_at'].isoformat()
            if app.get('cv_score') is None:
                app['cv_score'] = 85.0
            if 'interview_score' not in app:
                app['interview_score'] = None
            job = db.jobs.find_one({'_id': ObjectId(app['job_id'])})
            if job:
                app['job_details'] = {
                    'title': job.get('title'),
                    'department': job.get('department'),
                    'location': job.get('location'),
                    'logo': job.get('logo'),
                    'company': job.get('company', 'TechCorp Solutions')
                }
            # Provide base URL for CV retrieval; the frontend can append '?token=...'
            app['cv_url'] = f"/api/applications/{app['_id']}/cv"
            # Get proctoring score from most recent completed interview
            completed_interview = interviews_collection.find_one(
                {'application_id': app['_id'], 'status': 'completed'},
                sort=[('updated_at', -1)]
            )
            if completed_interview and completed_interview.get('proctoring_score'):
                proctoring_score = completed_interview.get('proctoring_score')
                # Handle both numeric and string values, exclude 'N/A'
                if isinstance(proctoring_score, (int, float)):
                    app['proctoring_score'] = proctoring_score
                elif isinstance(proctoring_score, str) and proctoring_score.replace('.', '', 1).isdigit():
                    app['proctoring_score'] = float(proctoring_score)
                else:
                    app['proctoring_score'] = None
            else:
                app['proctoring_score'] = None
            # Whether a report is available
            app['report_available'] = completed_interview is not None
        
        return jsonify(applications), 200
    
    else:
        return jsonify({'error': 'Unauthorized'}), 403

# ========= JOB DETAILS (SINGLE) ENDPOINT =========

@app.route('/api/jobs/<job_id>', methods=['GET'])
@cross_origin()
@token_required
def get_job_details(current_user, job_id):
    """Get details for a single job.
    - Recruiters: can view their own jobs; other jobs are visible but include all fields.
    - Candidates: can view jobs that are active/published or have no status.
    """
    try:
        job = db.jobs.find_one({'_id': ObjectId(job_id)})
    except Exception:
        return jsonify({'error': 'Invalid job id'}), 400

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()

    if user_type != 'recruiter':
        # For candidates, restrict to active jobs only
        status = (job.get('status') or '').strip().lower()
        if status not in ['active', ''] and job.get('status') is not None:
            return jsonify({'error': 'Job not available'}), 403
        # Hide recruiter-only fields
        job.pop('created_by', None)

    job['_id'] = str(job['_id'])

    return jsonify(job), 200

@app.route('/api/applications/<application_id>/status', methods=['PUT'])
@cross_origin()
@token_required
def update_application_status(current_user, application_id):
    """Update application status (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can update application status.'}), 403
    
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status not in ['pending', 'reviewed', 'shortlisted', 'interviewed', 'selected', 'rejected']:
        return jsonify({'error': 'Invalid status'}), 400
    
    # Find application
    application = applications_collection.find_one({'_id': ObjectId(application_id)})
    if not application:
        return jsonify({'error': 'Application not found'}), 404
    
    # Verify the job belongs to current recruiter
    job = db.jobs.find_one({'_id': ObjectId(application['job_id']), 'created_by': str(current_user['_id'])})
    if not job:
        return jsonify({'error': 'Unauthorized to update this application'}), 403
    
    old_status = application.get('status', 'pending')
    
    # Update application status
    applications_collection.update_one(
        {'_id': ObjectId(application_id)},
        {
            '$set': {
                'status': new_status,
                'updated_at': datetime.datetime.utcnow(),
                'updated_by': str(current_user['_id'])
            }
        }
    )
    
    # Update job statistics
    # Build proper increments for known job counters
    job_update = {}
    status_counters = ['pending', 'interviewed', 'selected', 'rejected']  # keep only fields that exist on jobs

    if old_status in status_counters:
        job_update[old_status] = -1
    if new_status in status_counters:
        job_update[new_status] = job_update.get(new_status, 0) + 1

    if job_update:
        db.jobs.update_one({'_id': ObjectId(application['job_id'])}, {'$inc': job_update})
    
    return jsonify({'message': 'Application status updated successfully'}), 200

@app.route('/api/applications/<application_id>/cv', methods=['GET'])
@cross_origin()
@token_required
def get_application_cv(current_user, application_id):
    """Stream the candidate's CV PDF for a given application (recruiters only).
    Authorization: Recruiter must own the job tied to the application.
    """
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can view candidate CVs.'}), 403

    # Find the application
    try:
        app_doc = applications_collection.find_one({'_id': ObjectId(application_id)})
    except Exception:
        return jsonify({'error': 'Invalid application id'}), 400

    if not app_doc:
        return jsonify({'error': 'Application not found'}), 404

    # Verify recruiter owns the job
    job = db.jobs.find_one({'_id': ObjectId(app_doc['job_id'])})
    if not job or job.get('created_by') != str(current_user['_id']):
        return jsonify({'error': 'Unauthorized to view this CV'}), 403

    # Look up candidate user for CV path
    try:
        student_user = users_collection.find_one({'_id': ObjectId(app_doc['student_id'])})
    except Exception:
        student_user = None

    if not student_user:
        return jsonify({'error': 'Candidate not found'}), 404

    cv_path = student_user.get('cv_path')
    if not cv_path or not os.path.exists(cv_path):
        return jsonify({'error': 'CV not found'}), 404

    # Stream the PDF
    return send_file(cv_path)

@app.route('/api/jobs/<job_id>/applications', methods=['GET'])
@cross_origin()
@token_required
def get_job_applications(current_user, job_id):
    """Get all applications for a specific job (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can view job applications.'}), 403
    
    # Verify job belongs to current recruiter
    job = db.jobs.find_one({'_id': ObjectId(job_id), 'created_by': str(current_user['_id'])})
    if not job:
        return jsonify({'error': 'Job not found or unauthorized'}), 404
    
    # Get all applications for this job
    applications = list(applications_collection.find({'job_id': job_id}))
    
    # Convert ObjectId to string
    for app in applications:
        app['_id'] = str(app['_id'])
    
    return jsonify({
        'job': {
            'id': str(job['_id']),
            'title': job.get('title'),
            'department': job.get('department'),
            'location': job.get('location')
        },
        'applications': applications
    }), 200

# ========= SINGLE APPLICATION (BY ID) ENDPOINT =========

@app.route('/api/applications/<application_id>', methods=['GET'])
@cross_origin()
@token_required
def get_application_by_id(current_user, application_id):
    """Get a single application document by id with job details.
    - Candidate can view their own application.
    - Recruiter can view if they own the job for this application.
    """
    try:
        app_doc = applications_collection.find_one({'_id': ObjectId(application_id)})
    except Exception:
        return jsonify({'error': 'Invalid application id'}), 400

    if not app_doc:
        return jsonify({'error': 'Application not found'}), 404

    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type in ['candidate', 'student']:
        if app_doc.get('student_id') != str(current_user['_id']):
            return jsonify({'error': 'Unauthorized'}), 403
    elif user_type == 'recruiter':
        job = db.jobs.find_one({'_id': ObjectId(app_doc['job_id'])})
        if not job or job.get('created_by') != str(current_user['_id']):
            return jsonify({'error': 'Unauthorized'}), 403
    else:
        return jsonify({'error': 'Unauthorized'}), 403

    # shape response
    app_doc['_id'] = str(app_doc['_id'])
    if isinstance(app_doc.get('applied_at'), datetime.datetime):
        app_doc['applied_at'] = app_doc['applied_at'].isoformat()
    if isinstance(app_doc.get('updated_at'), datetime.datetime):
        app_doc['updated_at'] = app_doc['updated_at'].isoformat()
    if app_doc.get('cv_score') is None:
        app_doc['cv_score'] = 85.0
    if 'interview_score' not in app_doc:
        app_doc['interview_score'] = None

    job = db.jobs.find_one({'_id': ObjectId(app_doc['job_id'])})
    if job:
        app_doc['job_details'] = {
            'title': job.get('title'),
            'company': job.get('company', 'TechCorp Solutions'),
            'location': job.get('location'),
            'type': job.get('type'),
            'department': job.get('department'),
            'logo': job.get('logo')
        }

    # whether report exists
    app_doc['report_available'] = interviews_collection.find_one({'application_id': app_doc['_id'], 'status': 'completed'}) is not None

    return jsonify(app_doc), 200

# Interview report retrieval by application id
@app.route('/api/applications/<application_id>/interview-report', methods=['GET'])
@cross_origin()
@token_required
def get_interview_report(current_user, application_id):
    """Return the latest interview report for a given application.
    - Candidate can view their own.
    - Recruiter can view if they own the job for this application.
    """
    try:
        app_doc = applications_collection.find_one({'_id': ObjectId(application_id)})
    except Exception:
        return jsonify({'error': 'Invalid application id'}), 400

    if not app_doc:
        return jsonify({'error': 'Application not found'}), 404

    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type in ['candidate', 'student']:
        if app_doc.get('student_id') != str(current_user['_id']):
            return jsonify({'error': 'Unauthorized'}), 403
    elif user_type == 'recruiter':
        job = db.jobs.find_one({'_id': ObjectId(app_doc['job_id'])})
        if not job or job.get('created_by') != str(current_user['_id']):
            return jsonify({'error': 'Unauthorized'}), 403
    else:
        return jsonify({'error': 'Unauthorized'}), 403

    report = interviews_collection.find_one(
        {'application_id': application_id, 'status': 'completed'},
        sort=[('updated_at', -1)]
    )
    if not report:
        return jsonify({'error': 'Report not found'}), 404

    # Return lightweight report summary
    payload = {
        'session_id': report.get('session_id'),
        'final_score': report.get('final_score'),
        'proctoring_score': report.get('proctoring_score'),
        'evaluation': report.get('evaluation')
    }
    return jsonify(payload), 200

# Test endpoint to create sample jobs
@app.route('/api/create-sample-jobs', methods=['POST'])
@cross_origin()
def create_sample_jobs():
    """Create sample jobs for testing (development only)"""
    sample_jobs = [
        {
            'title': 'Senior Business Development Manager',
            'department': 'Sales',
            'location': 'San Francisco, CA (Remote)',
            'type': 'Full-time',
            'experience': '5+ years',
            'salary': '$120,000 - $150,000',
            'description': 'We are looking for an experienced Business Development Manager with expertise in client acquisition to join our growing team.',
            'skills': ['Sales Strategy', 'Client Acquisition', 'Market Research', 'Negotiation'],
            'status': 'active',
            'created_by': 'sample_recruiter',
            'created_at': datetime.datetime.utcnow(),
            'deadline': datetime.datetime.utcnow() + datetime.timedelta(days=30),
            'applicants': 0,
            'interviewed': 0,
            'selected': 0,
            'rejected': 0,
            'pending': 0
        },
        {
            'title': 'Strategic Partnerships Manager',
            'department': 'Business Development',
            'location': 'New York, NY',
            'type': 'Full-time',
            'experience': '3+ years',
            'salary': '$110,000 - $140,000',
            'description': 'Join our business team to develop strategic partnerships and drive mutual growth with key stakeholders.',
            'skills': ['Partnership Development', 'Contract Negotiation', 'Relationship Management'],
            'status': 'active',
            'created_by': 'sample_recruiter',
            'created_at': datetime.datetime.utcnow(),
            'deadline': datetime.datetime.utcnow() + datetime.timedelta(days=25),
            'applicants': 0,
            'interviewed': 0,
            'selected': 0,
            'rejected': 0,
            'pending': 0
        },
        {
            'title': 'Software Engineer',
            'department': 'Technology',
            'location': 'Remote',
            'type': 'Full-time',
            'experience': '2+ years',
            'salary': '$95,000 - $125,000',
            'description': 'We are seeking a talented Software Engineer to join our dynamic development team.',
            'skills': ['Python', 'JavaScript', 'React', 'Node.js', 'MongoDB'],
            'status': 'active',
            'created_by': 'sample_recruiter',
            'created_at': datetime.datetime.utcnow(),
            'deadline': datetime.datetime.utcnow() + datetime.timedelta(days=20),
            'applicants': 0,
            'interviewed': 0,
            'selected': 0,
            'rejected': 0,
            'pending': 0
        }
    ]
    
    # Insert sample jobs
    for job_data in sample_jobs:
        # Check if job already exists
        existing = db.jobs.find_one({'title': job_data['title'], 'created_by': 'sample_recruiter'})
        if not existing:
            db.jobs.insert_one(job_data)
    
    return jsonify({'message': 'Sample jobs created successfully'}), 201


if __name__ == '__main__':
    print("🚀 Starting Flask server with real-time proctoring capabilities...")
    # Auto-seed jobs if empty (dev convenience)
    try:
        if db.jobs.count_documents({}) == 0:
            print("📦 Seeding sample jobs (collection empty)...")
            sample_jobs = [
                {
                    'title': 'Senior Business Development Manager',
                    'department': 'Sales',
                    'location': 'San Francisco, CA (Remote)',
                    'type': 'Full-time',
                    'experience': '5+ years',
                    'salary': '$120,000 - $150,000',
                    'description': 'We are looking for an experienced Business Development Manager with expertise in client acquisition to join our growing team.',
                    'skills': ['Sales Strategy', 'Client Acquisition', 'Market Research', 'Negotiation'],
                    'status': 'active',
                    'created_by': 'system',
                    'created_at': datetime.datetime.utcnow(),
                    'applicants': 0,
                    'interviewed': 0,
                    'selected': 0,
                    'rejected': 0,
                    'pending': 0
                },
                {
                    'title': 'Strategic Partnerships Manager',
                    'department': 'Business Development',
                    'location': 'New York, NY',
                    'type': 'Full-time',
                    'experience': '3+ years',
                    'salary': '$110,000 - $140,000',
                    'description': 'Join our business team to develop strategic partnerships and drive mutual growth with key stakeholders.',
                    'skills': ['Partnership Development', 'Contract Negotiation', 'Relationship Management'],
                    'status': 'active',
                    'created_by': 'system',
                    'created_at': datetime.datetime.utcnow(),
                    'applicants': 0,
                    'interviewed': 0,
                    'selected': 0,
                    'rejected': 0,
                    'pending': 0
                }
            ]
            db.jobs.insert_many(sample_jobs)
            print("✅ Seeded sample jobs.")
    except Exception as e:
        print(f"⚠️ Job seeding skipped due to error: {e}")
    # Run with SocketIO server to ensure compatibility with websockets
    socketio.run(app, debug=False, use_reloader=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)