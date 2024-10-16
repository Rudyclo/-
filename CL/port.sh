#!/bin/bash

PORTS_LOGFILE="/home/CL/ncl/ports.log"
SERVER_URL="http://192.168.56.1:5000/receive-data"
SCRIPT_ID="Port.S"  # 적절한 script_id로 변경

current_time() {
    echo $(date +"%Y-%m-%d %H:%M:%S")
}

# 닫혀 있어야 하는 포트 목록
CLOSED_PORTS=(23 21 3389 445 2049 22 3306 5672 11211)

function get_open_ports() {
    ss -tuln | awk 'NR>1 {print $5}' | cut -d: -f2 | sort -n | uniq
    ss -tuln | awk 'NR>1 {print $5}' | cut -d: -f2 | sort -n | uniq >> $PORTS_LOGFILE
}

# 닫혀 있어야 하는 포트가 열려 있는지 확인하는 함수
function check_ports() {
    local open_ports
    open_ports=$(get_open_ports)
    for port in "${CLOSED_PORTS[@]}"; do
        if echo "$open_ports" | grep -q "^$port$"; then
            echo "Port $port is open but should be closed."
            return 1
        fi
    done
    echo "All restricted ports are closed."
    return 0
}

# 서버로 상태 전송하는 함수
send_status() {
    local script_id=$1
    local status_value=$2
    local data=$(jq -n --arg id "$script_id" --arg status "$status_value" '{id: $id, status: $status}')
    local response=$(curl -s -w "%{http_code}" -o /dev/null -X POST -H "Content-Type: application/json" -d "$data" "$SERVER_URL")
}

while true; do
    # 포트 상태를 확인하고 결과 출력
    check_ports
    if [ $? -eq 0 ]; then
        send_status $SCRIPT_ID 0
    else
        send_status $SCRIPT_ID 1
    fi

    > $PORTS_LOGFILE

    sleep 30
done

