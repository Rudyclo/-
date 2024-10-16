#!/bin/bash

# 검사할 디렉토리 경로
DIRECTORY="/opt/stack/data/glance/images"  # 적절한 경로로 수정

# 디렉토리가 존재하는지 확인
if [ ! -d "$DIRECTORY" ]; then
  echo "디렉토리가 존재하지 않습니다: $DIRECTORY"
  exit 1
fi

# 로그 파일 경로
LOG_FILE="/var/log/hashlog.csv"

# 새로운 로그 파일 경로
NEW_LOG_FILE="/var/log/new_download_hashlog.csv"

# 감시할 디렉토리 경로
WATCHED_DIRECTORY="$DIRECTORY"

# 초기 해시값 저장을 위한 딕셔너리 파일 경로
HASH_STORE_FILE="/var/log/hashstore.txt"

# 로그 파일 초기화
echo "파일,다운로드 시간,해시값,상태" > "$LOG_FILE"
echo "파일,다운로드 시간,해시값" > "$NEW_LOG_FILE"

# 감시 시작 메시지 출력
echo "디렉토리 감시 시작: $WATCHED_DIRECTORY"

# 초기 해시값 저장 함수
store_initial_hash() {
    local FILE="$1"
    local HASH=$(sha256sum "$FILE" | awk '{print $1}')
    echo "$(basename "$FILE"):$HASH" >> "$HASH_STORE_FILE"
}

# 해시값을 딕셔너리에서 로드
declare -A initial_hashes
if [ -f "$HASH_STORE_FILE" ]; then
    while IFS=":" read -r filename hash; do
        initial_hashes["$filename"]="$hash"
    done < "$HASH_STORE_FILE"
fi

# 파일 검사 함수
scan_file() {
    local FILE="$1"
    local FILENAME=$(basename "$FILE")
    echo "검사 중: $FILENAME"

    if [ ! -e "$FILE" ]; then
        echo "파일이 존재하지 않습니다: $FILENAME" >> /var/log/hashlog_error.log
        return
    fi

    if [ -d "$FILE" ]; then
        echo "디렉토리입니다: $FILENAME" >> /var/log/hashlog_error.log
        return
    fi

    STATUS="0" # 기본값을 0 (양호)로 설정

    # 파일의 해시값 계산
    HASH=$(sha256sum "$FILE" | awk '{print $1}')
    if [ -z "$HASH" ];then
        echo "해시값을 계산할 수 없습니다: $FILENAME" >> /var/log/hashlog_error.log
        return
    fi

    # 초기 해시값과 비교
    if [[ "${initial_hashes[$FILENAME]}" != "" && "${initial_hashes[$FILENAME]}" != "$HASH" ]]; then
        STATUS="1"  # 해시값이 변조된 경우 1 (취약)으로 설정
    fi

    # 초기 해시값이 없으면 저장
    if [[ "${initial_hashes[$FILENAME]}" == "" ]]; then
        initial_hashes["$FILENAME"]="$HASH"
        store_initial_hash "$FILE"
    fi

    # 해시값 출력
    echo "해시값: $HASH"

    # 로그 파일에 필요한 정보 저장
    echo "$FILENAME,$(date "+%Y-%m-%d %H:%M:%S"),$HASH,$STATUS" >> "$LOG_FILE"
    echo "파일 상태: $STATUS"

    echo "검사가 완료되었습니다: $FILENAME"
    echo "------------------------------"
}

# 기존 파일들 스캔
scan_existing_files() {
    > "$LOG_FILE"
    echo "파일,다운로드 시간,해시값,상태" > "$LOG_FILE"
    for FILE in "$DIRECTORY"/*; do
        if [ -e "$FILE" ]; then
            scan_file "$FILE"
        fi
    done
}

# 기존 파일들 스캔
scan_existing_files

# Python 스크립트를 통해 CSV를 엑셀로 변환 및 다운로드 폴더에 같은 이름 파일이 있으면 삭제
python3 <<EOF
import os
import pandas as pd
import requests

def send_file(file_path):
    url = 'http://192.168.56.1:5000/upload-file'
    files = {'file': open(file_path, 'rb')}
    response = requests.post(url, files=files)
    if response.status_code == 200:
        print('File sent successfully:', response.json())
    else:
        print('Failed to send file:', response.status_code, response.text)

try:
    # CSV 파일을 읽어 데이터프레임으로 변환
    df = pd.read_csv('$LOG_FILE', usecols=[0, 1, 2, 3], dtype=str)

    # 중복된 행 제거
    df = df.drop_duplicates()

    # 엑셀 파일 경로 설정
    output_excel_file = '/home/rudy/다운로드/hashlog.xlsx'

    # 동일한 이름의 파일이 존재하면 삭제
    if os.path.exists(output_excel_file):
        os.remove(output_excel_file)
        print(f"기존 엑셀 파일이 삭제되었습니다: {output_excel_file}")

    # 데이터프레임을 엑셀 파일로 저장
    df.to_excel(output_excel_file, index=False, header=['파일', '다운로드 시간', '해시값', '상태'])

    print(f"엑셀 파일이 성공적으로 생성되었습니다: {output_excel_file}")

    # 엑셀 파일을 서버로 전송
    send_file(output_excel_file)

except Exception as e:
    print(f"엑셀 파일 생성 중 오류 발생: {e}")
EOF

# 스크립트 종료 메시지 출력
echo "스크립트 실행이 완료되었습니다."

