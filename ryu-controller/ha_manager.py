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
        # election.run() calls become_leader() when this node wins, then BLOCKS
        # inside become_leader() until we explicitly return from it.
        # When become_leader() returns, election.run() automatically re-enters election.
        while True:
            try:
                self.election.run(self.become_leader)
            except Exception as e:
                log.error(f"Election error: {e}. Reconnecting in 5s...")
                time.sleep(5)

    def become_leader(self):
        """
        This function is called when this instance wins the election[cite: 40].
        We must block here (not return) while we want to stay master.
        """
        log.info("--- I am now the MASTER controller ---")
        self.is_leader = True
        # Tell the Ryu app it's now master
        if hasattr(self.ryu_app, 'set_master_role'):
            self.ryu_app.set_master_role(is_master=True)
        
        # Block here to hold leadership. Monitor ZK connection health.
        try:
            while self.zk.connected:
                time.sleep(1)
        except Exception as e:
            log.error(f"Leadership monitoring error: {e}")
        
        # If we exit this function, we've lost leadership
        log.info("--- Lost leadership, transitioning to SLAVE ---")
        self.is_leader = False
        if hasattr(self.ryu_app, 'set_master_role'):
            self.ryu_app.set_master_role(is_master=False)

    def stop(self):
        if self.election:
            self.election.cancel()  # Cleanly leave election
        if self.zk:
            self.zk.stop()


