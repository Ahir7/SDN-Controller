import logging
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4
from ryu.lib import hub

# Custom modules
from ha_manager import ZKLeaderElection
from k8s_watcher import K8sWatcher, EventK8sPodUpdate

# DB imports (to read policies)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://sdn_user:sdn_password@postgres-db/sdn_policy_db")

# Cookie used to tag ZeroTrustController-installed flow rules so they can be
# safely removed during reconciliation without touching CNI/base flows.
ZT_COOKIE = 0xDEADBEEF


class ZeroTrustController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _EVENTS = [EventK8sPodUpdate]  # Register our custom event [cite: 154]

    def __init__(self, *args, **kwargs):
        super(ZeroTrustController, self).__init__(*args, **kwargs)
        self.is_master = False
        self.datapaths = {}  # Connected OpenFlow switches
        
        # [cite_start]Internal state maps [cite: 131, 132]
        self.pod_label_map = {}  # { "10.1.1.5": {"app": "frontend", ...} }
        self.policy_map = {}     # { "policy_id": {...policy_obj...} }

        # Start HA Manager (leader election)
        self.ha_manager = ZKLeaderElection(self)
        hub.spawn(self.ha_manager.start)

        # Start K8s Watcher (Pod events -> custom Ryu events)
        self.k8s_watcher = K8sWatcher(self)
        hub.spawn(self.k8s_watcher.start)
        
        # Setup DB connection (policy source of truth)
        engine = create_engine(DATABASE_URL)
        self.DBSession = sessionmaker(bind=engine)

        # Start background policy watcher so new policies are picked up without restart
        hub.spawn(self._policy_watch_loop)
        
        self.logger.info("ZeroTrustController Initialized.")

    def set_master_role(self, is_master):
        """Callback from ha_manager."""
        self.is_master = is_master
        if is_master:
            # We are now Master. Tell all switches.
            self.logger.info("Setting role to OFPCR_ROLE_MASTER for all switches.")
            for dp in self.datapaths.values():
                self.send_role_request(dp, ofproto_v1_3.OFPCR_ROLE_MASTER)
            
            # [cite_start]Load policies from DB and reconcile state [cite: 73]
            self.load_policies_from_db()
            self.reconcile_all_flows()
        else:
            # We are now Slave.
            for dp in self.datapaths.values():
                self.send_role_request(dp, ofproto_v1_3.OFPCR_ROLE_SLAVE)

    def send_role_request(self, datapath, role):
        """
        [cite_start]Send OFPRoleRequest to a switch[cite: 41].
        """
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        msg = ofp_parser.OFPRoleRequest(datapath, role, 0)
        datapath.send_msg(msg)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Handle new switch connection.
        """
        dp = ev.msg.datapath
        self.datapaths[dp.id] = dp
        self.logger.info(f"Switch {dp.id} connected.")
        
        # Set the switch role based on our current HA state
        if self.is_master:
            self.send_role_request(dp, ofproto_v1_3.OFPCR_ROLE_MASTER)
        else:
            self.send_role_request(dp, ofproto_v1_3.OFPCR_ROLE_SLAVE)

        # Install the baseline, low-priority rule to send packets to the CNI
        # [cite_start]This is part of the "Priority Override" model [cite: 102]
        # We assume the CNI's rules are at priority 100.
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser
        match = ofp_parser.OFPMatch()
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_NORMAL)]  # "NORMAL" = CNI
        # Baseline rule should NOT use the ZT_COOKIE so that it is never
        # removed by our reconciliation cleanup.
        self.add_flow(dp, 1, match, actions, use_cookie=False)  # Priority 1 (lowest)

    def add_flow(self, datapath, priority, match, actions, use_cookie=True):
        """Helper to add a flow rule.

        If use_cookie is True, the rule is tagged so it can be removed safely
        during reconciliation without affecting CNI/base flows.
        """
        if not self.is_master:
            return  # Slaves don't install rules
            
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        if actions:
            inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        else:
            inst = []  # Empty instructions => DROP

        cookie = ZT_COOKIE if use_cookie else 0

        mod = ofp_parser.OFPFlowMod(
            datapath=datapath,
            cookie=cookie,
            priority=priority,
            match=match,
            instructions=inst
        )
        datapath.send_msg(mod)

    def clear_zt_flows(self):
        """Remove all previously installed Zero-Trust (ZT) flow rules.

        This uses the cookie tag to avoid touching CNI or other non-ZT flows.
        """
        for dp in self.datapaths.values():
            ofp = dp.ofproto
            ofp_parser = dp.ofproto_parser
            mod = ofp_parser.OFPFlowMod(
                datapath=dp,
                cookie=ZT_COOKIE,
                cookie_mask=0xFFFFFFFFFFFFFFFF,
                command=ofp.OFPFC_DELETE,
                out_port=ofp.OFPP_ANY,
                out_group=ofp.OFPG_ANY,
                match=ofp_parser.OFPMatch()
            )
            dp.send_msg(mod)

    def _policy_watch_loop(self):
        """Background loop to keep policy_map in sync with PostgreSQL.

        When this controller is Master, it periodically reloads policies
        from the database and reconciles flows to match the latest intent.
        """
        while True:
            try:
                if self.is_master:
                    self.load_policies_from_db()
                    self.reconcile_all_flows()
                # Sleep a short interval; tunable based on latency requirements.
                hub.sleep(5)
            except Exception as e:
                self.logger.error(f"Policy watch loop error: {e}")
                hub.sleep(5)

    # --- Policy and K8s Event Handling ---

    @set_ev_cls(EventK8sPodUpdate)
    def k8s_pod_update_handler(self, ev):
        """
        [cite_start]Handles the custom event from the K8s watcher[cite: 154].
        [cite_start]This is the start of the reconciliation loop[cite: 141].
        """
        if not self.is_master:
            return  # Slaves don't process logic
            
        self.logger.info(f"RECV custom event: {ev.event_type} Pod {ev.pod_ip}")
        
        if ev.event_type in ("ADDED", "MODIFIED"):
            self.pod_label_map[ev.pod_ip] = ev.labels
        elif ev.event_type == "DELETED":
            if ev.pod_ip in self.pod_label_map:
                del self.pod_label_map[ev.pod_ip]
        
        # Now that state is updated, reconcile flows
        self.reconcile_all_flows()

    def load_policies_from_db(self):
        """
        [cite_start]Load all policies from the PostgreSQL 'source of truth'[cite: 64, 73].
        """
        if not self.is_master:
            return
            
        self.logger.info("Loading policies from PostgreSQL...")
        session = self.DBSession()
        try:
            policies = session.query(PolicyDB).filter_by(status="ENABLED").all()
            self.policy_map = {p.id: p for p in policies}
            self.logger.info(f"Loaded {len(self.policy_map)} active policies.")
        except Exception as e:
            self.logger.error(f"Failed to load policies from DB: {e}")
        finally:
            session.close()

    def reconcile_all_flows(self):
        """
        This is the core reconciliation loop.
        [cite_start]It translates abstract policy (labels) into OpenFlow rules[cite: 125, 144].
        """
        if not self.is_master:
            return
            
        self.logger.info("--- Starting Policy Reconciliation ---")

        # Clear any previously-installed ZT flows so we can re-install from
        # the current policy_map without leaving stale rules behind.
        self.clear_zt_flows()
        
        for policy in self.policy_map.values():
            # Find all source and dest IPs that match the policy's label selectors
            source_ips = self.find_ips_from_selector(policy.source)
            dest_ips = self.find_ips_from_selector(policy.destination)
            
            if not source_ips or not dest_ips:
                continue  # No matching pods for this policy yet

            # [cite_start]Implement the "Priority Override" model [cite: 104, 111]
            # All our rules have high priority.
            priority = policy.priority
            
            # [cite_start]An empty action list means DROP [cite: 111]
            actions = []
            if policy.action == "ALLOW":
                # ALLOW rules are not implemented in this demo.
                self.logger.warning("ALLOW policies not yet implemented in this demo.")
                continue

            # Install DENY rules
            for src_ip in source_ips:
                for dst_ip in dest_ips:
                    match_fields = {
                        'eth_type': 0x0800,  # IPv4
                        'ipv4_src': src_ip,
                        'ipv4_dst': dst_ip
                    }
                    
                    # TODO: Add L4 (TCP/UDP port) matching from policy.service
                    
                    for dp in self.datapaths.values():
                        ofp_parser = dp.ofproto_parser
                        match = ofp_parser.OFPMatch(**match_fields)
                        # Security overlay rules are tagged with ZT_COOKIE so
                        # they can be safely removed during future reconciliations.
                        self.add_flow(dp, priority, match, actions, use_cookie=True)  # actions=[] means DROP
            
            self.logger.info(f"Installed DENY rules for policy: {policy.name}")

    def find_ips_from_selector(self, selector):
        """
        [cite_start]Finds Pod IPs that match a label selector[cite: 146].
        """
        ips = []
        if selector.get('ip_block'):
            ips.append(selector['ip_block'])
            
        if selector.get('label_selector'):
            sel = selector['label_selector']
            for ip, labels in self.pod_label_map.items():
                if all(item in labels.items() for item in sel.items()):
                    ips.append(ip)
        return list(set(ips))


# DB Model (minimal copy for zt_controller)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, JSON
Base = declarative_base()
class PolicyDB(Base):
    __tablename__ = "policies"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    priority = Column(Integer)
    source = Column(JSON)
    destination = Column(JSON)
    service = Column(JSON)
    action = Column(String)
    status = Column(String)

