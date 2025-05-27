# Orchestrator_it6

# Network Services Deployment - Compressor & Grayscaler

This repository documents the steps to build, load, deploy, undeploy, and monitor two network services: **compressor** and **grayscaler** using Docker, containerd, Helm, and a local deployment API.

---

## Prerequisites

Ensure the following tools are installed and configured:

- Docker
- containerd (with the `k8s.io` namespace)
- Kubernetes cluster
- Helm
- curl
- Deployment server running at `http://localhost:8090`

---

## Directory Structure

Navigate to the respective service directories before running the commands:

- **Compressor**: `network services -> compressor`
- **Grayscaler**: `network services -> grayscaler`

---

## 1. Build and Save Docker Images

### Compressor

```bash
sudo docker build -t compressor:offline .
sudo docker save compressor:offline -o compressor.tar
sudo ctr -n k8s.io images import compressor.tar
sudo ctr -n k8s.io images ls | grep compressor

---
