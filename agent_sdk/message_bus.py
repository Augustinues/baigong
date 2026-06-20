"""消息总线——Agent 间通信"""

import uuid
import time
import asyncio
from collections import deque
from typing import Callable

from .models import Message, MessageType


class MessageBus:
    """消息总线——所有 Agent 之间的通信中枢"""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}  # agent_id → [handler]
        self._history: deque[Message] = deque(maxlen=1000)  # 最近 1000 条
        self._global_handlers: list[Callable] = []

    def subscribe(self, agent_id: str, handler: Callable):
        """Agent 订阅自己的消息"""
        if agent_id not in self._subscribers:
            self._subscribers[agent_id] = []
        self._subscribers[agent_id].append(handler)

    def unsubscribe(self, agent_id: str, handler: Callable):
        """取消订阅"""
        if agent_id in self._subscribers:
            self._subscribers[agent_id].remove(handler)

    def on_any(self, handler: Callable):
        """全局监听（用于日志、监控）"""
        self._global_handlers.append(handler)

    async def send(self, message: Message):
        """发送消息"""
        if not message.id:
            message.id = f"msg_{uuid.uuid4().hex[:12]}"
        if not message.created_at:
            message.created_at = time.time()

        self._history.append(message)

        # 全局处理器
        for handler in self._global_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception:
                pass

        # 投递给每个接收者
        for recipient in message.recipients:
            if recipient == "all":
                # 广播给所有人
                for agent_id, handlers in self._subscribers.items():
                    for handler in handlers:
                        await self._deliver(handler, message)
            elif recipient in self._subscribers:
                for handler in self._subscribers[recipient]:
                    await self._deliver(handler, message)

    async def _deliver(self, handler, message: Message):
        """投递消息到单个 handler"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)
        except Exception as e:
            print(f"[MessageBus] 投递失败: {e}")

    def send_to_ceo(self, sender: str, body: str, msg_type: MessageType = MessageType.NOTIFICATION):
        """快捷方法：给 CEO 发消息"""
        return self.send(Message(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            type=msg_type,
            sender=sender,
            recipients=["ceo"],
            body=body,
            created_at=time.time(),
        ))

    def broadcast(self, sender: str, body: str, msg_type: MessageType = MessageType.NOTIFICATION):
        """广播给所有 Agent"""
        return self.send(Message(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            type=msg_type,
            sender=sender,
            recipients=["all"],
            body=body,
            created_at=time.time(),
        ))

    def get_recent(self, limit: int = 20) -> list[Message]:
        """获取最近消息"""
        return list(self._history)[-limit:]

    def count_recent(self, seconds: int = 3600) -> int:
        """最近 N 秒内的消息数"""
        cutoff = time.time() - seconds
        return sum(1 for m in self._history if m.created_at >= cutoff)

    def count_today(self) -> int:
        """今天的消息数"""
        cutoff = time.time() - 86400
        return sum(1 for m in self._history if m.created_at >= cutoff)
