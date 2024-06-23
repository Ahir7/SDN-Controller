import logging
from sklearn.ensemble import IsolationForest
import numpy as np
import requests
import time
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

API_URL = os.environ.get("API_URL", "http://fastapi-api:8000")
API_ENDPOINT = f"{API_URL}/api/v1/policies"


class MLAnalyticsService:
    def __init__(self):
        # Initialize Isolation Forest model [cite: 239]
        self.model = IsolationForest(contamination=0.1)
        self.is_trained = False
        self.mitigated_ips = set()

    def train_model(self):
        """
        Train the model on a 'golden' dataset of normal traffic[cite: 243].
        """
        log.info("Training Isolation Forest model on baseline data...")
        # Placeholder for normal traffic features
        normal_traffic = np.random.randn(1000, 5) # [src_port, dst_port, protocol, packets, bytes]
        self.model.fit(normal_traffic)
        self.is_trained = True
        log.info("Model training complete.")

    def analyze_traffic_stream(self):
        """
        Simulate analyzing a live stream of sFlow features.
        """
        log.info("Starting real-time traffic analysis...")
        while True:
            if not self.is_trained:
                time.sleep(1)
                continue
            
            # Simulate receiving a new flow feature vector
            # This would come from the telemetry-collector [cite: 241]
            
            # 1. A normal flow
            normal_flow = np.random.randn(1, 5)
            _ = self.model.predict(normal_flow)
            
            # 2. An anomalous (DDoS) flow
            # This flow is statistically different [cite: 237]
            anomalous_flow_data = [[12345, 80, 6, 10000, 5000000]]
            anomalous_flow_vector = np.array(anomalous_flow_data)
            anomalous_src_ip = "1.2.3.4" # The attacker IP
            
            score_anomaly = self.model.predict(anomalous_flow_vector)
            
            if score_anomaly[0] == -1: # -1 indicates an anomaly [cite: 245]
                log.warning(f"Anomaly detected! Source IP: {anomalous_src_ip}")
                if anomalous_src_ip not in self.mitigated_ips:
                    self.trigger_mitigation(anomalous_src_ip)
            
            time.sleep(5)

    def trigger_mitigation(self, attacker_ip):
        """
        This is the "closed-loop" feedback.
        The ML service acts as a client to its own IBN API[cite: 247, 251].
        """
        log.info(f"Triggering automated mitigation for {attacker_ip}...")
        
        # This JSON object is the "intent" to block the attacker [cite: 255-262]
        mitigation_policy = {
            "name": f"ML-DDoS-Mitigation-{attacker_ip}",
            "priority": 65000, # Highest priority
            "source": {
                "ip_block": f"{attacker_ip}/32"
            },
            "destination": {
                "ip_block": "0.0.0.0/0"
            },
            "action": "DENY",
            "status": "ENABLED"
        }
        
        try:
            response = requests.post(API_ENDPOINT, json=mitigation_policy)
            if response.status_code == 201:
                log.info(f"Successfully installed DENY policy for {attacker_ip}.")
                self.mitigated_ips.add(attacker_ip)
            else:
                log.error(f"Failed to install policy: {response.text}")
        except Exception as e:
            log.error(f"Error calling API: {e}")


if __name__ == "__main__":
    service = MLAnalyticsService()
    service.train_model()
    service.analyze_traffic_stream()

