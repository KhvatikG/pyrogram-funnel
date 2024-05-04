import datetime
import enum

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base


class State(enum.Enum):
    new_user = 'new_user'
    msg1_sent = 'msg1_sent'
    msg2_sent = 'msg2_sent'
    msg2_skipped = 'msg2_skipped'
    msg3_sent = 'msg3_sent'


class Status(enum.Enum):
    alive = 'alive'
    dead = 'dead'
    finished = 'finished'


class User(Base):
    __tablename__ = 'users'

    state: Mapped[State] = mapped_column(
        nullable=False, default='new_user')

    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False, default=func.now())

    state_updated_at: Mapped[datetime.datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), nullable=False)

    status: Mapped[Status] = mapped_column(
        nullable=False, default='alive')
