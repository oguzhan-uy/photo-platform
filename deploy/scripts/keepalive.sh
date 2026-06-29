#!/usr/bin/env bash
# Oracle Cloud Always Free idle-reclamation prevention.
#
# Oracle may reclaim free tier instances that show no CPU or disk activity
# for 7 consecutive days. This script writes a small file every 30 minutes
# to keep disk activity visible to the platform.
#
# Cron entry (set by cloud-init, runs as deploy user):
#   */30 * * * * /opt/photo/scripts/keepalive.sh
#
# CPU-cost: effectively zero. Disk-cost: one inode write every 30 min.

echo "$(date -u) keepalive" > /var/run/photo-keepalive
