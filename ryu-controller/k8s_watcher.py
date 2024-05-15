from kubernetes import config, client, watch
from ryu.base import app_manager
from ryu.controller import event
from ryu.lib import hub
import logging
import time


log = logging.getLogger(__name__)


# --- Custom Ryu Events ---
# [cite_start]These bridge the K8s watcher thread to the Ryu event loop [cite: 151]
class EventK8sPodUpdate(event.EventBase):
    def __init__(self, pod_event_type, pod_ip, labels, node):
        super(EventK8sPodUpdate, self).__init__()
        self.event_type = pod_event_type  # 'ADDED', 'MODIFIED', 'DELETED'
        self.pod_ip = pod_ip
        self.labels = labels
        self.node = node


class K8sWatcher:
    def __init__(self, ryu_app):
        self.ryu_app = ryu_app
        try:
            # Load in-cluster config when running as a Pod [cite: 128]
            config.load_incluster_config()
            log.info("Loaded in-cluster Kubernetes config.")
        except config.ConfigException:
            # Load kube_config for local development [cite: 129]
            config.load_kube_config()
            log.info("Loaded local kube_config.")
        
        self.v1 = client.CoreV1Api()
        self.watcher = watch.Watch()

    def start(self):
        log.info("Starting Kubernetes Pod event watcher...")
        # Run the watch loop in a separate green thread
        hub.spawn(self._watch_pods)

    def _watch_pods(self):
        """
        Watch stream for K8s Pod events[cite: 134].
        """
        while True:
            try:
                stream = self.watcher.stream(self.v1.list_pod_for_all_namespaces)
                for event in stream:
                    pod = event['object']
                    event_type = event['type']  # ADDED, MODIFIED, DELETED
                    
                    if not pod.status.pod_ip:
                        continue  # Skip pods without an IP
                        
                    pod_ip = pod.status.pod_ip
                    labels = pod.metadata.labels
                    node = pod.spec.node_name
                    
                    if labels:
                        log.info(f"K8s Event: {event_type} Pod {pod_ip} with labels {labels}")
                        # Emit a custom Ryu event to the main app [cite: 153]
                        custom_event = EventK8sPodUpdate(
                            event_type, pod_ip, labels, node
                        )
                        self.ryu_app.send_event_to_observers(custom_event)
                        
            except Exception as e:
                log.error(f"K8s watch stream error: {e}. Reconnecting...")
                time.sleep(5)


