from flask import Flask, render_template
import kubernetes.client
from kubernetes.client.rest import ApiException
import os
import time
from datetime import datetime
import threading

app = Flask(__name__)

# Global cache
service_links = []
last_updated = "Never"

def load_kube_config():
    """Auto-detect and load kubeconfig for k3s, standard Kubernetes, or fallback"""
    possible_configs = [
        "/etc/rancher/k3s/k3s.yaml",          # k3s 
        "/etc/kubernetes/admin.conf",         # Standard kubeadm / many distro installs
        os.path.expanduser("~/.kube/config"), # User kubeconfig (common for dev/root access)
    ]

    loaded = False
    for config_path in possible_configs:
        if os.path.exists(config_path):
            try:
                kubernetes.config.load_kube_config(config_file=config_path)
                print(f"Successfully loaded kubeconfig from: {config_path}")
                loaded = True
                break
            except Exception as e:
                print(f"Failed to load {config_path}: {e}")
                # Continue trying others

    if not loaded:
        raise FileNotFoundError(
            "No valid kubeconfig found. Checked:\n" +
            "\n".join(f"  - {p} (missing or invalid)" for p in possible_configs) +
            "\n\nEnsure one of these files exists and is readable by root, "
            "or place a valid kubeconfig in one of these locations."
        )

def collect_external_services():
    global service_links, last_updated

    v1 = kubernetes.client.CoreV1Api()

    try:
        services = v1.list_service_for_all_namespaces(watch=False)
    except ApiException as e:
        print(f"Kubernetes API error: {e}")
        return

    found = []

    for svc in services.items:
        if svc.spec.type not in ("LoadBalancer", "NodePort"):
            continue

        namespace = svc.metadata.namespace
        name = svc.metadata.name

        # Prefer LoadBalancer external IP/hostname first
        external_addrs = []
        if svc.status.load_balancer and svc.status.load_balancer.ingress:
            for ing in svc.status.load_balancer.ingress:
                if ing.hostname:
                    external_addrs.append(ing.hostname)
                elif ing.ip:
                    external_addrs.append(ing.ip)

        # Fallback to NodePort (showing nodePort only - real usage needs node IPs)
        if not external_addrs and svc.spec.type == "NodePort":
            for port in svc.spec.ports or []:
                if port.node_port:
                    external_addrs.append(f"node-ip:{port.node_port}")

        for addr in external_addrs:
            proto = "https" if "443" in str(addr) else "http"
            port_str = ""
            host = addr

            # Clean up address format
            if ":" in addr and not addr.startswith("node-ip:"):
                host, port_part = addr.split(":", 1)
                if port_part not in ("80", "443"):
                    port_str = f":{port_part}"

            # Try to find reasonable target port
            target_port = 80
            if svc.spec.ports:
                for p in svc.spec.ports:
                    if p.port in (80, 443):
                        target_port = p.port
                        break
                    try:
                        if p.target_port:
                            target_port = int(p.target_port)
                    except:
                        pass

            url = f"{proto}://{host}{port_str}"
            if target_port not in (80, 443):
                url += f":{target_port}"

            found.append({
                "namespace": namespace,
                "service": name,
                "url": url,
                "type": svc.spec.type,
                "external_addr": addr
            })

    service_links = sorted(found, key=lambda x: x["namespace"].lower())
    last_updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def background_refresh():
    """Refresh every 5 minutes"""
    while True:
        try:
            collect_external_services()
        except Exception as e:
            print(f"Refresh error: {e}")
        time.sleep(300)

@app.route("/")
def index():
    return render_template(
        "index.html",
        services=service_links,
        last_updated=last_updated,
        count=len(service_links)
    )

if __name__ == "__main__":
    load_kube_config()

    # Start background updater thread
    threading.Thread(target=background_refresh, daemon=True).start()

    # Initial collection
    collect_external_services()

    print("Starting Kubernetes Services Dashboard on http://0.0.0.0:80")
    app.run(
        host="0.0.0.0",
        port=80,
        debug=False,
        threaded=True          # Better concurrency for low-traffic internal use
    )