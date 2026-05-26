#!/bin/bash

# ============================================================================
# Smart Grid Kafka Topics Initialization
# ============================================================================
# This script creates all Kafka topics required for the pipeline.
#
# ============================================================================

echo "=========================================="
echo "  Smart Grid Kafka Topic Setup"
echo "=========================================="

echo "Waiting for Kafka brokers to form cluster..."
sleep 5

# --------------------------------------------------------------------------
# Bootstrap Servers
# --------------------------------------------------------------------------
# Use INTERNAL listeners (19092/19093/19094) because this script runs
# inside the Docker network. EXTERNAL ports (9092/9093/9094) are reserved
# for host-machine access only and should NOT be used between containers.
# --------------------------------------------------------------------------
BOOTSTRAP="kafka1:19092,kafka2:19093,kafka3:19094"

# ============================================================================
# Topic 1: Clean Smart Grid Events
# ============================================================================
# Partitions: 3 (distributed across 3 brokers for parallel processing)
# Replication: 3 (each partition replicated on all 3 brokers for HA)
# ============================================================================
kafka-topics --create \
  --topic smartgrid-clean \
  --partitions 3 \
  --replication-factor 3 \
  --bootstrap-server ${BOOTSTRAP} \
  --if-not-exists

echo "✅ Created topic: smartgrid-clean"

# ============================================================================
# Topic 2: Dead Letter Queue
# ============================================================================
# Partitions: 1 (sequential order matters for failed/error records)
# Replication: 3 (durability across all 3 brokers)
# ============================================================================
kafka-topics --create \
  --topic smartgrid-dlq \
  --partitions 1 \
  --replication-factor 3 \
  --bootstrap-server ${BOOTSTRAP} \
  --if-not-exists

echo "✅ Created topic: smartgrid-dlq"

# ============================================================================
# List All Topics
# ============================================================================

echo ""
echo "=========================================="
echo "  Available Kafka Topics"
echo "=========================================="

kafka-topics \
  --list \
  --bootstrap-server ${BOOTSTRAP}

echo ""
echo "Kafka topic initialization completed."