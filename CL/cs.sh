#!/bin/bash

# 필요한 패키지 설치
install_packages() {
    echo "Installing required packages: jq, curl, inotifywait"
    sudo apt-get update
    sudo apt-get install -y jq curl inotify-tools python3 python3-pip 
}

# 각 스크립트의 경로를 배열에 저장
scripts=(
    "/home/CL/arp.sh"
    "/home/CL/ddos2.sh"
    "/home/CL/ddos1.sh"
    "/home/CL/ports.sh"
    "/home/CL/rw.sh"
    "/home/CL/fpd.sh"
    "/home/CL/pbd.sh"
    # 추가 스크립트를 여기에 추가
)

# 계속 실행할 스크립트 지정
persistent_script="/home/CL/hash.sh"

# 계속 실행할 스크립트를 30초마다 실행
(
    while true; do
        echo "Running persistent script $persistent_script"
        bash "$persistent_script"
        sleep 30
    done
) &

# 나머지 스크립트를 병렬로 실행
for script in "${scripts[@]}"
do
    echo "Running $script"
    bash "$script" &
done

# 모든 백그라운드 작업이 완료될 때까지 기다림
wait
echo "All scripts finished"

