# k8s-service-dashboard

Simple web dashboard for externally exposed k8s services.

The Flask app runs on port 8080 and displays a dashboard of external (LoadBalancer/NodePort) Kubernetes services.

## Project Structure

- `code/app.py`: Main Flask application 
- `code/requirements.txt`: Python dependencies (flask, kubernetes)
- `code/templates/index.html`: HTML template 
- `install_service_dashboard.sh`: Script to install as systemd service (run as root)
- `uninstall_service_dashboard.sh`: Script to uninstall

## Installation

1. Run as root: `sudo ./install_service_dashboard.sh`

This installs the service, sets up a virtual environment in /opt/k8s-service-dashboard, and starts the systemd service.

## Usage

Access the dashboard at http://<server-ip>/ 

The app auto-refreshes the list of external services every 5 minutes.

## Uninstallation

Run as root: `sudo ./uninstall_service_dashboard.sh`

This stops and removes the systemd service and deletes the installation directory.
