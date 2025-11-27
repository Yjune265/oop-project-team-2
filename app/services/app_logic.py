# DB와 연동 가능한 형태로 리팩토링한 버전

from app.models.database import fetch_all, fetch_one, get_connection


class UserProfileManager:
    """
    사용자 설문 저장 및 프로필 저장을 담당하는 서비스 계층.
    DB의 user_profile 테이블과 연동됨.
    """

    def save_user_profile(self, data: dict):
        """
        사용자 프로필 저장 (예: 나이, 성별, 목표 등)
        data = { "user_id": 1, "age": 25, "gender": "F", ... }
        """
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO user_profile (user_id, age, gender, activity_level)
            VALUES (?, ?, ?, ?)
            """,
            [data.get("user_id"), data.get("age"), data.get("gender"), data.get("activity_level")]
        )

        conn.commit()
        conn.close()
        return True


    def save_survey_data(self, data: dict):
        """
        단계별 설문 저장
        data = { "user_id": 1, "sleep": "bad", "stress": "high", ... }
        """
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO survey (user_id, sleep_condition, stress_level, diet_pattern)
            VALUES (?, ?, ?, ?)
            """,
            [data.get("user_id"), data.get("sleep"), data.get("stress"), data.get("diet")]
        )

        conn.commit()
        conn.close()

        return data.get("user_id")


class RecommendationEngine:
    """
    사용자 설문 & DB 기반 영양제 추천 엔진
    supplements 테이블과 survey 테이블을 함께 참고
    """

    def __init__(self, user_id: int):
        self.user_id = user_id

    def _get_user_survey(self):
        query = "SELECT * FROM survey WHERE user_id = ? ORDER BY id DESC LIMIT 1"
        return fetch_one(query, [self.user_id])

    def _get_supplements_by_keyword(self, keyword: str):
        query = "SELECT * FROM supplements WHERE product_name LIKE ? LIMIT 10"
        return fetch_all(query, [f"%{keyword}%"])

    def recommend(self):
        """
        간단한 룰 기반 추천 (추후 알고리즘 확장 가능)
        """
        survey = self._get_user_survey()

        if not survey:
            return {"error": "설문 데이터가 없습니다."}

        rec_list = []

        # 예시 규칙 기반 추천
        if survey["stress_level"] == "high":
            rec_list += self._get_supplements_by_keyword("마그네슘")

        if survey["sleep_condition"] == "bad":
            rec_list += self._get_supplements_by_keyword("멜라토닌")

        if survey["diet_pattern"] == "poor":
            rec_list += self._get_supplements_by_keyword("비타민")

        return {
            "user_id": self.user_id,
            "survey_based_recommendations": rec_list
        }
