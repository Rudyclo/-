#!/bin/bash

# 모니터링할 네트워크 인터페이스 설정
INTERFACE="ens33"

# 트래픽 정보를 저장할 로그 파일 경로 설정
TRAFFIC_FILE="/home/CL/clog/ddos1_traffic.log"

# SYN 패킷을 저장할 로그 파일 경로 설정
SYN_FILE="/home/CL/clog/synips.log"

# 중복된 IP 주소를 저장할 로그 파일 경로 설정
THREE_SYN_FILE="/home/CL/3synips.log"

# 임계값
THRESHOLD=3

# 서버 URL 및 스크립트 ID
SERVER_URL="http://192.168.56.1:5000/receive-data"
SCRIPT_ID="DDoS1"  # 적절한 script_id로 변경

current_time() {
    echo $(date +"%Y-%m-%d %H:%M:%S")
}

# 서버로 상태 전송하는 함수
# 데이터 전송 함수
send_data() {
    local script_id=$1
    local status_value=$2
    local data=$(jq -n --arg id "$script_id" --arg status "$status_value" '{id: $id, status: $status}')
    local response=$(curl -s -w "%{http_code}" -o /dev/null -X POST -H "Content-Type: application/json" -d "$data" "$SERVER_URL")
}

# 초기 트래픽 데이터 수집
prev_rx=$(cat /proc/net/dev | grep "$INTERFACE" | awk '{print $2}')
prev_tx=$(cat /proc/net/dev | grep "$INTERFACE" | awk '{print $10}')

# 1분마다 트래픽 데이터 비교
while true; do

    # 현재 트래픽 데이터 수집
    curr_rx=$(cat /proc/net/dev | grep "$INTERFACE" | awk '{print $2}')
    curr_tx=$(cat /proc/net/dev | grep "$INTERFACE" | awk '{print $10}')

    # 트래픽 차이 계산
    rx_diff=$((curr_rx - prev_rx))
    tx_diff=$((curr_tx - prev_tx))

    # 트래픽 데이터를 로그 파일에 저장
    echo "$(date "+%Y-%m-%d %H:%M:%S")  RX: $rx_diff bytes, TX: $tx_diff bytes" >> "$TRAFFIC_FILE"

    # 이전 트래픽 데이터를 현재 데이터로 업데이트
    prev_rx=$curr_rx
    prev_tx=$curr_tx

    # 트래픽이 300000 바이트 이상인 경우 SYN 패킷을 캡처하여 SYN_FILE에 저장
    if [ $tx_diff -ge 300000 ]; then
        send_data $SCRIPT_ID 1
        tcpdump -i $INTERFACE 'tcp[tcpflags] & tcp-syn != 0' -n -q -tttt >> "$SYN_FILE"
        
        # 3번 이상 나타나는 IP 주소를 추출하여 3synips.log에 저장
        awk '{print $4 " > " $6}' "$SYN_FILE" | sort | uniq -c | while read count ip; do
            if [ "$count" -ge "$THRESHOLD" ]; then
                echo "$count 번 : $ip" >> "$THREE_SYN_FILE"
            fi
        done
    else
        send_data $SCRIPT_ID 0
    fi
    sleep 15
done

