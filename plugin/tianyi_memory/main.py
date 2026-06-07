"""
天依小本本 - 群聊记忆插件
记住和每个人的对话，换人聊也不断片
"""
import json
import time
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star


class TianyiMemory(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.max_history = 10      # 每个会话记最近10轮
        self.max_user_facts = 3    # 每人最多记3条个人信息

    # ----- 用户画像 -----
    async def _get_facts(self, user_id: str) -> list:
        data = await self.get_kv_data(f"user_{user_id}")
        return json.loads(data) if data else []

    async def _save_facts(self, user_id: str, facts: list):
        await self.put_kv_data(f"user_{user_id}", json.dumps(facts, ensure_ascii=False))

    # ----- 群聊历史 -----
    def _session_key(self, event):
        """私聊/群聊 区分"""
        gid = event.get_group_id() if hasattr(event, 'get_group_id') else ""
        return f"group_{gid}" if gid else f"private_{event.get_sender_id()}"

    async def _get_history(self, session: str) -> list:
        data = await self.get_kv_data(f"hist_{session}")
        return json.loads(data) if data else []

    async def _save_history(self, session: str, history: list):
        await self.put_kv_data(f"hist_{session}", json.dumps(history, ensure_ascii=False))

    def _summary(self, user_name: str, facts: list) -> str:
        if not facts:
            return ""
        return f"「{user_name}」之前说过：" + "；".join(facts) + "。\n"

    # ----- LLM请求前：注入上下文 -----
    @filter.on_llm_request()
    async def inject_context(self, event: AstrMessageEvent):
        try:
            sender = event.get_sender_id()
            user_name = event.get_sender_name() or "有人"
            session = self._session_key(event)

            # 1. 这个人的画像
            facts = await self._get_facts(sender)
            user_context = self._summary(user_name, facts)

            # 2. 最近群聊记录
            history = await self._get_history(session)
            chat_context = ""
            if history:
                recent = history[-self.max_history:]
                chat_context = "刚才在聊：\n" + "\n".join(f"- {h['name']}: {h['msg'][:40]}" for h in recent) + "\n"

            # 3. 拼到用户消息前面
            ctx = user_context + chat_context
            if ctx:
                event.message_str = f"[备忘]\n{ctx}\n---\n{user_name}: {event.message_str}"

        except Exception:
            pass

    # ----- LLM回复后：记录 -----
    @filter.on_llm_response()
    async def record_conversation(self, event: AstrMessageEvent):
        try:
            sender = event.get_sender_id()
            user_name = event.get_sender_name() or "有人"
            session = self._session_key(event)

            # 记录群聊历史
            history = await self._get_history(session)
            history.append({
                "name": user_name,
                "msg": event.message_str[:60],
                "time": int(time.time())
            })
            if len(history) > 20:
                history = history[-20:]
            await self._save_history(session, history)

            # 从对话里提取关键信息
            msg = event.message_str
            facts = await self._get_facts(sender)
            keywords = ["喜欢", "爱吃", "不喜欢", "讨厌", "在", "是", "做", "叫", "住"]

            for kw in keywords:
                if kw in msg:
                    idx = msg.index(kw)
                    snippet = msg[idx:idx + 25].strip()
                    if snippet and len(snippet) > 3 and snippet not in facts:
                        facts.append(snippet)
                        if len(facts) > self.max_user_facts:
                            facts.pop(0)

            if facts:
                await self._save_facts(sender, facts)

        except Exception:
            pass

    async def terminate(self):
        pass
