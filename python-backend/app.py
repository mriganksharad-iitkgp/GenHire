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

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = 'your-secret-key-here'

mongo_uri='mongodb+srv://adityapandeygkp90:CgsSnvo0o1WoRMmQ@hrtech.yneajzv.mongodb.net/?retryWrites=true&w=majority&appName=hrtech'
client = MongoClient(mongo_uri)
career_portal = 'hrtech'  # Your database name
db = client[career_portal]  # Use the variable directly
users_collection = db['users']

document_pdf_path = "Eric Ries - The Lean Startup.pdf"  # Path to the document for querying
groq_api_key = "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"  # Replace with actual API key
processor = PDFProcessor(document_pdf_path, groq_api_key)

# Define directories for storing files
UPLOAD_FOLDER = "uploads"
JD_FOLDER = os.path.join(UPLOAD_FOLDER, "jd")
CV_FOLDER = os.path.join(UPLOAD_FOLDER, "cv")

# Ensure folders exist
os.makedirs(JD_FOLDER, exist_ok=True)
os.makedirs(CV_FOLDER, exist_ok=True)

app.config["JD_FOLDER"] = JD_FOLDER
app.config["CV_FOLDER"] = CV_FOLDER
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

if __name__ == '__main__':
    # app.run(debug=False,host='10.29.8.94')
    app.run(debug=True)