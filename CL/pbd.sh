#!/bin/bash

# 서버 URL 및 스크립트 ID
SERVER_URL="http://192.168.56.1:5000/receive-data"
SCRIPT_ID="PBD"  # 적절한 script_id로 변경

send_status() {
    local script_id=$1
    local status_value=$2
    local data=$(jq -n --arg id "$script_id" --arg status "$status_value" '{id: $id, status: $status}')
    local response=$(curl -s -w "%{http_code}" -o /dev/null -X POST -H "Content-Type: application/json" -d "$data" "$SERVER_URL")
}

# 비정상적인 프로세스 탐지 함수
check_unusual_processes() {
    ps aux > /process_list.log

    # 비정상적인 프로세스 패턴을 정의 (예: 알려진 백도어 프로세스 이름)
    UNUSUAL_PROCESSES=$(grep -E "(netcat|telnetd|bash -i|python -c)" /process_list.log)

    if [ -n "$UNUSUAL_PROCESSES" ]; then
        send_status $SCRIPT_ID 1
    else
        send_status $SCRIPT_ID 0
    fi
}

# 로그 파일 설정
LOG_FILE="root/Downloads/CL/backdoor_detection.log"
exec > >(tee -a $LOG_FILE) 2>&1

# 탐지 루프
while true; do
    check_unusual_processes
    sleep 30 # 5분마다 체크
done
