# app/orchestrator.py
import os
import tarfile
import zipfile
import tempfile
import subprocess
import yaml
import numpy as np
import pandas as pd
import joblib
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import requests

app = Flask(__name__)

# Load ML Model and Preprocessor
OCSVM_MODEL_PATH = "ocsvm_model.pkl"
PREPROCESSOR_PATH = "preprocessor.pkl"
ocsvm = joblib.load(OCSVM_MODEL_PATH)
preprocessor = joblib.load(PREPROCESSOR_PATH)

def log(msg):
    print(f"[{datetime.now().isoformat()}] {msg}")

# Preprocessing Function
def preprocess_values(values):
    """
    Extracts relevant values and returns a DataFrame suitable for prediction.
    Assumes no top-level component key; infers type from namespace.app
    """
    try:
        component_name = values.get("namespace", {}).get("app", "").upper()
        if component_name not in ["COMPRESSOR", "GRAYSCALER"]:
            raise ValueError(f"Unknown component type: '{component_name}'")

        replica_count = values.get("replicaCount", 0)
        cpu_limit = values.get("resources", {}).get("limits", {}).get("cpu", 0)
        memory_limit = values.get("resources", {}).get("limits", {}).get("memory", 0)

        return pd.DataFrame([{
            "replica_count": replica_count,
            "cpu_limit": int(cpu_limit),
            "memory_limit": int(memory_limit),
            "network_function": component_name
        }])

    except Exception as e:
        raise ValueError(f"Error preprocessing values.yaml: {e}")


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
    url = 'http://localhost:8080/auth/realms/opademo/protocol/openid-connect/token'
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
    return render_template_string("""
        <h2>Helm Chart Deployment Interface</h2>
        <form action="/deploy" method="post" enctype="multipart/form-data">
            <input type="file" name="archive">
            <input type="submit" value="Deploy">
        </form>
    """)

@app.route('/deploy', methods=['POST'])
def deploy_charts():
    if 'archive' not in request.files:
        return jsonify({'error': 'No archive file uploaded'}), 400

    archive_file = request.files['archive']
    log(f"Received archive: {archive_file.filename}")

    # # Step 1: Get Bearer Token
    # token = None
    # try:
    #     token = get_bearer_token()
    #     if not token:
    #         log("Error: Failed to retrieve bearer token.")
    #         return jsonify({'error': 'Failed to retrieve bearer token'}), 500
    #     log("Bearer token retrieved successfully.")
    # except Exception as e:
    #     log(f"Exception during token retrieval: {str(e)}")
    #     return jsonify({'error': f'Exception during token retrieval: {str(e)}'}), 500

    # # Step 2: Establish Tunnel
    # try:
    #     tunnel_id = establish_tunnel(token)
    #     if not tunnel_id:
    #         log("Error: Failed to establish tunnel.")
    #         return jsonify({'error': 'Failed to establish tunnel'}), 500
    #     log(f"Tunnel established successfully. ID: {tunnel_id}")
    # except Exception as e:
    #     log(f"Exception during tunnel setup: {str(e)}")
    #     return jsonify({'error': f'Exception during tunnel setup: {str(e)}'}), 500

    results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, archive_file.filename)
        archive_file.save(archive_path)

        try:
            extract_archive(archive_path, tmpdir)
            log(f"Archive extracted to {tmpdir}")
        except Exception as e:
            return jsonify({'error': f'Failed to extract archive: {str(e)}'}), 500
        
        for root, dirs, files in os.walk(tmpdir):
            for name in files:
                if name == "values.yaml":
                    try:
                        with open(os.path.join(root, name), 'r') as f:
                            values = yaml.safe_load(f)

                        test_data = preprocess_values(values)
                        test_data_preprocessed = preprocessor.transform(test_data)
                        predictions = ocsvm.predict(test_data_preprocessed)
                        
                        predicted_labels = np.where(predictions == 1, 1, 0)
                        #test_data['predicted_label'] = np.where(predictions == 1, 1, 0)

                        results.append({
                            'chart_path': root,
                            'predictions': test_data.to_dict(orient='records')
                        })
                    
                        if np.any(predicted_labels == 0):
                            log(f"Skipping deployment of chart at {root} due to predicted label 0.")
                            results.append({'chart': root, 'status': 'skipped due to predicted label 0'})
                            continue
                        
                        release_name = os.path.basename(root)
                        if os.path.exists(os.path.join(root, 'Chart.yaml')):
                            result = subprocess.run(
                                ["helm", "upgrade", "--install", release_name, root, "--set", "image.pullPolicy=Never"],
                                check=True,
                                capture_output=True,
                                text=True
                            )
                            log(f"Deployed chart: {release_name}")
                            results.append({'chart': release_name, 'status': 'deployed', 'log': result.stdout})

                    except Exception as e:
                        log(f"Error during prediction or deployment: {str(e)}")
                        results.append({'error': str(e), 'chart_path': root})
        

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
    app.run(host='0.0.0.0', port=8000)
