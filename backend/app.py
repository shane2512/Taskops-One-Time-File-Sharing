from flask import Flask, request, send_file, jsonify
from supabase import create_client, Client
from datetime import datetime, timedelta
import shortuuid
import os
import io
import threading
import time
from flask_cors import CORS

# ------------------
# Supabase Setup
# ------------------
import os
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Flask App
app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------
# Upload File Route
# ------------------
@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    access_limit = int(request.form.get("access_limit", 1))
    expiry_minutes = int(request.form.get("expiry_minutes", 10))
    file_id = shortuuid.uuid()
    filename = f"{file_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    expires_at = (datetime.utcnow() + timedelta(minutes=expiry_minutes)).isoformat()

    # Insert record into Supabase
    data = {
        "filename": file.filename,
        "filepath": filepath,
        "token": file_id,
        "access_limit": access_limit,
        "expires_at": expires_at,
    }
    supabase.table("files").insert(data).execute()

    return jsonify({
        "message": "File uploaded",
        "download_link": request.host_url + f"download/{file_id}"
    }), 201

# ------------------
# Download File Route
# ------------------
@app.route("/download/<token>", methods=["GET"])
def download_file(token):
    result = supabase.table("files").select("*").eq("token", token).execute()

    if not result.data:
        return jsonify({"error": "Invalid or expired link"}), 404

    file_entry = result.data[0]

    if datetime.utcnow() > datetime.fromisoformat(file_entry["expires_at"]):
        delete_file(file_entry)
        return jsonify({"error": "File expired"}), 403

    if file_entry["access_limit"] <= 0:
        delete_file(file_entry)
        return jsonify({"error": "Download limit reached"}), 403

    # Read file
    if not os.path.exists(file_entry["filepath"]):
        return jsonify({"error": "File not found"}), 404

    with open(file_entry["filepath"], "rb") as f:
        file_data = f.read()

    # Decrement access limit
    supabase.table("files").update({"access_limit": file_entry["access_limit"] - 1}).eq("token", token).execute()

    # Start delete timer
    threading.Thread(target=lambda: delete_after_delay(file_entry), daemon=True).start()

    return send_file(
        io.BytesIO(file_data),
        as_attachment=True,
        download_name=file_entry["filename"]
    )

# ------------------
# Delete File and Record
# ------------------
def delete_after_delay(file_entry):
    time.sleep(60)
    delete_file(file_entry)

def delete_file(file_entry):
    try:
        if os.path.exists(file_entry["filepath"]):
            os.remove(file_entry["filepath"])
    except Exception as e:
        print(f"Error deleting file: {e}")
    supabase.table("files").delete().eq("token", file_entry["token"]).execute()
    print(f"Deleted: {file_entry['filename']}")
