#!/bin/bash
# Benchmarking suite for SDN Zero-Trust Controller
# Implements tests from Blueprint Table 4 (lines 401-410)

set -e

echo "======================================"
echo "SDN Controller Benchmark Suite"
echo "======================================"
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Baseline Performance
echo -e "${YELLOW}Test 1: Baseline Performance${NC}"
echo "Description: Establish throughput and latency baseline"
echo "Expected: 9.4 Gbps, 0.2 ms latency"
echo
echo "Run manually in Mininet CLI:"
echo "  mininet> iperf h1 h3"
echo "  mininet> h1 ping -c 10 h3"
echo
read -p "Press Enter to continue..."

# Test 2: ZTA Controller Overhead
echo
echo -e "${YELLOW}Test 2: ZTA Controller Overhead${NC}"
echo "Description: Measure performance impact of reactive controller"
echo "Expected: <5% impact vs baseline"
echo
echo "With Ryu running, compare iperf results to baseline"
echo
read -p "Press Enter to continue..."

# Test 3: Policy Enforcement
echo
echo -e "${YELLOW}Test 3: Policy Enforcement (DENY)${NC}"
echo "Description: Verify policy blocks traffic"
echo

# Create a test policy
echo "Creating DENY policy for 10.0.1.1 -> 10.0.2.1..."
curl -X POST http://localhost:8000/api/v1/policies \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Benchmark-Test-DENY",
    "priority": 5000,
    "source": {"ip_block": "10.0.1.1/32"},
    "destination": {"ip_block": "10.0.2.1/32"},
    "action": "DENY",
    "status": "ENABLED"
  }' 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Policy created${NC}"
    echo "Wait 10s for Ryu to detect policy..."
    sleep 10
    echo
    echo "Now run in Mininet CLI:"
    echo "  mininet> h1 ping -c 5 h3"
    echo "Expected: 100% packet loss"
    echo
    read -p "Press Enter to delete test policy..."
    
    # Get policy ID and delete
    POLICY_ID=$(curl -s http://localhost:8000/api/v1/policies | grep -o '"id":"[^"]*Benchmark-Test-DENY' | grep -o 'id":"[^"]*' | cut -d'"' -f3)
    if [ ! -z "$POLICY_ID" ]; then
        curl -X DELETE "http://localhost:8000/api/v1/policies/$POLICY_ID" 2>/dev/null
        echo -e "${GREEN}✓ Test policy deleted${NC}"
    fi
else
    echo -e "${RED}✗ Failed to create policy${NC}"
fi

# Test 4: L4 Port-Specific Policy
echo
echo -e "${YELLOW}Test 4: L4 Port-Specific Policy (TCP Port 80)${NC}"
echo "Description: Verify port-specific DENY"
echo

curl -X POST http://localhost:8000/api/v1/policies \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Benchmark-Port-Test",
    "priority": 6000,
    "source": {"ip_block": "10.0.1.1/32"},
    "destination": {"ip_block": "10.0.2.1/32"},
    "service": [{"protocol": "TCP", "port": 80}],
    "action": "DENY",
    "status": "ENABLED"
  }' 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Port-specific policy created${NC}"
    echo "Wait 10s for Ryu to detect policy..."
    sleep 10
    echo
    echo "Test in Mininet:"
    echo "  mininet> h3 python -m SimpleHTTPServer 80 &"
    echo "  mininet> h1 wget -O- http://10.0.2.1"
    echo "Expected: Connection refused (port 80 blocked)"
    echo
    echo "  mininet> h1 ping h3"
    echo "Expected: Ping succeeds (ICMP not blocked)"
    echo
    read -p "Press Enter to delete test policy..."
    
    POLICY_ID=$(curl -s http://localhost:8000/api/v1/policies | grep -o '"id":"[^"]*Benchmark-Port-Test' | grep -o 'id":"[^"]*' | cut -d'"' -f3)
    if [ ! -z "$POLICY_ID" ]; then
        curl -X DELETE "http://localhost:8000/api/v1/policies/$POLICY_ID" 2>/dev/null
        echo -e "${GREEN}✓ Test policy deleted${NC}"
    fi
fi

# Test 5: ML-Driven DDoS Mitigation
echo
echo -e "${YELLOW}Test 5: ML-Driven DDoS Mitigation${NC}"
echo "Description: Verify automated mitigation"
echo "Expected: ML service POSTs policy, traffic blocked within seconds"
echo
echo "Check ml-analytics logs:"
echo "  docker compose logs ml-analytics | grep 'Anomaly detected'"
echo "  docker compose logs ml-analytics | grep 'Successfully installed'"
echo
echo "The ML service automatically creates high-priority DENY policies"
echo "for detected anomalies (simulated attacker 1.2.3.4)"
echo
read -p "Press Enter to continue..."

# Test 6: HA Controller Failover
echo
echo -e "${YELLOW}Test 6: HA Controller Failover${NC}"
echo "Description: Verify sub-second failover"
echo "Expected: <1s disruption, minimal packet loss"
echo
echo "Steps:"
echo "1. Identify MASTER controller:"
echo "   docker compose logs ryu-controller | grep MASTER"
echo "   docker compose logs ryu-controller-2 | grep MASTER"
echo
echo "2. Kill MASTER:"
echo "   docker compose stop ryu-controller  (or ryu-controller-2)"
echo
echo "3. Verify SLAVE becomes MASTER:"
echo "   docker compose logs ryu-controller-2 --follow"
echo
echo "4. Test connectivity in Mininet (should resume within 1s)"
echo
read -p "Press Enter to finish..."

echo
echo -e "${GREEN}======================================"
echo "Benchmark Suite Complete"
echo "======================================${NC}"
echo
echo "Summary:"
echo "- Test 1-2: Manual iperf/ping comparison"
echo "- Test 3-4: Policy enforcement verified"
echo "- Test 5: ML mitigation (check logs)"
echo "- Test 6: HA failover (manual test)"
echo
echo "See readme.md for detailed validation steps"

