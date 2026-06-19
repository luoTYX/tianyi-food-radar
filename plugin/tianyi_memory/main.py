"""
天依小本本 - 群聊记忆插件
用大模型总结对话，记住和每个人的事。隐私分级，该说的说，不该说的不外泄。
"""
import json
import time
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star


class TianyiMemory(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.max_public = 5     # 每人公开摘要条数
        self.max_private = 3    # 隐私摘要条数
        self.max_history = 10   # 群聊上下文轮数

    # ----- 公开/隐私记忆 -----
    async def _get_public(self, uid: str) -> list:
        d = await self.get_kv_data(f"pub_{uid}")
        return json.loads(d) if d else []

    async def _save_public(self, uid: str, items: list):
        await self.put_kv_data(f"pub_{uid}", json.dumps(items, ensure_ascii=False))

    async def _get_private(self, uid: str) -> list:
        d = await self.get_kv_data(f"prv_{uid}")
        return json.loads(d) if d else []

    async def _save_private(self, uid: str, items: list):
        await self.put_kv_data(f"prv_{uid}", json.dumps(items, ensure_ascii=False))

    # ----- 群聊历史 -----
    def _session(self, event):
        gid = event.get_group_id() if hasattr(event, 'get_group_id') else ""
        return f"group_{gid}" if gid else f"private_{event.get_sender_id()}"

    async def _get_hist(self, session: str) -> list:
        d = await self.get_kv_data(f"hist_{session}")
        return json.loads(d) if d else []

    async def _save_hist(self, session: str, hist: list):
        await self.put_kv_data(f"hist_{session}", json.dumps(hist, ensure_ascii=False))

    # ----- LLM总结 -----
    async def _summarize_public(self, user_name: str, recent: list) -> str:
        """让大模型总结这个人的公开话题"""
        if not recent or len(recent) < 2:
            return ""

        dialogue = "\n".join(f"{h['role']}: {h['msg'][:80]}" for h in recent[-6:])
        prompt = f"""下面是一段对话，请用极短的一句话(10字内)总结{user_name}在这次对话中关心什么、喜欢什么、聊了什么话题。只总结不涉及隐私的公开信息。不要说地址电话等隐私。

对话：
{dialogue}

总结："""

        try:
            result = await self.context.llm_generate(prompt=prompt)
            if result and len(result.strip()) > 1:
                return f"跟{user_name}聊到：{result.strip()[:30]}"
        except Exception:
            pass
        return ""

    async def _summarize_private(self, user_name: str, recent: list) -> str:
        """提取隐私信息（只给本人看）"""
        if not recent or len(recent) < 2:
            return ""

        dialogue = "\n".join(f"{h['role']}: {h['msg'][:80]}" for h in recent[-6:])
        prompt = f"""从对话中提取{user_name}分享的个人信息(如所在地、职业、偏好等)，极短一句话。如果没有就说"无"。

对话：
{dialogue}

个人信息："""

        try:
            result = await self.context.llm_generate(prompt=prompt)
            if result and "无" not in result and len(result.strip()) > 1:
                return result.strip()[:30]
        except Exception:
            pass
        return ""

    # ----- LLM请求前注入上下文 -----
    @filter.on_llm_request()
    async def inject_context(self, event: AstrMessageEvent):
        try:
            sender = event.get_sender_id()
            name = event.get_sender_name() or "有人"
            session = self._session(event)

            pub = await self._get_public(sender)
            prv = await self._get_private(sender)
            hist = await self._get_hist(session)

            parts = []
            if pub:
                parts.append("关于" + name + "你知道：" + "；".join(pub[-3:]) + "。")
            if prv:
                parts.append(name + "的私事：" + "；".join(prv) + "。【绝不说出去】")
            if hist:
                recent = hist[-self.max_history:]
                parts.append("刚才在聊：\n" + "\n".join(
                    f"- {h['name']}: {h['msg'][:30]}" for h in recent
                ))

            if parts:
                ctx = "\n".join(parts)
                event.message_str = f"[备忘]\n{ctx}\n---\n{name}: {event.message_str}"

        except Exception:
            pass

    # ----- LLM回复后：记录+总结 -----
    @filter.on_llm_response()
    async def record_and_summarize(self, event: AstrMessageEvent):
        try:
            sender = event.get_sender_id()
            name = event.get_sender_name() or "有人"
            session = self._session(event)

            # 记录历史
            hist = await self._get_hist(session)
            hist.append({"name": name, "role": "user", "msg": event.message_str[:60], "time": int(time.time())})
            if len(hist) > 30:
                hist = hist[-30:]
            await self._save_hist(session, hist)

            # 收集最近的对话包含用户消息+bot回复
            recent = hist[-8:]

            # 公开总结
            pub = await self._get_public(sender)
            summary = await self._summarize_public(name, recent)
            if summary and summary not in pub:
                pub.append(summary)
                if len(pub) > self.max_public:
                    pub = pub[-self.max_public:]
                await self._save_public(sender, pub)

            # 隐私总结
            prv = await self._get_private(sender)
            prv_summary = await self._summarize_private(name, recent)
            if prv_summary and prv_summary not in prv:
                prv.append(prv_summary)
                if len(prv) > self.max_private:
                    prv = prv[-self.max_private:]
                await self._save_private(sender, prv)

        except Exception:
            pass

    # ----- 工具：查别人聊过啥(只给公开) -----
    @filter.llm_tool(name="what_did_they_talk_about")
    async def tool_check_user(self, event: AstrMessageEvent, who: str):
        """有人问XX之前跟我聊了什么，查公开记忆。隐私绝不透露。

        Args:
            who(string): 被问的人名字
        """
        data = await self.get_kv_data("__all_users__") or "[]"
        all_users = json.loads(data)

        target_id = None
        for uid, n in all_users:
            if who in n or who == uid:
                target_id = uid
                break

        if not target_id:
            yield event.plain_result("唔…不记得这人诶")
            return

        pub = await self._get_public(target_id)
        if not pub:
            yield event.plain_result("就跟" + who + "随便聊了几句~")
            return

        yield event.plain_result("关于" + who + "：" + "、".join(pub[-3:]) + "~")

    # ----- 追踪用户 -----
    @filter.after_message_sent()
    async def track_user(self, event: AstrMessageEvent):
        try:
            sender = event.get_sender_id()
            name = event.get_sender_name() or ""
            data = await self.get_kv_data("__all_users__") or "[]"
            users = json.loads(data)
            for i, (uid, n) in enumerate(users):
                if uid == sender:
                    users[i] = (uid, name)
                    await self.put_kv_data("__all_users__", json.dumps(users, ensure_ascii=False))
                    return
            users.append((sender, name))
            await self.put_kv_data("__all_users__", json.dumps(users, ensure_ascii=False))
        except Exception:
            pass

    async def terminate(self):
        pass
