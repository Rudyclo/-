import tkinter as tk
from tkinter import ttk, Toplevel, Canvas, Label
import subprocess
import sys
import os
import shutil
import urllib.request
from datetime import datetime
from PIL import Image, ImageTk
import threading
from flask import Flask, request, jsonify
import pandas as pd
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.colors import Color
from PIL import Image, ImageOps

# Flask 애플리케이션 설정
app = Flask(__name__)

# 데이터 수신을 위한 엔드포인트
@app.route('/receive-data', methods=['POST'])
def receive_data():
    data = request.json
    script_id = data.get('id')
    status = data.get('status')

    if script_id in vulnerability_status:
        # 공격이 발생하면 빨간불로 변경
        if bool(int(status)):
            update_status(script_id, True)  # 공격 발생 시 빨간불로 변경
        else:
            # 보고서 확인 후에는 초록불로 변경
            update_status(script_id, False)
    else:
        print("Unknown script ID")

    return jsonify({'status': 'success', 'message': 'Data received successfully'})

# 파일 업로드를 위한 엔드포인트
@app.route('/upload-file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
    
    upload_folder = 'uploads'
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, file.filename)
    
    file.save(file_path)
    
    analyze_file(file_path)
    
    return jsonify({'status': 'success', 'message': 'File uploaded and analyzed successfully'}), 200

def run_server():
    app.run(host='192.168.56.1', port=5000)

# Flask 서버를 별도의 스레드에서 실행
threading.Thread(target=run_server).start()

# ToolTip 클래스 정의
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        if self.tooltip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = Label(self.tooltip_window, text=self.text, justify='left', background='lightgrey', relief='solid', borderwidth=1)
        label.pack(ipadx=1)

    def hide_tooltip(self, event):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None

# 필요한 라이브러리 설치 함수
def install_packages():
    def install(package):
        subprocess.check_call([sys.executable, "-m", "pip", "install", package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    try:
        import reportlab
    except ImportError:
        print("reportlab 모듈이 설치되어 있지 않습니다. 자동으로 설치합니다...")
        install("reportlab")
    
    try:
        import pandas as pd
    except ImportError:
        print("pandas 모듈이 설치되어 있지 않습니다. 자동으로 설치합니다...")
        install("pandas")

install_packages()

# 폰트 등록
pdfmetrics.registerFont(TTFont("MalgunGothic", "malgun.ttf"))
pdfmetrics.registerFont(TTFont("MalgunGothicBold", "malgunbd.ttf"))  # 볼드체 폰트 등록

# 배경 투명화 함수 추가
def make_background_transparent(image_path):
    """흰색 배경을 투명하게 만드는 함수"""
    img = Image.open(image_path)
    img = img.convert("RGBA")
    datas = img.getdata()
    
    new_data = []
    for item in datas:
        if item[:3] == (255, 255, 255):  # 흰색 배경을 투명하게 변경
            new_data.append((255, 255, 255, 0))  # 투명도 0
        else:
            new_data.append(item)
    
    img.putdata(new_data)
    img.save(image_path, "PNG")

def download_image(url, save_path):
    """URL에서 이미지를 다운로드하는 함수"""
    urllib.request.urlretrieve(url, save_path)

def convert_image_to_gray(image_path, output_path):
    """이미지를 연한 회색으로 변환하는 함수"""
    img = Image.open(image_path).convert("RGBA")  # 이미지를 RGBA 형식으로 변환
    datas = img.getdata()

    new_data = []
    for item in datas:
        if item[:3] == (255, 255, 255):  # 흰색 배경을 투명하게 변경
            new_data.append((255, 255, 255, 0))  # 투명도 0
        else:
            new_data.append((192, 192, 192, item[3]))  # 회색으로 변경

    img.putdata(new_data)
    img.save(output_path, "PNG")

# 이미지 URL과 저장 경로 설정
image_url = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRGaqsh89BpMXnbbLJniGeq_rfHb6RmhlCvjg&s"
input_image_path = "school_mark.png"
output_image_path = "gray_school_mark.png"

# 이미지 다운로드 후 연한 회색으로 변환
download_image(image_url, input_image_path)
convert_image_to_gray(input_image_path, output_image_path)

# PDF 보고서 생성 함수 수정
def create_report(attack_type, data_to_add):
    filename = f"{attack_type}_report.pdf"
    
    # A4 사이즈 설정 및 여백 설정
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=1*inch, rightMargin=1*inch)
    
    # 스타일 설정 (폰트: 맑은 고딕)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MalgunTitle', fontName='MalgunGothic', fontSize=23, alignment=1))  # 가운데 정렬 제목
    styles.add(ParagraphStyle(name='MalgunNormal', fontName='MalgunGothic', fontSize=12, leading=18))  # 줄 간격 설정
    styles.add(ParagraphStyle(name='MalgunNormalRight', fontName='MalgunGothic', fontSize=12, alignment=2, leading=14))  # 오른쪽 정렬
    
    # 새로운 스타일: 가운데 정렬을 위한 스타일 추가
    centered_style = ParagraphStyle(name='Centered', fontName='MalgunGothic', fontSize=12, alignment=1, leading=18)  # 줄 간격 적용

    # PDF 요소 리스트 생성
    elements = []
    
    # 보고서 제목 추가 (가운데 정렬)
    title = Paragraph(f"{attack_type} 보고서", styles['MalgunTitle'])
    elements.append(title)

    # 제목과 제작자 정보 사이에 여백 추가
    elements.append(Spacer(1, 30))

    # 제작자 정보 추가 (오른쪽 정렬)
    creation_info = f"제작자 : 구름"
    elements.append(Paragraph(creation_info, styles['MalgunNormalRight']))

    # 제작자 정보 아래에 여백 추가
    elements.append(Spacer(1, 20))

    # Hash 공격 유형에 대해 엑셀에서 가져온 데이터 추가 (자동 줄바꿈 및 엔터)
    if attack_type == "Hash" and data_to_add:
        hash_content = "\n".join(data_to_add)  # 해시값을 줄바꿈으로 추가
        hash_paragraph = Paragraph(hash_content, styles['MalgunNormal'])
    else:
        hash_paragraph = Paragraph(get_expected_vulnerability(attack_type), styles['MalgunNormal'])

    # 테이블 데이터 생성 (1열, 1행에 텍스트 가운데 정렬 적용)
    table_data = [
        [Paragraph("구분", centered_style), Paragraph("상세 내용", centered_style)],  # 1행 텍스트를 가운데 정렬
        [Paragraph("생성 일시", centered_style), Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), styles['MalgunNormal'])],
        [Paragraph("예상 취약점", centered_style), Paragraph(hash_paragraph.text if attack_type == "Hash" else get_expected_vulnerability(attack_type), styles['MalgunNormal'])],
        [Paragraph("대응 방안", centered_style), Paragraph(get_solution(attack_type), styles['MalgunNormal'])],
    ]

    # 테이블 스타일 및 구성
    table = Table(table_data, colWidths=[2*inch, 4.5*inch])
    
    # 매우 연한 회색 배경색
    very_light_gray = colors.Color(0.95, 0.95, 0.95)
    
    # 테이블 스타일 설정
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), very_light_gray),  # 1열 전체에 연한 회색 배경
        ('BACKGROUND', (0, 0), (-1, 0), very_light_gray),  # 첫 번째 행에 연한 회색 배경
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),  # 텍스트 색상
        ('FONTNAME', (0, 0), (-1, -1), 'MalgunGothic'),  # 폰트: 맑은 고딕
        ('FONTSIZE', (0, 0), (-1, -1), 12),  # 폰트 크기: 12
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),  # 각 셀의 아래쪽 패딩
        ('TOPPADDING', (0, 0), (-1, -1), 12),     # 각 셀의 위쪽 패딩
        ('GRID', (0, 0), (-1, -1), 1, colors.black),  # 테두리 설정
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # 수직 가운데 정렬
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # 첫 번째 열 텍스트 가운데 정렬
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # 첫 번째 행 텍스트 가운데 정렬
    ]))
    
    elements.append(table)

    # 캔버스 함수 정의
    def add_watermark(canvas, doc):
        # 캔버스 크기 가져오기
        width, height = A4
        
        # 연한 회색으로 학교 마크 이미지 추가 (400x400 크기)
        canvas.setFillColor(Color(0.8, 0.8, 0.8, alpha=0.2))  # 아주 연한 회색
        canvas.drawImage(output_image_path, (width - 400) / 2, (height - 400) / 2, 400, 400, mask='auto')

    # PDF 저장 (페이지마다 커스텀 캔버스 적용)
    doc.build(elements, onFirstPage=add_watermark, onLaterPages=add_watermark)

# 상태 표시기를 업데이트하는 함수
def update_status(script_id, status):
    if status:
        # 새로운 공격이 발생하면 빨간불로 변경
        status_indicators[script_id].itemconfig("circle", fill="red")
        report_buttons[script_id].config(state=tk.NORMAL)
        vulnerability_status[script_id] = True  # 공격 상태를 True로 설정
    else:
        # 보고서를 확인했을 때 초록불로 변경
        status_indicators[script_id].itemconfig("circle", fill="green")
        report_buttons[script_id].config(state=tk.DISABLED)
        vulnerability_status[script_id] = False  # 안전 상태로 설정

    # 취약점 상태 업데이트
    vulnerability_status[script_id] = status

def analyze_file(file_path):
    if not os.path.exists(file_path):
        return
    
    # 엑셀 파일에서 Hash 데이터를 읽어오기
    df = pd.read_excel(file_path)
    data_to_add = df[df.iloc[:, 3] == 1].iloc[:, 0].tolist()  # D열 (4번째 열) 값이 1인 행의 데이터 가져오기
    
    if data_to_add:
        update_status("Hash", True)
        hash_data["Hash"] = data_to_add
    
    # 엑셀 파일 삭제
    os.remove(file_path)

# 예상 취약점 및 대응 방안 함수
def get_expected_vulnerability(attack_type):
    if attack_type == "DDoS1":
        return "의도치 않은 트래픽 급증과 반복적인 IP 주소 접근으로 인한 보안 취약성이 예상됩니다."
    elif attack_type == "DDoS2":
        return "비정상적으로 높은 연결 수와 특정 IP 주소로부터의 집중적인 트래픽으로 인한 보안 취약성이 예상됩니다."
    elif attack_type == "PBD":
        return "비정상적인 프로세스가 탐지 되었습니다. <br/><br/>공격자가 시스템에 백도어를 설치하여 원격으로 제어하려는 경우, nc 또는 netcat과 같은 유틸리티를 사용해 원격 셸을 실행하거나 bash -i 명령을 통해 상호작용 셸을 생성할 수 있습니다. <br/><br/>Python이나 Bash 스크립트를 사용해 시스템에서 악성 코드를 실행할 수 있습니다. 예를 들어, python -c 명령을 사용해 특정 명령을 직접 실행하는 경우가 이에 해당합니다."
    elif attack_type == "FBD":
        return "파일 변조 및 백도어 설치 의심 <br/><br/>공격자가 /etc/passwd, /etc/shadow, /etc/hosts, /etc/ssh/sshd_config와 같은 중요한 시스템 파일을 수정하여 백도어를 설치하거나 시스템 권한을 획득하려는 상활일수 있습니다. <br/><br/>/etc/ssh/sshd_config 파일이 변조될 경우, SSH 접근 권한이나 인증 방법이 변경되어 공격자가 시스템에 무단으로 접근할 수 있습니다."
    elif attack_type == "PW":
        return "공격자가 시스템 사용자 계정(Root)의 비밀번호를 변경하였습니다. <br/><br/>새로운 계정을 추가하여 시스템에 비인가된 접근을 시도할 수 있습니다. <br/><br/>공격자가 루트 권한을 획득하거나 기존 계정의 권한을 변경하여 시스템을 장악하는 데 사용될 수 있습니다."
    elif attack_type == "ARP":
        return "네트워크 장치 및 구성이 비정상적으로 변경되거나 ARP 테이블이 변경될 때 발생할 수 있는 보안 취약성이 예상됩니다."
    elif attack_type == "Port.S":
        return "비인가된 포트 오픈과 네트워크 서비스의 오남용으로 인한 보안 취약성이 예상됩니다."
    elif attack_type == "Hash":
        return "1. 클라우드 업로드 데이터중 해시값이 변경됨 <br/>클라우드에 업로드하는 데이터의 해시값이 변경될 수 있는 잠재적 취약점이 존재합니다. 이 경우, 파일의 무결성이 의심받게 되며, 해시값이 초기 저장값과 다르다는 것은 파일이 수정되었음을 의미합니다. <br/>해시값 변경의 원인은 여러 가지가 있을 수 있습니다. 예를 들어, 파일이 업로드되는 과정에서 손상이 발생하거나, 시스템 오류로 인해 데이터가 제대로 저장되지 않을 수 있습니다. <br/><br/>2. 중간자 공격 <br/>클라우드 업로드 과정에서 중간자 공격이 발생할 수 있습니다. <br/>이 공격은 공격자가 클라이언트와 서버 간의 데이터 전송 경로에 개입하여 데이터를 가로채거나 수정하는 방식으로 진행됩니다. 예를 들어, 사용자가 클라우드에 파일을 업로드하는 동안, 공격자는 네트워크를 통해 데이터 패킷을 가로채고 파일을 변경한 뒤 클라우드 서버로 전송할 수 있습니다. <br/><br/>3. 악성 코드 삽입 <br/>바이러스나 웜과 같은 악성 코드가 클라우드 업로드 과정에서 추가될 가능성도 있습니다. 사용자가 업로드하는 파일에 대한 무결성을 검사하는 절차가 부족할 경우, 악성 코드가 포함된 파일이 클라우드에 저장될 수 있습니다."
    else:
        return "."

def get_solution(attack_type):
    if attack_type == "DDoS1":
        return "SYN 패킷이 일정 수 이상 감지될 경우, 이를 악의적인 활동의 징후로 판단하여, 자동으로 해당 IP 주소를 차단하는 기능을 추가하여 보안을 강화합니다. <br/>이와 동시에, 감지된 트래픽에 대한 추가적인 로깅과 트래픽 분석을 통해, 패킷의 상세 정보를 기록하고, 공격 패턴을 심층적으로 분석하여 향후 발생할 수 있는 공격을 더 효과적으로 차단할 수 있도록 합니다."
    elif attack_type == "DDoS2":
        return "네트워크 성능과 보안을 유지하기 위해, 불필요하거나 과도한 트래픽이 발생할 경우 이를 효과적으로 제한하여 네트워크의 과부하를 방지하고, 동시에 중요한 서비스들이 안정적으로 운영될 수 있도록 보호하는 조치를 강화합니다. <br/>이를 통해 정상적인 사용자 경험을 보장하면서도 잠재적인 위협으로부터 시스템을 안전하게 유지합니다."
    elif attack_type == "PBD":
        return "1. 의심스러운 프로세스가 감지되면, 관리자는 즉시 해당 프로세스를 강제 종료해야 합니다. kill 명령을 사용하여 프로세스를 종료하고, 재발 방지를 위해 해당 프로세스가 실행된 경로와 관련 파일을 조사하여 제거해야 합니다. <br/><br/>2. 시스템을 즉시 격리하고 네트워크 연결을 차단하여 추가적인 원격 접근이나 데이터 유출을 방지해야 합니다. 격리된 상태에서 추가적인 조사를 수행합니다. <br/><br/>3. 비정상적인 프로세스가 실행된 이유와 경로를 파악하기 위해, 시스템 로그를 철저히 분석합니다. 이 과정에서 공격자가 어떤 경로를 통해 시스템에 접근했는지, 추가적인 악성 프로세스가 존재하는지 확인해야 합니다. <br/><br/>4. 발견된 백도어 및 악성 프로세스를 제거한 후, 시스템의 보안 취약점을 보완하기 위해 필요한 패치를 적용하고, 시스템 보안을 강화해야 합니다. 특히, 원격 접속 설정과 방화벽 규칙을 재검토하여 취약점이 없는지 확인합니다."
    elif attack_type == "FBD":
        return "1. 변조가 감지된 파일에 대해 시스템 관리자는 즉각적으로 해당 시스템의 네트워크 연결을 제한하거나 SSH 접근을 차단하여 추가적인 피해를 방지해야 합니다. <br/><br/>2. 변조가 감지된 파일에 대해 원본 파일과 비교하여 어떤 부분이 변경되었는지 확인하고, 백업된 파일이나 신뢰할 수 있는 소스에서 해당 파일을 복구해야 합니다. <br/>예를 들어, /etc/passwd나 /etc/shadow 파일이 변조된 경우, 정상적인 파일로 복구한 후 사용자 비밀번호를 재설정할 필요가 있습니다. <br/><br/>3. 변조가 감지되면 즉시 관련 로그 파일을 분석하여 공격의 원인을 파악하고, 시스템 전반에 걸쳐 다른 변조된 파일이 없는지 확인합니다. <br/>이 과정에서 로그 파일의 시간대와 IP 주소 등을 분석하여 공격자의 흔적을 찾습니다."
    elif attack_type == "PW":
        return "1. 변조가 감지된 후 시스템 관리자는 즉시 해당 시스템의 SSH 접근을 제한하거나, 전체 시스템의 네트워크를 차단하여 추가적인 공격 시도를 막아야 합니다. <br/><br/>2. 변조된 /etc/shadow 파일을 신뢰할 수 있는 백업 파일로 복구하고, 시스템의 모든 사용자 비밀번호를 재설정해야 합니다. 특히, 루트 계정 및 중요한 계정의 비밀번호는 즉시 변경하고, 모든 사용자에게도 비밀번호 변경을 요청해야 합니다. <br/><br/>3. 변조된 시점을 기준으로 시스템 로그를 철저히 분석하여 공격자가 어떤 경로로 시스템에 접근했는지, 추가적인 피해가 있는지를 조사합니다. <br/>변조 이후 모든 사용자 계정을 점검하여, 비인가된 계정이 생성되었는지 여부를 확인합니다. 비인가 계정이 발견되면 즉시 삭제하고, 해당 계정이 어떤 권한을 가지고 있었는지 조사하여 추가적인 보안 조치를 취해야 합니다."
    elif attack_type == "ARP":
        return "보안 이벤트가 발생했을 때 이를 신속히 감지하고 대응하기 위해, 먼저 알림 및 로그 기록을 철저히 확인하여 문제가 발생한 시점과 원인을 정확히 파악합니다. 그런 다음, 이러한 정보를 네트워크 관리 시스템과 긴밀하게 연동시켜, 중앙에서 네트워크 상태를 모니터링하고 이상 징후에 대한 통합적인 관리와 대응을 가능하게 합니다."
    elif attack_type == "Port.S":
        return "네트워크 보안을 강화하기 위해 주기적인 스캔 주기를 환경에 맞게 최적화하여, 불필요한 리소스 소모를 줄이면서도 잠재적인 위협을 효과적으로 감지할 수 있도록 조정하며, 동시에 각종 서비스의 설정을 더욱 강화하여 비인가된 접근이나 악의적인 사용을 방지하는 조치를 취합니다."
    elif attack_type == "Hash":
        return "1. 파일 변경 사유 기록 <br/>파일 변경 시 변경 사유를 함께 기록하고, 해시값을 비교할 때 변경 사유를 검토하여 정당성을 판단하도록 합니다. <br/><br/>2. 상세 로그 기록 강화 <br/>검사 시 파일 상태, 변경 이력, 검사 당시의 타임스탬프 등을 포함한 상세 로그를 기록하여, 이후에 발생할 수 있는 해시값 불일치에 대한 맥락을 제공합니다. <br/><br/>3. 문제점인 파일에 대한 처리 강화 <br/>문제점인 파일에 대한 처리 강화를 위해서는 클라우드 업로드 과정에서 파일 무결성 검사를 철저히 수행해야 합니다. 이를 통해 업로드되는 파일이 원본과 동일한지 확인하고, 변조된 파일은 즉시 차단할 수 있습니다. <br/><br/><br/>*주의사항* <br/><br/>- 단일 해시값 기준 <br/>스크립트는 각 파일의 상태를 단일 해시값으로만 판단하기 때문에 만약 해시값이 변경되었을 때는 해당 파일이 변조된 것으로 간주됩니다. 그러나 정상적인 업데이트나 변경이 발생한 경우에도 해시값이 변경되기 때문에, 이를 변조로 잘못 인식할 수 있습니다. 이는 파일 변경이 실제로는 정당한 사유에 의한 것일 수 있음에도 불구하고 변조로 잘못 판단하게 만듭니다. <br/><br/>- 해시값 검증의 신뢰성 부족 <br/>초기 해시값이 변하지 않는다고 가정하더라도, 해시값 검증의 신뢰성이 보장되지 않는 경우가 있습니다. 예를 들어, 만약 파일이 검사하는 동안 다른 프로세스에 의해 변경되거나, 네트워크를 통해 파일이 다운로드되는 경우, 해시값을 계산하기 직전에 파일의 상태가 변경될 수 있습니다. 이러한 경우, 실제로는 정상적인 파일이지만 변조로 잘못 인식될 수 있습니다."
    else:
        return "."

# 보고서 열기 함수
def open_report(attack_type, data_to_add):
    # 보고서 생성
    create_report(attack_type, data_to_add)
    
    # 보고서가 열렸으므로 상태를 초록불로 변경
    filename = f"{attack_type}_report.pdf"
    if sys.platform == "win32":
        os.startfile(filename)
    else:
        subprocess.call(["open", filename])

    # 보고서 확인 후 상태를 초록불로 변경
    report_checked[attack_type] = True  # 보고서 확인 플래그
    locked_status[attack_type] = False  # 빨간불 고정 해제
    update_status(attack_type, False)  # 상태를 초록불로 변경
    delete_uploads_folder()

def analyze_file(file_path):
    if not os.path.exists(file_path):
        return
    
    df = pd.read_excel(file_path)
    data_to_add = df[df.iloc[:, 3] == 1].iloc[:, 0].tolist()  # D열 (4번째 열) 값이 1인 행의 데이터 가져오기
    
    if data_to_add:
        update_status("Hash", True)
        hash_data["Hash"] = data_to_add
    
    # 엑셀 파일 삭제
    os.remove(file_path)

def delete_uploads_folder():
    upload_folder = 'uploads'
    if os.path.exists(upload_folder):
        shutil.rmtree(upload_folder)

# 초기 취약점 상태 설정
vulnerability_status = {
    "DDoS1": False,
    "DDoS2": False,
    "PBD": False,
    "FBD": False,
    "PW": False,
    "ARP": False,
    "Port.S": False,
    "Hash": False
}

# 보고서 확인 여부를 추적하는 딕셔너리 추가
report_checked = {
    "DDoS1": False,
    "DDoS2": False,
    "PBD": False,
    "FBD": False,
    "PW": False,
    "ARP": False,
    "Port.S": False,
    "Hash": False
}

# 빨간불 고정 플래그 변수 추가
locked_status = {
    "DDoS1": False,
    "DDoS2": False,
    "PBD": False,
    "FBD": False,
    "PW": False,
    "ARP": False,
    "Port.S": False,
    "Hash": False
}

hash_data = {"Hash": []}

# 상태 표시기를 업데이트하는 함수
def update_status(script_id, status):
    # 보고서가 확인되기 전까지 상태를 락함
    if locked_status[script_id]:  # 빨간불 고정 상태인 경우
        status_indicators[script_id].itemconfig("circle", fill="red")
        report_buttons[script_id].config(state=tk.NORMAL)
        return

    if status:
        # 빨간불 상태로 변경 및 고정 플래그 설정
        status_indicators[script_id].itemconfig("circle", fill="red")
        report_buttons[script_id].config(state=tk.NORMAL)
        vulnerability_status[script_id] = True
        locked_status[script_id] = True  # 빨간불 상태 고정
    else:
        # 초록불로 바뀌지 않도록 고정
        status_indicators[script_id].itemconfig("circle", fill="red")  # 빨간불 유지
        report_buttons[script_id].config(state=tk.NORMAL)

    # 취약점 상태 업데이트
    vulnerability_status[script_id] = status

    if script_id == "DDoS1":
        if status:
            status_indicators["DDoS1"].itemconfig("circle", fill="red")
            report_buttons["DDoS1"].config(state=tk.NORMAL)
        else:
            status_indicators["DDoS1"].itemconfig("circle", fill="green")
            report_buttons["DDoS1"].config(state=tk.DISABLED)

    elif script_id == "DDoS2":
        if status:
            status_indicators["DDoS2"].itemconfig("circle", fill="red")
            report_buttons["DDoS2"].config(state=tk.NORMAL)
        else:
            status_indicators["DDoS2"].itemconfig("circle", fill="green")
            report_buttons["DDoS2"].config(state=tk.DISABLED)

    elif script_id == "PBD":
        if status:
            status_indicators["PBD"].itemconfig("circle", fill="red")
            report_buttons["PBD"].config(state=tk.NORMAL)
        else:
            status_indicators["PBD"].itemconfig("circle", fill="green")
            report_buttons["PBD"].config(state=tk.DISABLED)

    elif script_id == "FBD":
        if status:
            status_indicators["FBD"].itemconfig("circle", fill="red")
            report_buttons["FBD"].config(state=tk.NORMAL)
        else:
            status_indicators["FBD"].itemconfig("circle", fill="green")
            report_buttons["FBD"].config(state=tk.DISABLED)

    elif script_id == "PW":
        if status:
            status_indicators["PW"].itemconfig("circle", fill="red")
            report_buttons["PW"].config(state=tk.NORMAL)
        else:
            status_indicators["PW"].itemconfig("circle", fill="green")
            report_buttons["PW"].config(state=tk.DISABLED)

    elif script_id == "ARP":
        if status:
            status_indicators["ARP"].itemconfig("circle", fill="red")
            report_buttons["ARP"].config(state=tk.NORMAL)
        else:
            status_indicators["ARP"].itemconfig("circle", fill="green")
            report_buttons["ARP"].config(state=tk.DISABLED)

    elif script_id == "Port.S":
        if status:
            status_indicators["Port.S"].itemconfig("circle", fill="red")
            report_buttons["Port.S"].config(state=tk.NORMAL)
        else:
            status_indicators["Port.S"].itemconfig("circle", fill="green")
            report_buttons["Port.S"].config(state=tk.DISABLED)

    elif script_id == "Hash":
        if status:
            status_indicators["Hash"].itemconfig("circle", fill="red")
            report_buttons["Hash"].config(state=tk.NORMAL)
        else:
            status_indicators["Hash"].itemconfig("circle", fill="green")
            report_buttons["Hash"].config(state=tk.DISABLED)

# 상태 표시기를 업데이트하는 코드
status_indicators = {}
report_buttons = {}

# 메인 윈도우 생성 및 설정
root = tk.Tk()
root.title("구름")
root.geometry("1000x800")
root.minsize(1000, 800)
root.maxsize(1000, 800)
font_style = ("Helvetica", 10)

# 상단 프레임 생성
top_frame = tk.Frame(root)
top_frame.pack(pady=10, fill="x")

# GUI 기능 설명 레이블
gui_frame = tk.LabelFrame(top_frame, text=" GUI 기능 설명 ", font=("Helvetica", 12, "bold"))
gui_frame.grid(row=0, column=0, rowspan=4, padx=20, pady=10, sticky='nw')

gui_label = tk.Label(gui_frame, text="""
이 프로그램은 네트워크 취약점을 검사하고 그 결과를 시각적으로 표시하는 도구입니다. 

주요 기능은 다음과 같습니다.


  1. 공격 유형 설명
                     
     - 각 공격 유형(DDoS1, DDoS2, PBD, FBD 등)에 대한 설명이 포함되어 있습니다.
     - 마우스를 각 공격 유형 위에 올리면 해당 공격 유형에 대한 자세한 설명을 툴팁으로 확인할 수 있습니다.

                     
  2. 상태 표시기
                     
     - 각 공격 유형에 대해 네트워크가 취약한지 여부를 시각적으로 표시합니다.
     - 빨간색 원은 취약함을, 초록색 원은 안전함을 의미합니다.

                     
  3. 보고서 버튼
                     
     - 각 공격 유형에 대한 보고서를 PDF 파일로 생성하고 열 수 있습니다.
     - 보고서는 안전한 상태(초록색)일시 비활성화되며, 위험한 상태(빨간색)일때만 활성화 됩니다.


이 프로그램은 네트워크 취약점 검사를 보다 쉽게 수행하고, 그 결과를 직관적으로 이해할 수 있도록 도와줍니다. 

각 기능을 활용하여 네트워크 보안을 강화할 수 있습니다.
""", font=("Helvetica", 10), width=85, height=27, anchor='w', justify='left')
gui_label.pack(padx=10, pady=10)

# 학교 마크 이미지 로드 및 라벨에 추가
school_image_path = "school_mark.png"
download_image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRGaqsh89BpMXnbbLJniGeq_rfHb6RmhlCvjg&s", school_image_path)
make_background_transparent(school_image_path)

school_image = ImageTk.PhotoImage(file=school_image_path)
school_mark_label = Label(top_frame, image=school_image)
school_mark_label.image = school_image
school_mark_label.grid(row=0, column=1, padx=10, pady=10, sticky='ne')

# 만든이 레이블 프레임
creators_frame = tk.LabelFrame(top_frame, text=" 팀원 소개 ", font=("Helvetica", 12, "bold"))
creators_frame.grid(row=1, column=1, padx=20, pady=(0, 10), sticky='ne')

creators_label = tk.Label(creators_frame, text="팀      장   :   하승범 91813248\n\n팀      원   :   김찬욱 91812218\n\n\t     고예진 92014954\n\n\t     김다빈 92103561\n\n\t     장진호 92113839\n\n담당 교수  :  양환석 교수님", font=("Helvetica", 10), anchor='w', justify='left')
creators_label.pack(padx=10, pady=10)

# 공격 유형 섹션
frame_attack = tk.LabelFrame(root, text=" 공격 유형 설명 ", font=("Helvetica", 12, "bold"))
frame_attack.pack(side=tk.TOP, fill=tk.X, padx=20, pady=(20, 20))

labels_attack = [
    ("DDoS1", "이 스크립트는 지정된 네트워크 인터페이스의 트래픽을 1분 간격으로 모니터링하여, \n트래픽이 3000 바이트를 초과하면 SYN 패킷을 캡처하고 로그 파일에 저장합니다. \n또한, 3회 이상 나타나는 IP 주소를 기록하여 DDoS 공격 가능성을 판단하며, 결과를 엑셀 파일에 기록합니다."),
    ("DDoS2", "이 스크립트는 지정된 네트워크 인터페이스에서 일정 간격으로 수신 패킷 수를 모니터링하여, \nDDoS 공격 여부를 감지하고 로그 파일과 엑셀 파일에 기록합니다. \n패킷 수가 설정한 임계값을 초과하면 DDoS 공격으로 간주하고 관련 정보를 기록합니다. \n정상 트래픽일 경우에도 로그 파일과 엑셀 파일에 기록합니다."),
    ("PBD", "이 스크립트는 30초 간격으로 시스템의 프로세스를 검사하여, \n백도어로 의심되는 비정상적인 프로세스(예: nc, telnetd, bash -i 등)가 실행 중인지 확인합니다. \n의심스러운 프로세스가 발견되면 서버에 경고 상태를 전송하고, \n정상일 경우에는 안전 상태를 보고합니다."),
    ("FBD", "이 스크립트는 시스템의 중요한 파일들이 백도어 설치나 \n기타 악의적인 변경으로 인해 변조되는 상황을 대비해 작성되었습니다. \n백도어는 공격자가 시스템에 지속적인 접근을 할 수 있도록 \n시스템 파일을 수정하거나 악성 코드를 삽입하는 형태로 구현됩니다."),
    ("PW", "이 스크립트는 /etc/shadow 파일의 수정 시간을 주기적으로 확인하여 변경 사항을 감지합니다. \n수정이 감지되면 엑셀 파일을 업데이트하여 변경 여부를 기록합니다. \n이를 통해 비밀번호 파일의 변조 여부를 감지할 수 있습니다."),
    ("ARP", "이 스크립트는 ARP 테이블을 10초 간격으로 모니터링하여 변경 사항을 감지합니다. \n변경이 감지되면 로그에 기록하고, 변경된 항목을 출력하며, \n엑셀 파일을 업데이트하여 ARP 공격의 가능성을 표시합니다."),
    ("Port.S", "이 스크립트는 특정 포트가 열려 있는지 확인하여 결과를 로그 파일과 엑셀 파일에 기록합니다. \n닫혀 있어야 하는 포트가 열려 있는 경우, 엑셀 파일에 해당 정보를 기록합니다."),
    ("Hash", "이 스크립트는 지정된 디렉토리 내의 파일들을 스캔하여 \n각 파일의 SHA-256 초기 해시값과 변환된 해쉬값을 비교하고\n 이 정보를 로그 파일에 기록한 후, \n로그 파일을 엑셀 파일로 변환하는 작업을 수행합니다.")
]

for i in range(len(labels_attack)):
    frame_attack.grid_columnconfigure(i, weight=1)

for i, (text, tooltip_text) in enumerate(labels_attack):
    label = Label(frame_attack, text=text, font=font_style, anchor='w')
    label.grid(row=0, column=i, padx=5, pady=5)
    ToolTip(label, tooltip_text)

# 상태 및 보고서 섹션
frame_status = tk.LabelFrame(root, text=" 상태 및 보고서 ", font=("Helvetica", 12, "bold"))
frame_status.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 20))

attack_types = ["DDoS1", "DDoS2", "PBD", "FBD", "PW", "ARP", "Port.S", "Hash"]

for idx in range(len(attack_types)):
    frame_status.grid_columnconfigure(idx, weight=1)

for idx, attack_type in enumerate(attack_types):
    ttk.Label(frame_status, text=attack_type, font=font_style).grid(row=0, column=idx, padx=10, pady=5)  # padx 값을 10으로 변경하여 간격 추가
    
    canvas = Canvas(frame_status, width=20, height=20, highlightthickness=0)
    canvas.create_oval(2, 2, 18, 18, outline="", fill="green", tags="circle")
    canvas.grid(row=1, column=idx, padx=10, pady=5)  # padx 값을 10으로 변경하여 간격 추가
    status_indicators[attack_type] = canvas
    
    report_button = ttk.Button(frame_status, text="보고서", command=lambda at=attack_type: open_report(at, hash_data[at] if at == "Hash" else []))
    report_button.grid(row=2, column=idx, padx=10, pady=10)  # padx와 pady 값을 10으로 변경하여 간격 추가
    report_buttons[attack_type] = report_button

# 초기 상태 표시기 업데이트
for attack_type, is_vulnerable in vulnerability_status.items():
    if attack_type == "DDoS1":
        if is_vulnerable:
            status_indicators["DDoS1"].itemconfig("circle", fill="red")
            report_buttons["DDoS1"].config(state=tk.NORMAL)
        else:
            status_indicators["DDoS1"].itemconfig("circle", fill="green")
            report_buttons["DDoS1"].config(state=tk.DISABLED)

    elif attack_type == "DDoS2":
        if is_vulnerable:
            status_indicators["DDoS2"].itemconfig("circle", fill="red")
            report_buttons["DDoS2"].config(state=tk.NORMAL)
        else:
            status_indicators["DDoS2"].itemconfig("circle", fill="green")
            report_buttons["DDoS2"].config(state=tk.DISABLED)

    elif attack_type == "PBD":
        if is_vulnerable:
            status_indicators["PBD"].itemconfig("circle", fill="red")
            report_buttons["PBD"].config(state=tk.NORMAL)
        else:
            status_indicators["PBD"].itemconfig("circle", fill="green")
            report_buttons["PBD"].config(state=tk.DISABLED)

    elif attack_type == "FBD":
        if is_vulnerable:
            status_indicators["FBD"].itemconfig("circle", fill="red")
            report_buttons["FBD"].config(state=tk.NORMAL)
        else:
            status_indicators["FBD"].itemconfig("circle", fill="green")
            report_buttons["FBD"].config(state=tk.DISABLED)

    elif attack_type == "PW":
        if is_vulnerable:
            status_indicators["PW"].itemconfig("circle", fill="red")
            report_buttons["PW"].config(state=tk.NORMAL)
        else:
            status_indicators["PW"].itemconfig("circle", fill="green")
            report_buttons["PW"].config(state=tk.DISABLED)

    elif attack_type == "ARP":
        if is_vulnerable:
            status_indicators["ARP"].itemconfig("circle", fill="red")
            report_buttons["ARP"].config(state=tk.NORMAL)
        else:
            status_indicators["ARP"].itemconfig("circle", fill="green")
            report_buttons["ARP"].config(state=tk.DISABLED)

    elif attack_type == "Port.S":
        if is_vulnerable:
            status_indicators["Port.S"].itemconfig("circle", fill="red")
            report_buttons["Port.S"].config(state=tk.NORMAL)
        else:
            status_indicators["Port.S"].itemconfig("circle", fill="green")
            report_buttons["Port.S"].config(state=tk.DISABLED)

    elif attack_type == "Hash":
        if is_vulnerable:
            status_indicators["Hash"].itemconfig("circle", fill="red")
            report_buttons["Hash"].config(state=tk.NORMAL)
        else:
            status_indicators["Hash"].itemconfig("circle", fill="green")
            report_buttons["Hash"].config(state=tk.DISABLED)

# 애플리케이션 실행
root.mainloop()
