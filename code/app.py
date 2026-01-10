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
        "/etc/rancher/k3s/k3s.yaml",          # k3s (most common)
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

    if not loaded:
        raise FileNotFoundError(
            "No valid kubeconfig found. Checked:\n" +
            "\n".join(f"  - {p} (missing or invalid)" for p in possible_configs)
        )

def collect_external_services():
    global service_links, last_updated

    v1 = kubernetes.client.CoreV1Api()

    # Collect node IPs (prefer ExternalIP if available)
    node_ips = set()
    try:
        nodes = v1.list_node()
        for node in nodes.items:
            for addr in node.status.addresses or []:
                if addr.address:
                    if addr.type == "ExternalIP":
                        node_ips.add(addr.address)
                    elif addr.type == "InternalIP":
                        node_ips.add(addr.address)
    except Exception as e:
        print(f"Error listing nodes: {e}")

    node_ips = sorted(node_ips)
    single_node = len(node_ips) == 1

    # Collect services
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
        ports = svc.spec.ports or []
        if not ports:
            continue

        for port_spec in ports:
            port_name = port_spec.name or ""
            service_port = port_spec.port
            node_port = port_spec.node_port

            display_name = name
            if len(ports) > 1 or port_name:
                display_name += f" ({port_name or service_port})"

            if svc.spec.type == "LoadBalancer":
                ingress_list = (svc.status.load_balancer.ingress or []) if svc.status.load_balancer else []
                if not ingress_list:
                    continue

                for ing in ingress_list:
                    host = ing.hostname or ing.ip
                    if not host:
                        continue

                    proto = "https" if str(service_port).endswith("443") else "http"
                    url = f"{proto}://{host}"
                    if service_port not in (80, 443):
                        url += f":{service_port}"

                    addr_display = host if service_port in (80, 443) else f"{host}:{service_port}"

                    found.append({
                        "namespace": namespace,
                        "service": display_name,
                        "url": url,
                        "type": "LoadBalancer",
                        "external_addr": addr_display
                    })

            elif svc.spec.type == "NodePort" and node_port:
                proto = "https" if str(node_port).endswith("443") else "http"
                url_base_template = f"{proto}://%s"
                addr_template = "%s" if node_port in (80, 443) else "%s:{node_port}"

                if node_ips:
                    for node_ip in node_ips:
                        url = url_base_template % node_ip
                        if node_port not in (80, 443):
                            url += f":{node_port}"

                        addr_display = addr_template % node_ip

                        service_display = display_name
                        if not single_node:
                            service_display += f" (via {node_ip})"

                        found.append({
                            "namespace": namespace,
                            "service": service_display,
                            "url": url,
                            "type": "NodePort",
                            "external_addr": addr_display
                        })
                else:
                    # Fallback placeholder
                    url = f"{proto}://<node-ip>:{node_port}" if node_port not in (80, 443) else f"{proto}://<node-ip>"
                    found.append({
                        "namespace": namespace,
                        "service": display_name,
                        "url": url,
                        "type": "NodePort",
                        "external_addr": f"<node-ip>:{node_port}"
                    })

    service_links = sorted(found, key=lambda x: (x["namespace"].lower(), x["service"].lower()))
    last_updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def background_refresh():
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

    threading.Thread(target=background_refresh, daemon=True).start()

    collect_external_services()

    # note for k3s port 80 is already in use by the load balancer
    port = int(os.environ.get("PORT", "8080"))
    print(f"Starting Kubernetes Services Dashboard on http://0.0.0.0:{port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True
    )