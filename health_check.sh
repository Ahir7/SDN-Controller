#!/bin/bash
# Health check script to verify all services are running and integrated properly

echo "=== SDN Controller Stack Health Check ==="
echo

# Check if docker compose is running
if ! docker compose ps > /dev/null 2>&1; then
    echo "❌ Docker Compose not found or project not running"
    echo "Run: docker compose up -d --build"
    exit 1
fi

echo "✓ Docker Compose is available"
echo

# Check service status
echo "Checking service status..."
services=("zookeeper" "postgres-db" "fastapi-api" "ryu-controller" "ryu-controller-2" "telemetry-collector" "ml-analytics" "prometheus" "grafana")

for service in "${services[@]}"; do
    status=$(docker compose ps --filter "name=$service" --format "{{.Status}}" 2>/dev/null | head -1)
    if echo "$status" | grep -q "Up"; then
        echo "✓ $service: Running"
    else
        echo "❌ $service: Not running or unhealthy"
    fi
done

echo
echo "=== Service Endpoints ==="
echo "FastAPI API: http://localhost:8000/docs"
echo "Prometheus: http://localhost:9090"
echo "Grafana: http://localhost:3000"
echo "PostgreSQL: localhost:5432"
echo "Zookeeper: localhost:2181"
echo

# Test FastAPI health
echo "Testing FastAPI API..."
if curl -s http://localhost:8000/api/v1/policies > /dev/null 2>&1; then
    echo "✓ FastAPI API is responding"
else
    echo "❌ FastAPI API not responding"
fi

# Test Prometheus
echo "Testing Prometheus..."
if curl -s http://localhost:9090/-/ready > /dev/null 2>&1; then
    echo "✓ Prometheus is responding"
else
    echo "❌ Prometheus not responding"
fi

echo
echo "=== Recent Logs (last 10 lines per service) ==="
for service in "${services[@]}"; do
    echo
    echo "--- $service ---"
    docker compose logs --tail=10 "$service" 2>/dev/null | tail -5
done

echo
echo "=== Health Check Complete ==="

