import io
import os
import threading
import time
from flask import Flask, request, send_file, jsonify, after_this_request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import shortuuid
from datetime import datetime, timedelta

# Initialize Flask App
app = Flask(__name__)
CORS(app)

# Load Configuration from config.py
app.config.from_pyfile("config.py")

# Ensure UPLOAD_FOLDER is set before usage
if "UPLOAD_FOLDER" not in app.config:
    app.config["UPLOAD_FOLDER"] = "backend/uploads"

# Ensure Upload Folder Exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize Database
db = SQLAlchemy(app)

# Database Model
class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    token = db.Column(db.String(50), unique=True, nullable=False)
    access_limit = db.Column(db.Integer, default=1)
    expires_at = db.Column(db.DateTime, nullable=False)

# Initialize Database Tables
with app.app_context():
    db.create_all()

# Home Route - Health Check
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Flask File Sharing API is running!"}), 200

# Upload File API
@app.route("/upload", methods=["POST"])

def upload_file():
    """Handles file upload, generates a unique link, and sets expiry & access limits."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    access_limit = request.form.get("access_limit", 1, type=int)
    expiry_minutes = request.form.get("expiry_minutes", 10, type=int)

    file_id = shortuuid.uuid()
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file_id + "_" + file.filename)
    file.save(filepath)

    expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)

    new_file = File(filename=file.filename, filepath=filepath, token=file_id, 
                    access_limit=access_limit, expires_at=expires_at)
    db.session.add(new_file)
    db.session.commit()

    # Fix: Return full URL instead of a relative path
    full_download_url = request.host_url + f"download/{file_id}"

    return jsonify({"message": "File uploaded", "download_link": full_download_url}), 201

# Download File API (One-Time with Delayed Deletion)
@app.route("/download/<token>", methods=["GET"])
def download_file(token):
    """Downloads the file and schedules its deletion 60 seconds after the first click."""
    file_entry = File.query.filter_by(token=token).first()

    if not file_entry:
        return jsonify({"error": "Invalid or expired link"}), 404

    if datetime.utcnow() > file_entry.expires_at or file_entry.access_limit <= 0:
        delete_file(file_entry)
        return jsonify({"error": "File expired or limit reached"}), 403

    if not os.path.exists(file_entry.filepath):
        return jsonify({"error": "File not found"}), 404  

    try:
        # Read file into memory to avoid file-locking issues on Windows
        with open(file_entry.filepath, "rb") as f:
            file_data = f.read()

        # Schedule deletion after 60 seconds in a background thread
        def delete_after_delay():
            time.sleep(10)
            # Check if file still exists before deletion
            if os.path.exists(file_entry.filepath):
                delete_file(file_entry)
                print(f"File {file_entry.filename} (token: {file_entry.token}) deleted after 60 seconds.")

        # Only schedule deletion on the first click
        threading.Thread(target=delete_after_delay, daemon=True).start()

        return send_file(
            io.BytesIO(file_data),
            as_attachment=True,
            download_name=os.path.basename(file_entry.filepath),
        )
    
    except Exception as e:
        return jsonify({"error": f"File access error: {str(e)}"}), 500

# Function to delete file and remove record from DB
def delete_file(file_entry):
    """Removes file from storage and database."""
    print(f"Deleting file: {file_entry.filename} (Token: {file_entry.token})")
    try:
        if os.path.exists(file_entry.filepath):
            os.remove(file_entry.filepath)
    except Exception as e:
        print(f"Error deleting file: {str(e)}")
    db.session.delete(file_entry)
    db.session.commit()
    print("File deleted successfully.")

if __name__ == "__main__":
    app.run(debug=True)
