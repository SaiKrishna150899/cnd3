import os
import json
from flask import Flask, redirect, request, render_template
from google.cloud import storage
import google.generativeai as genai
import re
from io import BytesIO
from google.cloud import secretmanager

app = Flask(__name__)
app.secret_key = "your-secret-key"

bucket_name = 'appz_buckets'
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)

os.makedirs('files', exist_ok=True)

def get_gemini_api_key():
    secret_client = secretmanager.SecretManagerServiceClient()
    name = "projects/cloudnative12/secrets/geminiSecret/versions/latest"
    response = secret_client.access_secret_version(request={"name": name})
    gemini_api_key = response.payload.data.decode("UTF-8")
    return gemini_api_key

def upload_blob(file, blob_name):
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file)

def upload_json(data, blob_name):
    blob = bucket.blob(blob_name)
    blob.upload_from_string(json.dumps(data, indent=4), content_type='application/json')

def list_images():
    blobs = bucket.list_blobs()
    files = []
    for blob in blobs:
        if blob.name.lower().endswith(('.png', '.jpg', '.jpeg')):
            j_blob = f"{os.path.splitext(blob.name)[0]}.json"
            try:
                title_blob = bucket.blob(j_blob)
                title_data = title_blob.download_as_string()
                title_json = json.loads(title_data)
            except Exception as e:
                title_json = {"title": "No title", "description": "No description"}
                
            files.append({
                "name": blob.name,
                "title": title_json["title"],
                "description": title_json["description"]
            })

    return sorted(files, key=lambda x: x['name'], reverse=True)

@app.route('/')
def index():
    return render_template('index.html', images=list_images())

def generate_description(image_file):
    genai.configure(api_key=get_gemini_api_key())
    model = genai.GenerativeModel("gemini-1.5-flash")
    image_blob = {"mime_type": "image/jpeg", "data": image_file}

    prompt = (
        "Analyze the image and generate a clear title and description.\n\n"
        "Strictly respond in this JSON format:\n"
        "{\n"
        " 'title': 'A short, engaging title',\n"
        " 'description':'2-3 sentences describing the image'\n"
        "}\n"
    )

    response = model.generate_content([image_blob, prompt])

    if response and hasattr(response, 'text'):
        res = response.text.strip()
        res = re.sub(r"^```json\n|\n```$", "", res)

        try:
            return json.loads(res)
        except json.JSONDecodeError:
            return {"title": "No title", "description": "No description"}

    return {"title": "No title", "description": "No description"}

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['formFile']
    filename = file.filename
    image = file.read()

    data = generate_description(image)

    file.seek(0)
    upload_blob(file, filename)

    json_file = f"{os.path.splitext(filename)[0]}.json"
    upload_json(data, json_file)

    return redirect('/')

@app.route('/files/<filename>')
def get_file(filename):
    blob = bucket.blob(filename)

    fs = BytesIO()
    blob.download_to_file(fs)
    
    fs.seek(0)

    return app.response_class(fs.read(), mimetype='image/jpeg')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
