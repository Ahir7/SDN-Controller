from kazoo.client import KazooClient
from kazoo.recipe.election import Election
import logging
import time
import os


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Allow configuration of an ensemble (e.g., "zookeeper-1:2181,zookeeper-2:2181")
ZK_HOSTS = os.environ.get("ZK_HOSTS", "zookeeper:2181")
ELECTION_PATH = '/sdn/controller_election'


class ZKLeaderElection:
    def __init__(self, ryu_app):
        self.ryu_app = ryu_app
        self.zk = KazooClient(hosts=ZK_HOSTS)
        self.election = None
        self.is_leader = False

    def start(self):
        self.zk.start()
        log.info(f"Connecting to Zookeeper at {ZK_HOSTS}...")
        self.election = Election(self.zk, ELECTION_PATH)
        # Start the election process.
        # The election.run() method will block until this instance
        # is elected leader[cite: 39].
        self.election.run(self.become_leader)

    def become_leader(self):
        """
        This function is called when this instance wins the election[cite: 40].
        """
        log.info("--- I am now the MASTER controller ---")
        self.is_leader = True
        # Tell the Ryu app it's now master
        if hasattr(self.ryu_app, 'set_master_role'):
            self.ryu_app.set_master_role(is_master=True)
        
        # Keep running logic while master
        while True:
            try:
                # Check if still leader (best-effort; depends on Kazoo internals)
                if hasattr(self.election, 'is_leader') and not self.election.is_leader:
                    break
                time.sleep(1)
            except Exception:
                break
        
        # If loop breaks, we are no longer leader
        self.lose_leadership()

    def lose_leadership(self):
        """
        Called when election is lost or ZK session is lost[cite: 44].
        """
        log.info("--- I am now a SLAVE controller ---")
        self.is_leader = False
        if hasattr(self.ryu_app, 'set_master_role'):
            self.ryu_app.set_master_role(is_master=False)
        
        # Re-run the election to get back in line
        self.election.run(self.become_leader)

    def stop(self):
        self.election.cancel()  # Cleanly leave election
        self.zk.stop()


