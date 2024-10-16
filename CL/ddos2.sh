#!/bin/bash

# 감지할 네트워크 인터페이스
INTERFACE="ens33"

# 감지 임계값 설정
THRESHOLD=1000

# 모니터링 시간 간격 (초)
INTERVAL=15

# 서버 URL 및 스크립트 ID
SERVER_URL="http://192.168.56.1:5000/receive-data"
SCRIPT_ID="DDoS2"  # 적절한 script_id로 변경

# 서버로 상태 전송하는 함수
send_status() {
    local script_id=$1
    local status_value=$2
    local data=$(jq -n --arg id "$script_id" --arg status "$status_value" '{id: $id, status: $status}')
    local response=$(curl -s -w "%{http_code}" -o /dev/null -X POST -H "Content-Type: application/json" -d "$data" "$SERVER_URL")
}

while true; do
    # 현재 시간과 패킷 수 확인
    START_TIME=$(date +%s)
    START_PACKETS=$(cat /sys/class/net/$INTERFACE/statistics/rx_packets)

    # INTERVAL 만큼 대기
    sleep $INTERVAL

    # 종료 시간과 패킷 수 확인
    END_TIME=$(date +%s)
    END_PACKETS=$(cat /sys/class/net/$INTERFACE/statistics/rx_packets)

    # 패킷 수 차이 계산
    PACKET_DIFF=$((END_PACKETS - START_PACKETS))

    # 네트워크 연결 수 확인
    CONNECTION_COUNT=$(ss -tan | grep ESTAB | wc -l)

    # 연결된 IP 주소 확인
    CONNECTED_IPS=$(ss -tan | grep ESTAB | awk '{print $5}' | cut -d':' -f1 | sort | uniq)
    
    # DDoS 공격 감지 여부 확인
    if [ "$PACKET_DIFF" -gt "$THRESHOLD" ]; then
        send_status $SCRIPT_ID 1
    else
        send_status $SCRIPT_ID 0
    fi
done
