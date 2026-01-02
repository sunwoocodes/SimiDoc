import sqlite3
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse.linalg import norm as sparse_norm # <-- scipy.sparse.linalg에서 norm 함수 임포트!

class SimilarityAnalyzer:
    """
    SimiDoc의 핵심: PDF 문단 간의 유사도를 분석하는 클래스.
    TF-IDF 벡터화와 코사인 유사도를 사용하여 문단별 유사도를 계산합니다.
    """
    def __init__(self, db_path):
        self.db_path = db_path
        self.paragraphs = [] 
        self.pdf_paragraph_map = {} 

    def _get_all_paragraphs_from_db(self):
        """데이터베이스에서 모든 문단 정보를 불러옵니다."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, pdf_id, paragraph_text, page_number FROM paragraphs ORDER BY pdf_id, page_number ASC")
            all_db_paragraphs = cursor.fetchall()
            
            self.paragraphs = [] 
            self.pdf_paragraph_map = {} 

            for para_id, pdf_id, text, order in all_db_paragraphs:
                self.paragraphs.append((para_id, pdf_id, text, order))
                if pdf_id not in self.pdf_paragraph_map:
                    self.pdf_paragraph_map[pdf_id] = []
                self.pdf_paragraph_map[pdf_id].append((para_id, text, order))
            
        except sqlite3.Error as e:
            print(f"ERROR(DB): 데이터베이스에서 문단 불러오기 오류: {e}")
            self.paragraphs = [] 
            self.pdf_paragraph_map = {}
        finally:
            if conn:
                conn.close()
        return self.paragraphs, self.pdf_paragraph_map

    def analyze_similarity(self, target_pdf_id, files_data):
        all_paragraphs, pdf_paragraph_map = self._get_all_paragraphs_from_db()

        if not all_paragraphs:
            return [] 

        texts_for_vectorization = [p[2] for p in all_paragraphs]
        
        if not texts_for_vectorization:
            return []

        try:
            self.vectorizer = TfidfVectorizer() 
            self.paragraph_vectors = self.vectorizer.fit_transform(texts_for_vectorization)

            # 2. 모든 벡터가 0 벡터가 되어버리는 경우를 처리합니다.
            if self.paragraph_vectors.shape[1] == 0:
                 print("DEBUG: TfidfVectorizer extracted no features. All similarities will be 0.")
                 results = []
                 for _, (target_para_id, target_para_text, target_para_order) in enumerate(pdf_paragraph_map.get(target_pdf_id, [])):
                     results.append({
                         'target_paragraph': (target_para_id, target_para_text, target_para_order),
                         'similar_paragraphs': [] 
                     })
                 return results

            # 3. 추가적인 방어 로직: 총 비교 가능한 문단 수가 1개 이하일 경우.
            if len(all_paragraphs) <= 1:
                print("DEBUG: Only 1 or 0 paragraphs available in total. All similarities will be 0.")
                results = []
                for _, (target_para_id, target_para_text, target_para_order) in enumerate(pdf_paragraph_map.get(target_pdf_id, [])):
                     results.append({
                         'target_paragraph': (target_para_id, target_para_text, target_para_order),
                         'similar_paragraphs': [] 
                     })
                return results

        except Exception as e:
            print(f"ERROR(Analyze): TF-IDF vectorization failed: {e}")
            return []

        results = []
        target_paragraphs_info = pdf_paragraph_map.get(target_pdf_id, [])

        if not target_paragraphs_info:
            return []

        # 타겟 PDF의 각 문단을 순회하며 유사도 분석
        for _, (target_para_id, target_para_text, target_para_order) in enumerate(target_paragraphs_info):
            full_list_target_para_idx = -1
            for i, (para_id, pdf_id, text, order) in enumerate(all_paragraphs):
                if para_id == target_para_id:
                    full_list_target_para_idx = i
                    break

            if full_list_target_para_idx == -1:
                continue

            target_vector = self.paragraph_vectors[full_list_target_para_idx]

            similar_paragraphs_for_target = []
            
            # 모든 문단 벡터와 비교
            for other_para_index in range(self.paragraph_vectors.shape[0]):
                # 현재 순회 중인 '비교 대상 문단'이 '타겟 문단 자신'과 완전히 동일한 경우 비교를 건너뜁니다.
                if other_para_index == full_list_target_para_idx:
                    continue
                
                other_vector = self.paragraph_vectors[other_para_index]
                
                # --- !!! 핵심 수정 지점 !!! ---
                # sparse_norm(벡터)이 0인 경우 (즉, 0 벡터)를 확인합니다.
                if sparse_norm(target_vector) == 0 or sparse_norm(other_vector) == 0:
                    similarity = 0.0
                else:
                    similarity = cosine_similarity(target_vector, other_vector)[0][0]
                # ------------------------------

                if similarity > 0.0:
                    similar_paragraphs_for_target.append({
                        'source_pdf_id': all_paragraphs[other_para_index][1],
                        'source_paragraph': (all_paragraphs[other_para_index][0], all_paragraphs[other_para_index][2], all_paragraphs[other_para_index][3]),
                        'similarity': similarity
                    })
            
            similar_paragraphs_for_target.sort(key=lambda x: x['similarity'], reverse=True)
            
            results.append({
                'target_paragraph': (target_para_id, target_para_text, target_para_order),
                'similar_paragraphs': similar_paragraphs_for_target[:5] 
            })
        
        return results