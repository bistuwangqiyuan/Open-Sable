#!/bin/bash

# System Check Script

timestamp=$(date '+%Y-%m-%d %H:%M:%S')
log_file="system_check_$(date +%Y%m%d).log"

echo "[$timestamp] Starting system check" >> "$log_file"

echo "--- DISK SPACE ---" >> "$log_file"
df -h >> "$log_file"
echo "" >> "$log_file"

# CPU and Memory
echo "--- CPU & MEMORY ---" >> "$log_file"
top -b -n 1 | awk '/^%Cpu/{print}' >> "$log_file"
free -h >> "$log_file"
echo "" >> "$log_file"

# Services
echo "--- SERVICES ---" >> "$log_file"
services=$(systemctl list-units --type=service)
echo "" >> "$log_file"

# Logs
echo "--- LOGS ---" >> "$log_file"
grep -i 'error' /var/log/*.log >> "$log_file"

echo "[$timestamp] System check complete" >> "$log_file"