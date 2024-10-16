#!/bin/bash

# 서버 URL 및 스크립트 ID
SERVER_URL="http://192.168.56.1:5000/receive-data"
SCRIPT_ID="FBD"  # 적절한 script_id로 변경

send_status() {
    local script_id=$1
    local status_value=$2
    local data=$(jq -n --arg id "$script_id" --arg status "$status_value" '{id: $id, status: $status}')
    local response=$(curl -s -w "%{http_code}" -o /dev/null -X POST -H "Content-Type: application/json" -d "$data" "$SERVER_URL")
}

# 시스템 파일 변경 탐지 함수
detect_file_changes() {
    # 감시할 중요한 파일 목록
    FILES_TO_MONITOR=("/etc/passwd" "/etc/shadow" "/etc/hosts" "/etc/ssh/sshd_config")
    
    # 상태 유지 시간 설정 (초)
    ALERT_DURATION=60
    
    for FILE in "${FILES_TO_MONITOR[@]}"; do
        if [ -f "$FILE" ]; then
            CURRENT_CHECKSUM=$(md5sum "$FILE" | awk '{print $1}')
            PREVIOUS_CHECKSUM_FILE="/var/log/$(basename "$FILE").md5"

            if [ -f "$PREVIOUS_CHECKSUM_FILE" ]; then
                PREVIOUS_CHECKSUM=$(cat "$PREVIOUS_CHECKSUM_FILE")
                if [ "$CURRENT_CHECKSUM" != "$PREVIOUS_CHECKSUM" ]; then
                    echo "[ALERT] Change detected in $FILE!"
                    send_status $SCRIPT_ID 1
                    
                    # 변경 탐지 후 ALERT_DURATION 동안 상태를 유지
                    END_TIME=$(( $(date +%s) + ALERT_DURATION ))
                    while [ $(date +%s) -lt $END_TIME ]; do
                        send_status $SCRIPT_ID 1
                        sleep 5
                    done
                else
                    send_status $SCRIPT_ID 0
                fi
            fi

            echo "$CURRENT_CHECKSUM" > "$PREVIOUS_CHECKSUM_FILE"
        fi
    done
}

# 로그 파일 설정
LOG_FILE="/backdoor_detection.log"
exec > >(tee -a $LOG_FILE) 2>&1

# 탐지 루프
while true; do
    detect_file_changes
    sleep 30 # 5분마다 체크
done
