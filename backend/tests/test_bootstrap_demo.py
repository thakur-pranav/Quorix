"""bootstrap_demo: copies exactly one org into another database, re-runnably."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Chunk, ClusterMember, Conversation, Message, TopicCluster
from scripts.bootstrap_demo import copy_org
from tests.fakes import add_chunk


def seed(db: Session, org: str) -> None:
    add_chunk(db, f"chk_{org}_1", "refunds take five days", org)
    conversation = Conversation(organization_id=org, session_id=f"s-{org}", synthetic=True)
    message = Message(organization_id=org, role="customer", text="refund?", period="2026-11", confidence=0.6)
    conversation.messages.append(message)
    db.add(conversation)
    db.flush()
    topic = TopicCluster(organization_id=org, period="2026-11", name="Refunds", trend="baseline")
    topic.members = [ClusterMember(organization_id=org, message_id=message.id)]
    db.add(topic)
    db.commit()


def test_copies_one_org_with_vectors_and_can_run_again(db: Session, tmp_path: Path) -> None:
    seed(db, "org_demo")
    seed(db, "org_other")  # must stay behind
    target_url = f"sqlite:///{(tmp_path / 'prod.db').as_posix()}"
    target = create_engine(target_url)
    Base.metadata.create_all(target)

    first = copy_org("org_demo", target_url)
    assert first["chunks"] == first["messages"] == first["cluster_members"] == 1
    second = copy_org("org_demo", target_url)  # re-run: replaces, doesn't duplicate
    assert second == first

    with Session(target) as prod:
        assert prod.scalar(select(func.count()).select_from(Chunk)) == 1
        chunk = prod.scalars(select(Chunk)).one()
        assert chunk.organization_id == "org_demo" and len(chunk.embedding or []) == 384  # vector survived
        assert prod.scalars(select(Message.organization_id).distinct()).all() == ["org_demo"]
        member = prod.scalars(select(ClusterMember)).one()
        assert prod.get(Message, member.message_id) is not None  # links intact after renumbering
    target.dispose()
