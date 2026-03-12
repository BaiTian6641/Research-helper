"""CRUD for the local library database (local_library.db)."""

from __future__ import annotations

from src.storage.models import Paper, init_db
from sqlalchemy.orm import Session


class LibraryStore:
    """Separate SQLite database for user's local paper collection."""

    def __init__(self, db_path: str = "local_library.db"):
        self._session_factory = init_db(db_path)

    def _session(self) -> Session:
        return self._session_factory()

    def add_papers(self, papers: list[Paper]) -> int:
        new_count = 0
        with self._session() as session:
            for paper in papers:
                paper.is_local = True
                if not session.get(Paper, paper.id):
                    session.add(paper)
                    new_count += 1
            session.commit()
        return new_count

    def get_all_papers(self) -> list[Paper]:
        with self._session() as session:
            papers = list(session.query(Paper).all())
            for p in papers:
                session.expunge(p)
            return papers

    def search_papers(self, keyword: str, limit: int = 200) -> list[Paper]:
        with self._session() as session:
            papers = list(
                session.query(Paper)
                .filter(Paper.title.ilike(f"%{keyword}%"))
                .limit(limit)
                .all()
            )
            for p in papers:
                session.expunge(p)
            return papers

    def get_paper_count(self) -> int:
        with self._session() as session:
            return session.query(Paper).count()

    def delete_paper(self, paper_id: str) -> bool:
        with self._session() as session:
            paper = session.get(Paper, paper_id)
            if paper:
                session.delete(paper)
                session.commit()
                return True
            return False
