import sys
import os
import re
import fitz  # PyMuPDF를 fitz로 import 합니다.
import sqlite3

# similarity_analyzer.py가 simidoc_gui.py와 동일한 폴더에 위치해야 합니다.
try:
    import similarity_analyzer
except ModuleNotFoundError:
    print("ModuleNotFoundError: similarity_analyzer.py 모듈을 찾을 수 없습니다. 동일한 폴더에 있는지 확인하세요.")
    class DummySimilarityAnalyzer: # 모듈이 없을 때를 대비한 더미 클래스
        def __init__(self, db_path): pass
        def analyze_similarity(self, target_pdf_id, files_data): 
            print("ERROR: 유사도 분석 모듈이 로드되지 않아 분석 기능을 사용할 수 없습니다.")
            return []
    similarity_analyzer = DummySimilarityAnalyzer()


from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QCheckBox, QTextEdit, QSplitter, QFileDialog, QFrame,
    QMessageBox
)
from PyQt6.QtCore import Qt, QSize, QDateTime, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette


# --- 다크 모드 스타일시트 (QSS) ---
dark_style = """
QWidget {
    background-color: #1a1a1a; /* 메인 배경색 - 더 어두운 보라색 계열 */
    color: #E0E0E0; /* 기본 텍스트 색상 - 밝은 회색 */
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}

/* 제목 레이블 */
QLabel#titleLabel {
    font-size: 16pt; /* 더 커진 제목 폰트 */
    font-weight: bold;
    color: #E0E0E0; /* 황금색 강조 */
    padding-bottom: 5px;
}

/* 모든 푸시버튼 */
QPushButton {
    background-color: #4d4d4d; /* 강조 파란색 */
    border: none;
    border-radius: 8px; /* 둥근 모서리 */
    padding: 10px 20px; /* 패딩 증가 */
    color: white;
    font-size: 11pt;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #6d6d6d; /* 호버 시 더 밝은 파란색 */
}

QPushButton:pressed {
    background-color: #444444; /* 클릭 시 더 진한 파란색 */
}

QPushButton:disabled {
    background-color: #444444; /* 비활성화 시 어두운 회색 */
    color: #999999;
}

/* 리스트 위젯 (QListWidget) */
QListWidget {
    background-color: #2a2a2a; /* 리스트 배경색 - 메인 배경보다 약간 밝게 */
    border: 1px solid #4A4A66; /* 부드러운 테두리 */
    border-radius: 8px;
    padding: 5px;
    selection-background-color: #4d4d4d; /* 선택된 아이템 배경색 */
    selection-color: white;
}
/* 리스트 아이템 */
QListWidget::item {
    padding: 5px;
    border-bottom: 1px solid #616161; /* 아이템 사이 구분선 */
}
QListWidget::item:hover {
    background-color: #3A3A52; /* 호버 시 약간 밝게 */
}


/* 텍스트 에디트 (QTextEdit) */
QTextEdit {
    background-color: #2a2a2a; /* 텍스트 에디트 배경색 */
    border: 1px solid #4A4A66;
    border-radius: 8px;
    padding: 10px;
    color: #E0E0E0;
    /* line-height는 QSS에서 직접 지원하지 않아 C++ 속성을 사용해야 함 */
}

/* 프레임 또는 컨테이너 역할 위젯 */
QFrame {
    background-color: #2a2a2a;
    border: none;
    border-radius: 8px;
    padding: 10px;
}
QFrame#splitterWidget { /* splitter 안의 각 위젯 프레임 */
    background-color: #333333; /* 메인 배경과 동일 */
    border: none;
}


/* 체크박스 */
QCheckBox {
    spacing: 5px;
    color: #E0E0E0;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #5A5A72;
    border-radius: 4px;
    background-color: #2D2D44;
}
QCheckBox::indicator:checked {
    background-color: #3A82F7;
    border: 2px solid #3A82F7;
    /* image: url(./icons/check_white.png);  체크 아이콘 경로. 실제 파일 필요 */
    /* 아이콘이 없으면 아래 svg/ttf 아이콘 또는 단순 색상으로 대체 */
    /* image: url(some_check_icon_path.png); */ 
}
QCheckBox::indicator:disabled {
    background-color: #3A3A52;
    border: 2px solid #5A5A72;
}

/* 스크롤바 */
QScrollBar:vertical {
    background: #0f0f0f;
    width: 10px;
    margin: 0px 0px 0px 0px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #2f5ea1;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

/* QLabel 일반 스타일 */
QLabel {
    color: #B0B0B0; /* 보조 텍스트 색상 */
    padding: 2px;
}

/* 유사도 레이블에 대한 특별 스타일 */
QLabel#similarityLabel {
    font-weight: bold;
    font-size: 11pt;
    color: #90EE90; /* 기본 녹색, 유사도에 따라 색상 변경될 수 있음 */
}
"""

# --- 텍스트 추출 함수 ---
def extract_text_from_pdf(pdf_path):
    """PDF 파일에서 모든 텍스트를 추출합니다."""
    text_content = ""
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text_content += page.get_text()
        doc.close()
    except Exception as e:
        text_content = f"PDF 파일 처리 중 오류 발생: {e}"
    return text_content

# --- PDF 파일 리스트 아이템 위젯 (체크박스 포함) ---
class PDFFileItem(QWidget):
    def __init__(self, filename, loaded_datetime):
        super().__init__()
        layout = QHBoxLayout() # QHBoxLayout(self) 대신 이렇게 선언하고 self.setLayout()
        self.checkbox = QCheckBox()
        self.label_filename = QLabel(filename)
        self.label_date = QLabel(loaded_datetime.toString("yyyy-MM-dd HH:mm:ss"))
        self.label_date.setStyleSheet("color: #999999; font-size: 9pt;") # 날짜는 더 작게
        
        layout.addWidget(self.checkbox)
        layout.addWidget(self.label_filename)
        layout.addStretch() # filename과 date 사이 공간 확보
        layout.addWidget(self.label_date)
        layout.setContentsMargins(5, 2, 5, 2) # 내부 마진 조정
        self.setLayout(layout) # 레이아웃을 위젯에 설정

    def is_checked(self):
        return self.checkbox.isChecked()
    
    # 이 위젯 자체의 선호 크기 (setSizeHint용)
    def sizeHint(self):
        return QSize(200, 30) # 적절한 크기 명시 (텍스트 길이에 따라 조절 가능)


# --- 문단 리스트 아이템 위젯 (표절율 포함) ---
class ParagraphListItem(QWidget):
    """
    PDF 문단 리스트 속 각 항목을 표현하는 커스텀 위젯.
    문단 텍스트와 표절률을 체크박스(옵션)와 함께 보여줍니다.
    """
    def __init__(self, paragraph_text_preview, plagiarism_rate=0.0):
        super().__init__()
        layout = QHBoxLayout() # QHBoxLayout(self) 대신 이렇게 선언하고 self.setLayout()
        # self.checkbox = QCheckBox() # 필요시 체크박스 추가
        self.text_label = QLabel(paragraph_text_preview)
        self.text_label.setWordWrap(True) # 텍스트가 길 경우 줄바꿈
        self.rate_label = QLabel(f"{plagiarism_rate*100:.1f}%")
        self.rate_label.setMinimumWidth(50) # 표절률 레이블 최소 너비 지정
        self.rate_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) # 우측 정렬

        # 표절률에 따른 색상 설정 (다크 모드에 맞는 색상)
        color = QColor("#90EE90")  # 기본 연녹색 (낮음)
        if plagiarism_rate >= 0.8:
            color = QColor("#FF4444")  # 빨강 (높음)
        elif plagiarism_rate >= 0.5:
            color = QColor("#FFA500")  # 주황 (중간)

        palette = self.rate_label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, color)
        self.rate_label.setPalette(palette)
        self.rate_label.setStyleSheet("font-weight: bold; font-size: 10pt;") # 글씨 크기

        # layout.addWidget(self.checkbox) # 필요시 체크박스 추가
        layout.addWidget(self.text_label)
        layout.addStretch() # 텍스트와 표절률 사이에 공간 확보
        layout.addWidget(self.rate_label)
        layout.setContentsMargins(5, 5, 5, 5) # 위젯 내부 패딩 조정
        self.setLayout(layout) # 레이아웃을 위젯에 설정
    
    # 이 위젯 자체의 선호 크기 (setSizeHint용)
    def sizeHint(self):
        # 텍스트 길이에 따라 높이를 조절해야 하지만, 간단히 고정 높이 지정
        # QListWidgetItem의 텍스트가 길면 자동으로 늘어나므로 이 부분은 상황에 따라 복잡해질 수 있음
        return QSize(200, 40) 

    # 표절률 업데이트 및 색상 재적용 메서드
    def set_plagiarism_rate(self, rate):
        self.rate_label.setText(f"{rate*100:.1f}%")
        color = QColor("#90EE90")
        if rate >= 0.8:
            color = QColor("#FF4444")
        elif rate >= 0.5:
            color = QColor("#FFA500")
        palette = self.rate_label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, color)
        self.rate_label.setPalette(palette)

# 분석 작업을 백그라운드에서 실행하기 위한 워커 쓰레드
class AnalysisWorker(QThread):
    # 분석 완료 시 결과 데이터, 타겟 ID, 파일명을 메인 쓰레드로 전달하는 신호
    finished = pyqtSignal(list, int, str)

    def __init__(self, analyzer, target_pdf_id, file_name_only, files_data):
        super().__init__()
        self.analyzer = analyzer
        self.target_pdf_id = target_pdf_id
        self.file_name_only = file_name_only
        self.files_data = files_data

    def run(self):
        # 여기가 실질적으로 시간이 오래 걸리는 작업 (백그라운드 실행)
        results = self.analyzer.analyze_similarity(self.target_pdf_id, self.files_data)
        self.finished.emit(results, self.target_pdf_id, self.file_name_only)

# --- 메인 윈도우 클래스 ---
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SimiDoc - PDF 유사도 분석기")
        self.resize(1300, 800) # 창 크기 더 넓고 높게 조정
        QApplication.instance().setStyleSheet(dark_style) # 어플리케이션 전체에 스타일 적용

        # SQLite 데이터베이스 초기화
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(script_dir, "simidoc.db")
        
        # --- DB 초기화 성공 여부 확인 추가 (오류 발생 시 프로그램 종료) ---
        if not self._init_database():
            # DB 초기화 실패 시 QApplication 종료
            sys.exit(1)
        # -----------------------------------------------------------------

        self.files_data = [] # 데이터베이스에서 로드될 파일 정보를 저장할 리스트
        self.analyzer = similarity_analyzer.SimilarityAnalyzer(self.db_path) # 유사도 분석기 초기화

        # 각 PDF 문단별 최고 표절률을 저장하는 캐시 (분석 완료 후에 채워짐)
        # key: (pdf_id, paragraph_order_in_pdf), value: highest_plagiarism_score
        self._cached_paragraph_plagiarism_rates = {}
        # 현재 선택된 PDF의 ID (이 ID의 문단에 대한 표절률이 캐시되었음을 알림)
        self._cached_pdf_id = None
        print(f"DEBUG(GUI Init): _cached_pdf_id={self._cached_pdf_id}, _cached_paragraph_plagiarism_rates={len(self._cached_paragraph_plagiarism_rates)}")


        main_layout = QVBoxLayout() # MainWindow의 메인 레이아웃

        # 상단 제목 레이블
        title = QLabel("SimiDoc - PDF 문서 유사도 분석")
        title.setObjectName("titleLabel") # QSS에서 사용할 Object Name 설정
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # 주요 3단 분할기
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("mainSplitter") # QSS 적용을 위한 object name
        splitter.setContentsMargins(10, 0, 10, 10) # 분할기 바깥 여백

        # --- 좌측 패널 (PDF 파일 리스트) ---
        left_widget = QFrame() # QFrame을 사용하여 QSS border-radius 적용
        left_widget.setObjectName("splitterWidget")
        left_layout = QVBoxLayout() # <--- 수정됨: QVBoxLayout()만 사용
        left_layout.addWidget(QLabel("📂 PDF 파일 목록"))
        self.file_list_widget = QListWidget()
        left_layout.addWidget(self.file_list_widget)
        
        # 좌측 하단 버튼들 (삭제, 불러오기)
        left_buttons_layout = QHBoxLayout()
        self.btn_load = QPushButton("➕ 파일 불러오기")
        self.btn_delete = QPushButton("🗑️ 선택 파일 삭제")
        left_buttons_layout.addWidget(self.btn_load)
        left_buttons_layout.addWidget(self.btn_delete)
        left_layout.addLayout(left_buttons_layout)
        
        left_widget.setLayout(left_layout) # <--- 수정됨: QFrame에 레이아웃 명시적 설정
        splitter.addWidget(left_widget)


        # --- 중앙 패널 (선택된 PDF의 문단 리스트) ---
        center_widget = QFrame()
        center_widget.setObjectName("splitterWidget")
        center_layout = QVBoxLayout() # <--- 수정됨: QVBoxLayout()만 사용
        center_layout.addWidget(QLabel("📝 선택된 PDF 문단 목록"))
        self.paragraph_list_widget = QListWidget() # 문단 리스트 위젯
        center_layout.addWidget(self.paragraph_list_widget)
        
        center_widget.setLayout(center_layout) # <--- 수정됨: QFrame에 레이아웃 명시적 설정
        splitter.addWidget(center_widget)


        # --- 우측 패널 (상세 문단 내용 및 유사도 결과) ---
        right_widget = QFrame()
        right_widget.setObjectName("splitterWidget")
        right_layout = QVBoxLayout() # <--- 수정됨: QVBoxLayout()만 사용
        right_layout.addWidget(QLabel("🔍 유사도 분석 결과 및 상세 내용"))
        
        # 상세 문단 내용 (중앙 리스트에서 선택 시)
        self.text_details = QTextEdit() 
        self.text_details.setReadOnly(True)
        self.text_details.setPlaceholderText("중앙 목록에서 문단을 선택하면 원문 내용을 볼 수 있습니다.")
        right_layout.addWidget(self.text_details)

        right_layout.addWidget(QLabel("📊 타겟 문단과 유사 문단 비교 결과"))
        self.text_comparison = QTextEdit() # 유사도 분석 결과 표시
        self.text_comparison.setReadOnly(True)
        self.text_comparison.setPlaceholderText("왼쪽 PDF 파일을 선택하고 '✨ 분석하기' 버튼을 누르면 유사도 결과가 여기에 표시됩니다.")
        self.text_comparison.setMaximumHeight(250) # 비교 결과 창 높이 제한
        right_layout.addWidget(self.text_comparison)
        
        # 우측 하단 버튼 (분석하기, 비교문서보기)
        right_buttons_layout = QHBoxLayout()
        self.btn_analyze = QPushButton("✨ 분석하기")
        self.btn_compare_view = QPushButton("📄 비교 문서 보기") # 새롭게 추가될 버튼
        right_buttons_layout.addWidget(self.btn_analyze)
        right_buttons_layout.addWidget(self.btn_compare_view)
        right_layout.addLayout(right_buttons_layout)
        
        right_widget.setLayout(right_layout) # <--- 수정됨: QFrame에 레이아웃 명시적 설정
        splitter.addWidget(right_widget)
        
        splitter.setSizes([300, 400, 600]) # 초기 너비 비율 설정 (px 단위 아님, 총 합은 1300 정도)

        main_layout.addWidget(splitter) # 메인 레이아웃에 분할기 추가
        self.setLayout(main_layout) # <--- MainWindow의 최종 레이아웃 설정


        # --- 이벤트 연결 ---
        self.btn_load.clicked.connect(self.load_pdfs)
        self.btn_delete.clicked.connect(self.delete_selected_files)
        self.file_list_widget.currentItemChanged.connect(self._on_pdf_selection_changed) # PDF 선택 시
        self.paragraph_list_widget.currentItemChanged.connect(self._on_paragraph_selection_changed) # 문단 선택 시
        self.btn_analyze.clicked.connect(self.analyze_selected_file)
        self.btn_compare_view.clicked.connect(self._open_compare_view) # 비교문서보기 버튼 연결

        # 모든 GUI 컴포넌트가 생성된 후, DB에서 파일 목록을 GUI에 로드합니다.
        self._load_files_from_db()


    # --- DB 및 내부 유틸리티 함수 ---
    def _init_database(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pdfs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    loaded_date TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS paragraphs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pdf_id INTEGER NOT NULL,
                    paragraph_text TEXT NOT NULL,
                    page_number INTEGER,
                    FOREIGN KEY (pdf_id) REFERENCES pdfs (id) ON DELETE CASCADE
                )
            ''')
            conn.commit()
            return True # 성공적으로 초기화되면 True 반환
        except sqlite3.Error as e:
            QMessageBox.critical(self, "데이터베이스 오류", f"데이터베이스 초기화 중 오류 발생: {e}\n경로: {self.db_path}")
            return False # 실패하면 False 반환
        finally:
            if conn:
                conn.close()

    def _load_files_from_db(self):
        self.file_list_widget.clear()
        self.files_data = [] # 내부 데이터 캐시도 초기화

        # --- 캐시 변수 초기화 (수정 없음) ---
        self._cached_paragraph_plagiarism_rates = {} # 표절률 캐시 초기화
        self._cached_pdf_id = None # 캐시된 PDF ID 초기화
        # --- 디버그 메시지 추가 ---
        print(f"DEBUG(LoadDB): Cache initialized. _cached_pdf_id={self._cached_pdf_id}, rates={len(self._cached_paragraph_plagiarism_rates)}")
        
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, file_path, file_name, loaded_date FROM pdfs ORDER BY id DESC")
            files_in_db = cursor.fetchall()
            
            for pdf_id, file_path, file_name, loaded_date_str in files_in_db:
                if not os.path.exists(file_path):
                    print(f"DEBUG(LoadDB): File '{file_path}' not found. Deleting from DB.") # 디버그
                    self._delete_pdf_from_db(pdf_id)
                    continue
                
                loaded_dt = QDateTime.fromString(loaded_date_str, "yyyy-MM-dd HH:mm:ss")
                self.files_data.append({"id": pdf_id, "filename": file_path, "loaded_dt": loaded_dt, "file_name_only": file_name})

                item_widget = PDFFileItem(file_name, loaded_dt)
                list_item = QListWidgetItem(self.file_list_widget)
                list_item.setSizeHint(item_widget.sizeHint()) 
                self.file_list_widget.addItem(list_item)
                self.file_list_widget.setItemWidget(list_item, item_widget)
            
            print(f"DEBUG(LoadDB): Loaded {len(self.files_data)} files into GUI.") # 디버그
        except sqlite3.Error as e:
            QMessageBox.warning(self, "데이터베이스 로드 오류", f"기존 파일을 불러오는 중 오류 발생: {e}\n경로: {self.db_path}")
        finally:
            if conn: conn.close()

    def _add_pdf_to_db(self, file_path):
        conn = None
        pdf_id = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            file_name_only = os.path.basename(file_path)
            loaded_date = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")

            cursor.execute("SELECT id FROM pdfs WHERE file_path = ?", (file_path,))
            if cursor.fetchone():
                QMessageBox.warning(self, "파일 중복", f"'{file_name_only}' 파일은 이미 추가되었습니다.")
                return None

            cursor.execute("INSERT INTO pdfs (file_path, file_name, loaded_date) VALUES (?, ?, ?)",
                           (file_path, file_name_only, loaded_date))
            pdf_id = cursor.lastrowid
            print(f"DEBUG(AddDB): Added file '{file_name_only}' with new PDF ID: {pdf_id}") # 디버그

            text_content = extract_text_from_pdf(file_path)
            paragraphs = self._split_text_into_paragraphs(text_content)
            print(f"DEBUG(AddDB): Extracted {len(paragraphs)} paragraphs from '{file_name_only}'.") # 디버그

            for i, para_text in enumerate(paragraphs):
                if para_text.strip(): 
                    cursor.execute("INSERT INTO paragraphs (pdf_id, paragraph_text, page_number) VALUES (?, ?, ?)",
                                   (pdf_id, para_text.strip(), i + 1))
            conn.commit()
            return pdf_id
        except sqlite3.Error as e:
            QMessageBox.critical(self, "데이터 저장 오류", f"PDF 데이터를 데이터베이스에 저장하는 중 오류 발생: {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn: conn.close()

    def _delete_pdf_from_db(self, pdf_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # [수정] 외래키 설정(CASCADE)에 의존하지 않고, 명시적으로 문단 데이터를 먼저 삭제.
            # 고아 데이터가 남는 문제 방지가능.
            cursor.execute("DELETE FROM paragraphs WHERE pdf_id = ?", (pdf_id,))
            
            # 그 다음 PDF 파일 정보를 삭제합니다.
            cursor.execute("DELETE FROM pdfs WHERE id = ?", (pdf_id,))
            
            conn.commit()
            print(f"DEBUG(DeleteDB): Deleted PDF and its paragraphs with ID: {pdf_id}")
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "데이터 삭제 오류", f"데이터베이스에서 PDF를 삭제하는 중 오류 발생: {e}")
        finally:
            if conn: conn.close()

    def _get_paragraphs_for_pdf(self, pdf_id):
        paragraphs = []
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT paragraph_text FROM paragraphs WHERE pdf_id = ? ORDER BY page_number ASC", (pdf_id,))
            for row in cursor.fetchall():
                paragraphs.append(row[0])
            print(f"DEBUG(GetParas): Fetched {len(paragraphs)} paragraphs for PDF ID: {pdf_id}") # 디버그
        except sqlite3.Error as e:
            QMessageBox.critical(self, "데이터 불러오기 오류", f"문단을 데이터베이스에서 불러오는 중 오류 발생: {e}")
        finally:
            if conn: conn.close()
        return paragraphs

    def _split_text_into_paragraphs(self, text):
        paragraphs = []
        text = text.strip()
        text = text.replace('ㅡ', '')
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'([^\n.?!])\n([^\n])', r'\1 \2', text)
        text = re.sub(r'([.?!])([ㄱ-ㅎㅏ-ㅣ가-힣])', r'\1 \2', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text).strip()
        
        raw_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        MAX_PARA_LENGTH = 400
        MIN_SENTENCE_LENGTH = 10

        final_paragraphs = []

        for raw_para in raw_paragraphs:
            raw_para = re.sub(r'(?<!\')([,])(?!\')', r'\1 ', raw_para)
            raw_para = re.sub(r'([.?!])', r'\1 ', raw_para)
            raw_para = re.sub(r'\s+', ' ', raw_para).strip()

            sentences = re.split(r'(?<=[.?!”])\s*(?=[ㄱ-ㅎㅏ-ㅣ가-힣A-Za-z”])', raw_para) # 수정된 정규식
            sentences = [s.strip() for s in sentences if len(s.strip()) > MIN_SENTENCE_LENGTH] 
            
            current_paragraph_buffer = []
            current_paragraph_length = 0

            for sentence in sentences:
                if current_paragraph_length + len(sentence) + 1 <= MAX_PARA_LENGTH:
                    current_paragraph_buffer.append(sentence)
                    current_paragraph_length += len(sentence) + 1
                else:
                    if current_paragraph_buffer:
                        final_paragraphs.append(" ".join(current_paragraph_buffer))
                    current_paragraph_buffer = [sentence]
                    current_paragraph_length = len(sentence) + 1

            if current_paragraph_buffer:
                final_paragraphs.append(" ".join(current_paragraph_buffer))
        
        return final_paragraphs

    # --- GUI 이벤트 핸들러 ---
    def load_pdfs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "PDF 파일 선택", "", "PDF Files (*.pdf)")
        if not files: return
        
        for f in files:
            self._add_pdf_to_db(f)
        
        self._load_files_from_db() # 파일 목록 갱신 (캐시도 초기화됨)
        print(f"DEBUG(LoadPDFs): Files loaded. Cache after load: _cached_pdf_id={self._cached_pdf_id}, rates={len(self._cached_paragraph_plagiarism_rates)}")


    def delete_selected_files(self):
        pdf_ids_to_delete_from_db = []
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            item_widget = self.file_list_widget.itemWidget(item)
            if item_widget and item_widget.is_checked():
                if i < len(self.files_data):
                    pdf_ids_to_delete_from_db.append(self.files_data[i]["id"])

        if not pdf_ids_to_delete_from_db:
            QMessageBox.information(self, "선택 없음", "삭제할 파일을 선택해주세요.")
            return

        reply = QMessageBox.question(self, "삭제 확인", "선택된 PDF 파일을 삭제하시겠습니까? 데이터베이스에서도 삭제됩니다.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for pdf_id in pdf_ids_to_delete_from_db:
                self._delete_pdf_from_db(pdf_id)
            
            # DB 삭제 후 GUI 및 캐시 초기화/재로드
            self._load_files_from_db() # 캐시 초기화는 이 함수에서 수행됨
            self.paragraph_list_widget.clear() 
            self.text_details.clear()
            self.text_comparison.clear()
            QMessageBox.information(self, "삭제 완료", "선택된 PDF 파일이 삭제되었습니다.")
            print(f"DEBUG(Delete): After deletion, _cached_pdf_id={self._cached_pdf_id}, rates={len(self._cached_paragraph_plagiarism_rates)}")


    def _on_pdf_selection_changed(self, current_item, previous_item):
        """PDF 리스트에서 항목 선택 시 중앙에 해당 PDF의 문단들을 로드합니다."""
        self.paragraph_list_widget.clear() # 기존 문단 목록 초기화
        self.text_details.clear() # 상세 내용 초기화
        # self.text_comparison.clear() # PDF 선택만으로 유사도 결과가 사라지게 할지 유지할지는 UX에 따라

        if current_item is None:
            # 선택 해제 시 관련 캐시도 초기화
            self._cached_pdf_id = None # 선택된 PDF가 없어지면 분석된 PDF ID도 초기화
            self._cached_paragraph_plagiarism_rates = {} # 관련 캐시도 초기화
            print(f"DEBUG(SelectPDF): Selection cleared. Cache reset: _cached_pdf_id={self._cached_pdf_id}, rates={len(self._cached_paragraph_plagiarism_rates)}")
            return

        selected_pdf_index = self.file_list_widget.row(current_item)

        if selected_pdf_index >= 0 and selected_pdf_index < len(self.files_data):
            selected_pdf_id = self.files_data[selected_pdf_index]["id"]
            paragraphs = self._get_paragraphs_for_pdf(selected_pdf_id) # DB에서 문단들 가져오기
            
            # 현재 캐시된 표절률이 방금 선택한 PDF에 대한 것인지 확인
            is_current_pdf_analyzed = (self._cached_pdf_id == selected_pdf_id)
            print(f"DEBUG(SelectPDF): Selected PDF ID: {selected_pdf_id}. Cached PDF ID: {self._cached_pdf_id}. Is Analyzed? {is_current_pdf_analyzed}. Num Paras in cache: {len(self._cached_paragraph_plagiarism_rates)}")


            for i, para_text in enumerate(paragraphs):
                plagiarism_rate = 0.0
                if is_current_pdf_analyzed:
                    # 분석 결과가 캐시되어 있으면 해당 문단의 표절률 가져오기
                    # 캐시 키는 (pdf_id, paragraph_order)
                    plagiarism_rate = self._cached_paragraph_plagiarism_rates.get((selected_pdf_id, i + 1), 0.0)
                    print(f"DEBUG(SelectPDF): Para ({selected_pdf_id}, {i+1}) rate from cache: {plagiarism_rate}") # 캐시 사용 여부 확인
                
                para_preview = para_text[:150].replace('\n', ' ') # 미리보기 텍스트
                if len(para_text) > 150: para_preview += '...'
                
                # ParagraphListItem 위젯 생성 및 QListWidget에 추가
                item_widget = ParagraphListItem(f"[{i+1}] {para_preview}", plagiarism_rate)
                list_item = QListWidgetItem(self.paragraph_list_widget) # item을 listwidget에 직접 연결
                list_item.setSizeHint(item_widget.sizeHint())
                self.paragraph_list_widget.setItemWidget(list_item, item_widget)
        else:
            self.paragraph_list_widget.addItem("PDF 문단 정보를 불러올 수 없습니다.")


    def _on_paragraph_selection_changed(self, current_item, previous_item):
        """문단 리스트에서 항목 선택 시 우측 상단에 해당 문단 상세 내용을 표시합니다."""
        self.text_details.clear() # 상세 내용 초기화

        if current_item is None:
            return
        
        # 선택된 문단의 전체 텍스트 가져오기
        item_widget = self.paragraph_list_widget.itemWidget(current_item)
        
        if item_widget and isinstance(item_widget, ParagraphListItem):
            selected_para_text_preview = item_widget.text_label.text() # ParagraphListItem 위젯의 텍스트 레이블에서 텍스트 가져오기
            
            current_pdf_item = self.file_list_widget.currentItem()
            if current_pdf_item:
                selected_pdf_index = self.file_list_widget.row(current_pdf_item)
                if selected_pdf_index >= 0 and selected_pdf_index < len(self.files_data):
                    pdf_id = self.files_data[selected_pdf_index]["id"]
                    all_paragraphs_of_pdf = self._get_paragraphs_for_pdf(pdf_id)
                    
                    try:
                        # "[1] 텍스트..." 에서 1을 추출
                        para_idx_match = re.match(r'\[(\d+)\]', selected_para_text_preview)
                        if para_idx_match:
                            para_index_in_list = int(para_idx_match.group(1)) - 1 # 리스트 인덱스로 변환
                            if 0 <= para_index_in_list < len(all_paragraphs_of_pdf):
                                self.text_details.setPlainText(f"--- 선택 문단 상세 ---\n\n"
                                                               f"[{para_index_in_list+1}] {all_paragraphs_of_pdf[para_index_in_list]}")
                            else:
                                self.text_details.setPlainText("문단 상세 내용을 불러올 수 없습니다: (인덱스 오류)")
                        else:
                            self.text_details.setPlainText("문단 상세 내용을 불러올 수 없습니다: (형식 오류)")
                    except Exception as e:
                         self.text_details.setPlainText(f"문단 상세 내용을 불러오는 중 오류 발생: {e}")
                else:
                     self.text_details.setPlainText("PDF가 선택되지 않았거나 PDF 정보 오류입니다.")
            else:
                 self.text_details.setPlainText("PDF가 선택되지 않았습니다.")
        else:
             self.text_details.setPlainText("선택된 문단의 위젯이 올바르지 않습니다.")


    def analyze_selected_file(self):
        current_item = self.file_list_widget.currentItem()
        if current_item is None:
            self.text_comparison.setPlainText("분석할 PDF 파일을 먼저 왼쪽 목록에서 선택해주세요.")
            return
        
        selected_pdf_index = self.file_list_widget.row(current_item)
        
        if selected_pdf_index >= 0 and selected_pdf_index < len(self.files_data):
            target_pdf_id = self.files_data[selected_pdf_index]["id"]
            file_name_only = self.files_data[selected_pdf_index]["file_name_only"]

            # 1. UI 최적화: 사용자가 기다리는 동안 피드백 제공
            self.text_comparison.setPlainText(f"⏳ '{file_name_only}' 파일 분석 중...\n(잠시만 기다려주세요...)")
            self.btn_analyze.setEnabled(False) # 중복 실행 방지
            self.btn_analyze.setText("분석 중...") 

            # 2. 성능 최적화: 워커 쓰레드 생성 및 실행 (GUI 멈춤 방지)
            self.worker = AnalysisWorker(self.analyzer, target_pdf_id, file_name_only, self.files_data)
            self.worker.finished.connect(self.on_analysis_complete) # 작업이 끝나면 실행될 함수 연결
            self.worker.start()

        else:
            self.text_comparison.setPlainText("선택된 파일이 올바르지 않습니다.")

    # [추가] 쓰레드 작업이 완료되었을 때 호출되는 함수 (결과 화면 표시)
    def on_analysis_complete(self, analysis_results, target_pdf_id, file_name_only):
        self.btn_analyze.setEnabled(True) # 버튼 다시 활성화
        self.btn_analyze.setText("✨ 분석하기")

        # 캐시 업데이트 (기존 로직 재사용)
        self._cached_pdf_id = target_pdf_id
        self._cached_paragraph_plagiarism_rates = {} 
        for res in analysis_results:
            target_para_order = res['target_paragraph'][2]
            # 리스트 컴프리헨션 최적화
            scores = [sp['similarity'] for sp in res['similar_paragraphs']]
            highest_score = max(scores) if scores else 0.0
            self._cached_paragraph_plagiarism_rates[(target_pdf_id, target_para_order)] = highest_score
        
        # 결과 텍스트 생성 (HTML)
        if not analysis_results:
            self.text_comparison.setPlainText(f"'{file_name_only}'에 대한 유사도 분석 결과가 없습니다.")
        else:
            result_lines = [f"--- '{file_name_only}' 유사도 분석 결과 ---\n"]
            
            for res in analysis_results:
                t_order = res['target_paragraph'][2]
                t_text = res['target_paragraph'][1][:100]
                score = self._cached_paragraph_plagiarism_rates.get((target_pdf_id, t_order), 0.0)

                # 색상 결정 로직 간소화
                color = "#FF4444" if score >= 0.8 else "#FFA500" if score >= 0.5 else "#90EE90"
                
                result_lines.append(
                    f"▪️ 타겟 문단 [{t_order}] "
                    f"(<span style='color:{color}; font-weight:bold;'>표절율: {score*100:.0f}%</span>): "
                    f"{t_text}...\n"
                )
                
                if res['similar_paragraphs']:
                    for sim in res['similar_paragraphs']:
                        s_id = sim['source_pdf_id']
                        # 파일명 찾기 최적화 (generator expression)
                        s_name = next((f["file_name_only"] for f in self.files_data if f["id"] == s_id), "알 수 없음")
                        s_order = sim['source_paragraph'][2]
                        s_text = sim['source_paragraph'][1][:100]
                        sim_score = sim['similarity']
                        
                        sim_color = "#90EE90" if sim_score > 0.8 else "#FFFF00" if sim_score > 0.5 else "#FF6347"
                        
                        result_lines.append(
                            f"  <span style='color:{sim_color}; font-weight:bold;'>[유사도: {sim_score:.2f}]</span> "
                            f"PDF '{s_name}' [{s_order}]: {s_text}...\n"
                        )
                else:
                    result_lines.append("  유사한 문단 없음.\n")
                
                result_lines.append("\n")
            
            self.text_comparison.setHtml("".join(result_lines))
        
        # 리스트 뷰 갱신 (표절율 색상 반영)
        current_pdf_item = self.file_list_widget.currentItem()
        if current_pdf_item:
            self._on_pdf_selection_changed(current_pdf_item, None)

    def _open_compare_view(self):
        """'비교 문서 보기' 버튼 클릭 시 실행될 함수 (현재는 더미)"""
        QMessageBox.information(self, "기능 예정", "이 기능은 추후 개발될 예정입니다! 😊")


# --- 메인 실행 블록 ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())