"""
天依小本本 - 记忆插件
帮天依记住和每个人的对话，不会再问「你谁啊」「你之前说过啥」
"""
import json
import re
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star


class TianyiMemory(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.max_memory = 3  # 每人最多记3条

    async def _get_memory(self, user_id: str) -> list:
        """读某个人的记忆"""
        data = await self.get_kv_data(f"mem_{user_id}")
        return json.loads(data) if data else []

    async def _save_memory(self, user_id: str, memories: list):
        """保存记忆"""
        await self.put_kv_data(f"mem_{user_id}", json.dumps(memories, ensure_ascii=False))

    async def _extract_fact(self, text: str, user_id: str):
        """从对话里提取值得记住的事"""
        facts = []
        keywords = {
            "喜欢": "喜欢",
            "爱吃": "爱吃",
            "不喜欢": "不喜欢",
            "讨厌": "讨厌",
            "是": "是",  # 我是学生 / 我是程序员
            "在": "在",    # 我在北京
            "叫": "叫",  # 叫我小王
            "做": "做",  # 我做设计的
        }

        for kw, label in keywords.items():
            if kw in text:
                idx = text.index(kw)
                snippet = text[idx:idx + 20].strip()
                if snippet and len(snippet) > 3:
                    facts.append(snippet)

        if facts:
            mem = await self._get_memory(user_id)
            for f in facts:
                if f not in mem:
                    mem.append(f)
            # 只保留最近几条
            if len(mem) > self.max_memory:
                mem = mem[-self.max_memory:]
            await self._save_memory(user_id, mem)

    def _build_context(self, mems: list) -> str:
        """把记忆拼成一段上下文"""
        if not mems:
            return ""
        lines = [f"- {m}" for m in mems]
        return "关于这人你记得：" + "；".join(mems) + "。\n"

    # 钩子：在LLM收到消息前，注入用户记忆
    @filter.on_llm_request()
    async def inject_memory(self, event: AstrMessageEvent):
        """在每条消息前注入对应用户的记忆"""
        try:
            sender = event.get_sender_id()
            user_name = event.get_sender_name() or ""

            # 读这个人的记忆
            mems = await self._get_memory(sender)
            if mems:
                ctx = self._build_context(mems)
                # 加在消息前面，让模型能看到
                original = event.message_str
                event.message_str = f"[备忘] {ctx}\n{user_name}: {original}"
        except Exception:
            pass

    # 钩子：LLM回复后，从回复中提取可记的事
    @filter.on_llm_response()
    async def learn_from_conversation(self, event: AstrMessageEvent):
        """分析对话中学到的东西"""
        try:
            msg = event.message_str
            sender = event.get_sender_id()

            # 从用户的话里提取
            await self._extract_fact(msg, sender)

            # 如果回复里有"记住了""知道了"这类确认，也试着提取
            if any(w in msg for w in ["记住了", "记下了", "知道啦", "好哒"]):
                # 往前找用户说了啥
                pass
        except Exception:
            pass

    async def terminate(self):
        pass
