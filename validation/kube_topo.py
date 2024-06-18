from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel


def create_k8s_topology():
    """
    Creates a simple Mininet topology to emulate K8s nodes.
    - 2 OVS switches (representing 2 K8s worker nodes) [cite: 302]
    - 2 hosts per switch (representing Pods) [cite: 303]
    """
    net = Mininet(
        controller=None,
        switch=OVSKernelSwitch,
        autoSetMacs=True
    )

    print("Adding remote controllers (pointing to Docker)...")
    # Point to the Ryu controllers running in Docker [cite: 305]
    c0 = net.addController(
        'c0',
        controller=RemoteController,
        ip='127.0.0.1',  # Docker host IP
        port=6653        # First Ryu controller
    )
    c1 = net.addController(
        'c1',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6654        # Second Ryu controller instance
    )

    print("Adding switches (K8s Nodes)...")
    s1 = net.addSwitch('s1')  # Node 1
    s2 = net.addSwitch('s2')  # Node 2

    print("Adding hosts (Pods)...")
    # Pods on Node 1
    h1 = net.addHost('h1', ip='10.0.1.1/24')
    h2 = net.addHost('h2', ip='10.0.1.2/24')
    
    # Pods on Node 2
    h3 = net.addHost('h3', ip='10.0.2.1/24')
    h4 = net.addHost('h4', ip='10.0.2.2/24')

    print("Creating links...")
    # Pods to switches
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s2)
    net.addLink(h4, s2)
    
    # Switches together
    net.addLink(s1, s2)

    print("Starting network...")
    net.build()
    c0.start()
    c1.start()
    # Start switches with both controllers to emulate multi-controller OVS
    s1.start([c0, c1])
    s2.start([c0, c1])

    print("Network is running. Type 'h1 ping h3' to test.")
    print("Run Test C (Policy Enforcement)[cite: 319]:")
    print("1. In Mininet: h1 ping h3 (should work)")
    print("2. In another terminal: curl -X POST http://localhost:8000/api/v1/policies "
          "-H 'Content-Type: application/json' -d '...' (to DENY 10.0.1.1 to 10.0.2.1)")
    print("3. In Mininet: h1 ping h3 (should fail)")
    
    CLI(net)

    print("Stopping network...")
    net.stop()


if __name__ == '__main__':
    # [cite_start]This Mininet script emulates the K8s node topology [cite: 301]
    # and connects to our remote Ryu controller cluster.
    setLogLevel('info')
    create_k8s_topology()


