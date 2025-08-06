from flask import Flask, request, jsonify, redirect
from supabase import create_client, Client
from datetime import datetime, timedelta
from flask_cors import CORS
from io import BytesIO
import shortuuid
import os

# ------------------
# Supabase Setup
# ------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET_NAME = "filebucket"  # ✅ Ensure this bucket exists in Supabase

# ------------------
# Flask App
# ------------------
app = Flask(__name__)
CORS(app)
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "✅ File sharing backend is running."}), 200

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
    expires_at = (datetime.utcnow() + timedelta(minutes=expiry_minutes)).isoformat()

    # ✅ Upload file bytes to Supabase
    res = supabase.storage.from_(BUCKET_NAME).upload(
        path=filename,
        file=file.read(),  # 👈 THIS is the fix
        file_options={"content-type": file.mimetype}
    )

    if res.get("error"):
        return jsonify({"error": "Upload to storage failed", "details": res["error"]}), 500

    # ✅ Save metadata to DB
    data = {
        "filename": file.filename,
        "token": file_id,
        "storage_path": filename,
        "access_limit": access_limit,
        "expires_at": expires_at
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

    # ✅ Expiry check
    if datetime.utcnow() > datetime.fromisoformat(file_entry["expires_at"]):
        return jsonify({"error": "File expired"}), 403

    # ✅ Access limit check
    if file_entry["access_limit"] <= 0:
        return jsonify({"error": "Download limit reached"}), 403

    # ✅ Decrement access limit
    supabase.table("files").update(
        {"access_limit": file_entry["access_limit"] - 1}
    ).eq("token", token).execute()

    # ✅ Create signed download URL (valid for 2 minutes)
    signed = supabase.storage.from_(BUCKET_NAME).create_signed_url(file_entry["storage_path"], 120)
    if signed.get("error"):
        return jsonify({"error": "Unable to generate download URL"}), 500

    return redirect(signed["signedURL"])


