"""Tests for ConfirmationBroker — deferred write confirmation."""
from __future__ import annotations

import asyncio

import pytest

from edu_cloud.ai.engine.confirmation_broker import ConfirmationBroker


def test_request_creates_pending():
    broker = ConfirmationBroker()
    pc = broker.request_confirmation("call_1", "update_score", {"score": 92})
    assert not pc.resolved
    assert not pc.approved
    assert len(broker.get_pending()) == 1


def test_approve_resolves():
    broker = ConfirmationBroker()
    broker.request_confirmation("call_1", "update_score", {"score": 92})
    broker.approve("call_1")
    pending = broker.get_pending()
    assert len(pending) == 0


def test_deny_resolves():
    broker = ConfirmationBroker()
    pc = broker.request_confirmation("call_1", "update_score", {"score": 92})
    broker.deny("call_1")
    assert pc.resolved
    assert not pc.approved


def test_auto_approve():
    broker = ConfirmationBroker(auto_approve=True)
    pc = broker.request_confirmation("call_1", "update_score", {"score": 92})
    assert pc.resolved
    assert pc.approved


@pytest.mark.asyncio
async def test_wait_for_approval():
    broker = ConfirmationBroker()
    broker.request_confirmation("call_1", "update_score", {"score": 92})

    async def approve_later():
        await asyncio.sleep(0.05)
        broker.approve("call_1")

    task = asyncio.create_task(approve_later())
    approved = await broker.wait_for_resolution("call_1")
    assert approved
    await task


@pytest.mark.asyncio
async def test_wait_timeout_denies():
    broker = ConfirmationBroker(timeout=0.1)
    broker.request_confirmation("call_1", "update_score", {"score": 92})
    approved = await broker.wait_for_resolution("call_1")
    assert not approved


def test_is_expired():
    broker = ConfirmationBroker(timeout=0.0)
    broker.request_confirmation("call_1", "update_score", {})
    assert broker.is_expired("call_1")


def test_multiple_pending():
    broker = ConfirmationBroker()
    broker.request_confirmation("c1", "tool1", {})
    broker.request_confirmation("c2", "tool2", {})
    broker.request_confirmation("c3", "tool3", {})
    assert len(broker.get_pending()) == 3
    broker.approve("c2")
    assert len(broker.get_pending()) == 2
