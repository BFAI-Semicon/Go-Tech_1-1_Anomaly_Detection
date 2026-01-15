from __future__ import annotations

from abc import ABC, abstractmethod


class RateLimitPort(ABC):
    @abstractmethod
    def increment_submission(self, user_id: str) -> int:
        """指定ユーザーの提出カウンターをインクリメントし、現在値を返す"""
        ...

    @abstractmethod
    def get_submission_count(self, user_id: str) -> int:
        """指定ユーザーの提出カウンターを取得"""
        ...

    @abstractmethod
    def decrement_submission(self, user_id: str) -> int:
        """指定ユーザーの提出カウンターをデクリメントし、現在値を返す"""
        ...

    @abstractmethod
    def try_increment_submission(self, user_id: str, max_count: int) -> bool:
        """指定ユーザーの提出カウンターをアトミックにチェック＆インクリメント

        現在のカウントが max_count 未満の場合のみインクリメントし、Trueを返す。
        max_count 以上の場合はインクリメントせず、Falseを返す。
        """
        ...
