#!/bin/bash

# ARP 테이블을 저장할 파일
ARP_TABLE_OLD="/home/CL/ncl/arp_table_old.txt"
ARP_TABLE_NEW="/home/CL/ncl/arp_table_new.txt"

# 서버 URL 및 스크립트 ID
SERVER_URL="http://192.168.56.1:5000/receive-data"
SCRIPT_ID="ARP"  # 적절한 script_id로 변경

# 서버로 상태 전송하는 함수
send_status() {
    local script_id=$1
    local status_value=$2
    local data=$(jq -n --arg id "$script_id" --arg status "$status_value" '{id: $id, status: $status}')
    local response=$(curl -s -w "%{http_code}" -o /dev/null -X POST -H "Content-Type: application/json" -d "$data" "$SERVER_URL")
}

# 초기 ARP 테이블 저장
arp -n > $ARP_TABLE_OLD

while true; do
    # 새로운 ARP 테이블 저장
    arp -n > $ARP_TABLE_NEW

    # ARP 테이블 비교
    if ! diff $ARP_TABLE_OLD $ARP_TABLE_NEW >/dev/null; then
        echo "ARP 테이블 변경 감지"

        # 변경된 항목 로그
        diff $ARP_TABLE_OLD $ARP_TABLE_NEW | while read line; do
            echo "변경된 항목: $line"
        done

        # 최신 ARP 테이블로 갱신
        cp $ARP_TABLE_NEW $ARP_TABLE_OLD

        # 엑셀 파일 업데이트 및 서버에 상태 전송
        send_status $SCRIPT_ID 1
    else
        # 엑셀 파일 업데이트 및 서버에 상태 전송
        send_status $SCRIPT_ID 0
    fi

    # 10초 대기
    sleep 10
done

