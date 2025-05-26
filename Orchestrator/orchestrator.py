# app/orchestrator.py
import os
import zipfile
import tarfile
import tempfile
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import requests

app = Flask(__name__)

def log(msg):
    print(f"[{datetime.now().isoformat()}] {msg}")

def extract_archive(archive_path, extract_to):
    if archive_path.endswith('.zip'):
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    elif archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(path=extract_to)
    else:
        raise ValueError("Unsupported archive format. Use .zip or .tgz")

# Function to get the bearer token
def get_bearer_token():
    url = 'http://ip:8080/auth/realms/opademo/protocol/openid-connect/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'client_id': 'lcl',
        'username': 'SO',
        'password': 'SO',
        'grant_type': 'password',
        'client_secret': 'secret'
    }

    response = requests.post(url, headers=headers, data=data)
    
    if response.status_code == 200:
        token = response.json().get('access_token')
        return token
    else:
        print(f"Failed to get token: {response.status_code} - {response.text}")
        return None

# Function to establish a tunnel and return the tunnel ID
def establish_tunnel(bearer_token):
    url = 'http://ip:9080/ccips'
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {bearer_token}'
    }
    data = {
        "nodes": [
            {"ipData": "10.0.3.11", "ipControl": "192.168.159.242"},
            {"ipData": "10.0.3.12", "ipControl": "192.168.159.254"}
        ],
        "encAlg": ["aes-cbc"],
        "intAlg": ["sha2-256"],
        "softLifetime": {"nTime": 10},
        "hardLifetime": {"nTime": 30}
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        tunnel_id = response.json().get('id')
        return tunnel_id
    else:
        print(f"Failed to establish tunnel: {response.status_code} - {response.text}")
        return None

# Function to delete the tunnel by ID
def delete_tunnel(bearer_token, tunnel_id):
    url = f'http://ip:9080/ccips/{tunnel_id}'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {bearer_token}'
    }

    response = requests.delete(url, headers=headers)

    if response.status_code == 200:
        print(f"Tunnel {tunnel_id} successfully deleted.")
    else:
        print(f"Failed to delete tunnel {tunnel_id}: {response.status_code} - {response.text}")

@app.route('/')
def index():
    return render_template_string(open(os.path.join(os.path.dirname(__file__), "app/ui.html")).read())

@app.route('/deploy', methods=['POST'])
def deploy_charts():
    if 'archive' not in request.files:
        return jsonify({'error': 'No archive file uploaded'}), 400

    archive_file = request.files['archive']
    log(f"Received archive: {archive_file.filename}")

    # # Step 1: Get Bearer Token
    # token = get_bearer_token()
    # if not token:
    #     return jsonify({'error': 'Failed to retrieve bearer token'}), 500
    # log("Bearer token retrieved successfully.")

    # # Step 2: Establish Tunnel
    # try:
    #     establish_tunnel(token)
    #     log("Tunnel established successfully.")
    # except Exception as e:
    #     return jsonify({'error': f'Failed to establish tunnel: {str(e)}'}), 500

    # Step 3: Only continue if both previous steps succeeded
    results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, archive_file.filename)
        archive_file.save(archive_path)

        try:
            extract_archive(archive_path, tmpdir)
            log(f"Archive extracted to {tmpdir}")
        except Exception as e:
            return jsonify({'error': f'Failed to extract archive: {str(e)}'}), 500

        for item in os.listdir(tmpdir):
            chart_path = os.path.join(tmpdir, item)
            if os.path.isdir(chart_path) and os.path.exists(os.path.join(chart_path, 'Chart.yaml')):
                release_name = item
                try:
                    result = subprocess.run(
                        ["helm", "upgrade", "--install", release_name, chart_path, "--set", "image.pullPolicy=Never"],
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    log(f"Deployed chart: {release_name}")
                    results.append({'chart': release_name, 'status': 'deployed', 'log': result.stdout})
                except subprocess.CalledProcessError as e:
                    log(f"Error deploying chart {release_name}: {e.stderr}")
                    results.append({'chart': release_name, 'status': 'error', 'log': e.stderr})

    return jsonify({'deployments': results}), 200


@app.route('/undeploy', methods=['POST'])
def undeploy_chart():
    data = request.get_json()
    if not data or 'release' not in data:
        return jsonify({'error': 'Missing "release" name in request body'}), 400

    release_name = data['release']
    try:
        result = subprocess.run(
            ["helm", "uninstall", release_name],
            check=True,
            capture_output=True,
            text=True
        )
        return jsonify({'release': release_name, 'status': 'uninstalled', 'log': result.stdout}), 200
    except subprocess.CalledProcessError as e:
        return jsonify({'release': release_name, 'status': 'error', 'log': e.stderr}), 500

@app.route('/status', methods=['POST'])
def status_chart():
    data = request.get_json()
    if not data or 'release' not in data:
        return jsonify({'error': 'Missing "release" name in request body'}), 400

    release_name = data['release']
    try:
        result = subprocess.run(
            ["helm", "status", release_name, "--output", "json"],
            check=True,
            capture_output=True,
            text=True
        )
        return jsonify({'release': release_name, 'status': 'found', 'details': result.stdout}), 200
    except subprocess.CalledProcessError as e:
        return jsonify({'release': release_name, 'status': 'not found or error', 'log': e.stderr}), 404

if __name__ == '__main__':
    log("Orchestrator started")
    app.run(host='0.0.0.0', port=8090)
