#!/bin/bash

# 데이터 전송 함수
send_data() {
    url="http://192.168.56.1:5000/receive-data"
    data=$(jq -n --arg id "PW" --arg status "$1" '{id: $id, status: $status}')
    echo "Sending data: $data to $url"
    curl -X POST -H "Content-Type: application/json" -d "$data" "$url" -v
}

# 파일 변경 감지 및 상태 전송
echo "Watching for changes in /etc/shadow..."
while true; do
    # 파일 수정 감지
    inotifywait -e modify /etc/shadow
    
    # 파일 수정이 감지되면 상태 1을 전송
    send_data 1

    # 일정 시간 대기 후 상태 0을 전송
    sleep 10
    send_data 0
done

