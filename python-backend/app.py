import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Define directories for storing files
UPLOAD_FOLDER = "uploads"
JD_FOLDER = os.path.join(UPLOAD_FOLDER, "jd")
CV_FOLDER = os.path.join(UPLOAD_FOLDER, "cv")

# Ensure folders exist
os.makedirs(JD_FOLDER, exist_ok=True)
os.makedirs(CV_FOLDER, exist_ok=True)

app.config["JD_FOLDER"] = JD_FOLDER
app.config["CV_FOLDER"] = CV_FOLDER
app.config["ALLOWED_EXTENSIONS"] = {"pdf", "docx"}

# Function to check allowed file types
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

# Route to handle file uploads
@app.route("/api/upload", methods=["POST"])
def upload_files():
    if "jd" not in request.files or "cv" not in request.files:
        return jsonify({"error": "Both JD and CV files are required"}), 400

    jd_file = request.files["jd"]
    cv_file = request.files["cv"]

    if jd_file and allowed_file(jd_file.filename):
        jd_filename = secure_filename(jd_file.filename)
        jd_path = os.path.join(app.config["JD_FOLDER"], jd_filename)
        jd_file.save(jd_path)
    else:
        return jsonify({"error": "Invalid JD file format"}), 400

    if cv_file and allowed_file(cv_file.filename):
        cv_filename = secure_filename(cv_file.filename)
        cv_path = os.path.join(app.config["CV_FOLDER"], cv_filename)
        cv_file.save(cv_path)
    else:
        return jsonify({"error": "Invalid CV file format"}), 400

    return jsonify({"message": "Files uploaded successfully!"}), 200

if __name__ == "__main__":
    app.run(debug=True)
