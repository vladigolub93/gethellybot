from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.interviews import InterviewAnswer, InterviewQuestion, InterviewSession


ACTIVE_INTERVIEW_STATES = ("INVITED", "ACCEPTED", "IN_PROGRESS")


class InterviewsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_session_by_match_id(self, match_id) -> Optional[InterviewSession]:
        stmt = select(InterviewSession).where(InterviewSession.match_id == match_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, session_id) -> Optional[InterviewSession]:
        stmt = select(InterviewSession).where(InterviewSession.id == session_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_active_session_for_candidate(self, candidate_profile_id) -> Optional[InterviewSession]:
        stmt = (
            select(InterviewSession)
            .where(
                InterviewSession.candidate_profile_id == candidate_profile_id,
                InterviewSession.state.in_(ACTIVE_INTERVIEW_STATES),
            )
            .order_by(InterviewSession.updated_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def create_session(
        self,
        *,
        match_id,
        candidate_profile_id,
        vacancy_id,
        state: str = "CREATED",
        expires_in_hours: int = 48,
        plan_json: Optional[dict] = None,
    ) -> InterviewSession:
        now = datetime.now(timezone.utc)
        row = InterviewSession(
            match_id=match_id,
            candidate_profile_id=candidate_profile_id,
            vacancy_id=vacancy_id,
            state=state,
            expires_at=now + timedelta(hours=expires_in_hours),
            plan_json=plan_json,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def create_question(
        self,
        *,
        session_id,
        order_no: int,
        question_text: str,
        question_kind: str = "primary",
        parent_question_id=None,
    ) -> InterviewQuestion:
        row = InterviewQuestion(
            session_id=session_id,
            order_no=order_no,
            question_text=question_text,
            question_kind=question_kind,
            parent_question_id=parent_question_id,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def set_total_questions(self, session: InterviewSession, total_questions: int) -> InterviewSession:
        session.total_questions = total_questions
        self.session.flush()
        return session

    def get_question_by_order(self, session_id, order_no: int) -> Optional[InterviewQuestion]:
        stmt = select(InterviewQuestion).where(
            InterviewQuestion.session_id == session_id,
            InterviewQuestion.order_no == order_no,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def shift_questions_from_order(self, session_id, start_order: int, delta: int = 1) -> None:
        stmt = (
            select(InterviewQuestion)
            .where(
                InterviewQuestion.session_id == session_id,
                InterviewQuestion.order_no >= start_order,
            )
            .order_by(InterviewQuestion.order_no.desc())
        )
        rows = list(self.session.execute(stmt).scalars().all())
        for row in rows:
            row.order_no += delta
        self.session.flush()

    def mark_question_asked(self, question: InterviewQuestion) -> InterviewQuestion:
        question.asked_at = datetime.now(timezone.utc)
        self.session.flush()
        return question

    def mark_question_answered(self, question: InterviewQuestion) -> InterviewQuestion:
        question.answered_at = datetime.now(timezone.utc)
        self.session.flush()
        return question

    def create_answer(
        self,
        *,
        session_id,
        question_id,
        raw_message_id=None,
        file_id=None,
        content_type: str,
        answer_text=None,
        transcript_text=None,
        is_follow_up_answer: bool = False,
    ) -> InterviewAnswer:
        row = InterviewAnswer(
            session_id=session_id,
            question_id=question_id,
            raw_message_id=raw_message_id,
            file_id=file_id,
            content_type=content_type,
            answer_text=answer_text,
            transcript_text=transcript_text,
            is_follow_up_answer=is_follow_up_answer,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_answers_for_session(self, session_id) -> list[InterviewAnswer]:
        stmt = select(InterviewAnswer).where(InterviewAnswer.session_id == session_id)
        return list(self.session.execute(stmt).scalars().all())

    def advance_question_pointer(self, session: InterviewSession, next_order: int) -> InterviewSession:
        session.current_question_order = next_order
        self.session.flush()
        return session

    def mark_invited(self, session: InterviewSession) -> InterviewSession:
        session.invited_at = datetime.now(timezone.utc)
        self.session.flush()
        return session

    def mark_accepted(self, session: InterviewSession) -> InterviewSession:
        session.accepted_at = datetime.now(timezone.utc)
        self.session.flush()
        return session

    def mark_started(self, session: InterviewSession) -> InterviewSession:
        session.started_at = datetime.now(timezone.utc)
        self.session.flush()
        return session

    def mark_completed(self, session: InterviewSession) -> InterviewSession:
        session.completed_at = datetime.now(timezone.utc)
        self.session.flush()
        return session
