import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS, cross_origin
from qa import PDFProcessor
from werkzeug.utils import secure_filename
import uuid  # new import
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import jwt as pyjwt 
import datetime
from functools import wraps
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# Import interview system
from interview_system import session_manager

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = 'your-secret-key-here'

mongo_uri='mongodb+srv://adityapandeygkp90:CgsSnvo0o1WoRMmQ@hrtech.yneajzv.mongodb.net/?retryWrites=true&w=majority&appName=hrtech'
client = MongoClient(mongo_uri)
career_portal = 'hrtech'  # Your database name
db = client[career_portal]  # Use the variable directly
users_collection = db['users']
interviews_collection = db['interviews']  # New collection for interviews

document_pdf_path = "Eric Ries - The Lean Startup.pdf"  # Path to the document for querying
groq_api_key = "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"  # Replace with actual API key
processor = PDFProcessor(document_pdf_path, groq_api_key)

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

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = pyjwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])  # Use pyjwt here
            current_user = users_collection.find_one({'_id': ObjectId(data['user_id'])})
            
            if not current_user:
                return jsonify({'message': 'User not found!'}), 401
                
        except pyjwt.ExpiredSignatureError:  # And here
            return jsonify({'message': 'Token has expired!'}), 401
        except pyjwt.InvalidTokenError:  # And here
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

    # Validation
    if not all([name, email, password, confirm_password]):
        return jsonify({'error': 'All fields are required'}), 400
    
    if password != confirm_password:
        return jsonify({'error': 'Passwords do not match'}), 400
    
    # Check if user exists
    if users_collection.find_one({'email': email}):
        return jsonify({'error': 'Email already exists'}), 400
    
    # Create new user
    user_id = users_collection.insert_one({
        'name': name,
        'email': email,
        'password': generate_password_hash(password),
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow()
    }).inserted_id
    
    # Generate token
    token = generate_token(user_id)
    
    return jsonify({
        'message': 'User registered successfully',
        'token': token,
        'user': {
            'id': str(user_id),
            'name': name,
            'email': email
        }
    }), 201

@app.route("/api/login", methods=["POST"])
@cross_origin()
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    user = users_collection.find_one({'email': email})
    
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid credentials'}), 401
    # Generate token
    token = generate_token(user['_id'])
    print("Logged in")
    return jsonify({
        'message': 'Logged in successfully',
        'token': token,
        'user': {
            'id': str(user['_id']),
            'name': user['name'],
            'email': user['email']
        }
    }), 200

@app.route("/api/me", methods=["GET"])
@cross_origin()
@token_required
def get_current_user(current_user):
    return jsonify({
        'id': str(current_user['_id']),
        'name': current_user['name'],
        'email': current_user['email']
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

    similarity = float(processor.get_similarity(cv_path, jd_path))

    interview_questions = processor.generate_initial_questions(cv_path, jd_path)
    
    return jsonify({
        "message": "Files uploaded successfully!",
        "jd_file_path": jd_path,
        "cv_file_path": cv_path,
        "similarity": similarity,
        "interview_questions": interview_questions
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
    result = processor.query_document(question)

    return jsonify({'result': str(result)})

# Interview System API Routes
@app.route('/api/interviews/start', methods=['POST'])
@cross_origin()
@token_required
def start_interview(current_user):
    data = request.json
    
    # Get file paths (either from request or use defaults for testing)
    cv_path = data.get('cv_path', "uploads/cv/PeterConnollyResume-2.pdf")
    jd_path = data.get('jd_path', "uploads/jd/JD1.pdf")
    reference_path = data.get('reference_path', "Eric Ries - The Lean Startup.pdf")
    
    # Create a new interview session
    session_data = session_manager.create_session(cv_path, jd_path, reference_path)
    
    # Store session info in the database
    interview_id = interviews_collection.insert_one({
        'user_id': str(current_user['_id']),
        'session_id': session_data['session_id'],
        'cv_path': cv_path,
        'jd_path': jd_path,
        'reference_path': reference_path,
        'status': 'active',
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow()
    }).inserted_id
    
    return jsonify({
        'interview_id': str(interview_id),
        'session_id': session_data['session_id'],
        'initial_questions': session_data['initial_questions'],
        'similarity_score': session_data['similarity_score']
    })

@app.route('/api/interviews/<session_id>/question', methods=['GET'])
@cross_origin()
def get_interview_question(session_id):
    # Get session data
    session_data = session_manager.get_session(session_id)
    
    if not session_data:
        return jsonify({'error': 'Interview session not found'}), 404
    
    return jsonify({
        'current_questions': session_data['current_questions']
    })

@app.route('/api/interviews/<session_id>/answer', methods=['POST'])
@cross_origin()
def submit_answer(session_id):
    data = request.json
    question = data.get('question')
    answer = data.get('answer')
    
    if not question or not answer:
        return jsonify({'error': 'Question and answer are required'}), 400
    
    # Process the answer and get the next question
    result = session_manager.submit_answer(session_id, question, answer)
    
    if 'error' in result:
        return jsonify(result), 404
    
    return jsonify(result)

@app.route('/api/interviews/<session_id>/end', methods=['POST'])
@cross_origin()
@token_required
def end_interview(current_user, session_id):
    # End the interview session and get the final evaluation
    result = session_manager.end_session(session_id)
    
    if 'error' in result:
        return jsonify(result), 404
    
    # Update interview status in the database
    interviews_collection.update_one(
        {'session_id': session_id, 'user_id': str(current_user['_id'])},
        {'$set': {
            'status': 'completed',
            'evaluation': result['evaluation'],
            'updated_at': datetime.datetime.utcnow()
        }}
    )
    
    return jsonify(result)

@app.route('/api/interviews', methods=['GET'])
@cross_origin()
@token_required
def get_user_interviews(current_user):
    # Get all interviews for the current user
    user_interviews = list(interviews_collection.find({'user_id': str(current_user['_id'])}))
    
    # Format the interviews for JSON response
    formatted_interviews = []
    for interview in user_interviews:
        formatted_interviews.append({
            'id': str(interview['_id']),
            'session_id': interview['session_id'],
            'status': interview['status'],
            'created_at': interview['created_at'].isoformat(),
            'updated_at': interview['updated_at'].isoformat(),
            'cv_path': interview.get('cv_path'),
            'jd_path': interview.get('jd_path')
        })
    
    return jsonify(formatted_interviews)

@app.route('/api/interviews/<session_id>/upload-recording', methods=['POST'])
@cross_origin()
@token_required
def upload_interview_recording(current_user, session_id):
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    
    # Validate the file is a video
    if not video_file.filename.lower().endswith(('.webm', '.mp4', '.mov')):
        return jsonify({'error': 'Invalid video format'}), 400
    
    # Create session-specific folder
    session_folder = os.path.join(app.config["PROCTORING_FOLDER"], session_id)
    os.makedirs(session_folder, exist_ok=True)
    
    # Save the video
    filename = secure_filename(f"recording_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{video_file.filename}")
    video_path = os.path.join(session_folder, filename)
    video_file.save(video_path)
    
    # Update interview record in database
    interviews_collection.update_one(
        {'session_id': session_id, 'user_id': str(current_user['_id'])},
        {'$push': {
            'recordings': {
                'path': video_path,
                'timestamp': datetime.datetime.utcnow()
            }
        }}
    )
    
    return jsonify({'message': 'Recording saved successfully'}), 200


if __name__ == '__main__':
    # app.run(debug=False,host='10.29.8.94')
    app.run(debug=True)