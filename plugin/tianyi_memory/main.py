"""
天依小本本 - 群聊记忆插件
记住和每个人的对话，可以聊别人聊过的话题，但隐私不外泄
"""
import json
import time
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star


class TianyiMemory(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.max_public = 3    # 每人最多记3个公开话题
        self.max_private = 3   # 每人最多记3条隐私

    # ----- 公开话题(可以跟别人说) -----
    async def _get_public(self, user_id: str) -> list:
        data = await self.get_kv_data(f"pub_{user_id}")
        return json.loads(data) if data else []

    async def _save_public(self, user_id: str, items: list):
        await self.put_kv_data(f"pub_{user_id}", json.dumps(items, ensure_ascii=False))

    # ----- 隐私信息(绝不说出去) -----
    async def _get_private(self, user_id: str) -> list:
        data = await self.get_kv_data(f"prv_{user_id}")
        return json.loads(data) if data else []

    async def _save_private(self, user_id: str, items: list):
        await self.put_kv_data(f"prv_{user_id}", json.dumps(items, ensure_ascii=False))

    # ----- 群聊历史(全部) -----
    def _session_key(self, event):
        gid = event.get_group_id() if hasattr(event, 'get_group_id') else ""
        return f"group_{gid}" if gid else f"private_{event.get_sender_id()}"

    async def _get_history(self, session: str) -> list:
        data = await self.get_kv_data(f"hist_{session}")
        return json.loads(data) if data else []

    async def _save_history(self, session: str, history: list):
        await self.put_kv_data(f"hist_{session}", json.dumps(history, ensure_ascii=False))

    # ----- 判断是否隐私 -----
    _private_keywords = ["密码", "账号", "电话", "手机号", "地址", "住", "银行卡",
                         "身份证", "真名", "实名", "工资", "收入", "密码", "token",
                         "key", "apikey", "secret", "密码"]

    def _is_private(self, text: str) -> bool:
        for kw in self._private_keywords:
            if kw in text:
                return True
        return False

    # ----- LLM请求前：注入上下文 -----
    @filter.on_llm_request()
    async def inject_context(self, event: AstrMessageEvent):
        try:
            sender = event.get_sender_id()
            user_name = event.get_sender_name() or "有人"
            session = self._session_key(event)

            # 这个人的公开+隐私(只给自己看)
            pub = await self._get_public(sender)
            prv = await self._get_private(sender)
            user_ctx = ""
            if pub:
                user_ctx += f"「{user_name}」聊过：" + "；".join(pub) + "。\n"
            if prv:
                user_ctx += f"「{user_name}」的私事：" + "；".join(prv) + "。【绝对不说出去】\n"

            # 最近群聊记录
            history = await self._get_history(session)
            chat_ctx = ""
            if history:
                recent = history[-8:]
                chat_ctx = "刚才聊了：\n" + "\n".join(
                    f"- {h['name']}: {h['msg'][:30]}" for h in recent
                ) + "\n"

            ctx = user_ctx + chat_ctx
            if ctx:
                event.message_str = f"[备忘]\n{ctx}\n---\n{user_name}: {event.message_str}"

        except Exception:
            pass

    # ----- LLM回复后：记录 + 分类 + 追踪用户 -----
    @filter.on_llm_response()
    async def record_conversation(self, event: AstrMessageEvent):
        try:
            sender = event.get_sender_id()
            user_name = event.get_sender_name() or "有人"
            session = self._session_key(event)

            # 追踪用户ID-名字映射
            data = await self.get_kv_data("__all_users__") or "[]"
            users = json.loads(data)
            found = False
            for i, (uid, n) in enumerate(users):
                if uid == sender:
                    users[i] = (uid, user_name)
                    found = True
                    break
            if not found:
                users.append((sender, user_name))
            await self.put_kv_data("__all_users__", json.dumps(users, ensure_ascii=False))

            # 记录群聊历史
            history = await self._get_history(session)
            history.append({"name": user_name, "msg": event.message_str[:60], "time": int(time.time())})
            if len(history) > 20:
                history = history[-20:]
            await self._save_history(session, history)

            # 从对话提取公开话题
            msg = event.message_str
            topic_words = ["吃", "火锅", "奶茶", "甜品", "歌", "音乐", "游戏",
                          "电影", "动漫", "学习", "工作", "学校", "旅行", "玩"]
            pub_facts = await self._get_public(sender)
            for tw in topic_words:
                if tw in msg:
                    snippet = f"聊过{tw}"
                    if snippet not in pub_facts:
                        pub_facts.append(snippet)
            if len(pub_facts) > self.max_public:
                pub_facts = pub_facts[-self.max_public:]
            if pub_facts:
                await self._save_public(sender, pub_facts)

            # 隐私信息提取（仅自己可见）
            if self._is_private(msg):
                prv_facts = await self._get_private(sender)
                words = ["喜欢", "爱吃", "在", "住", "做", "叫"]
                for w in words:
                    if w in msg:
                        idx = msg.index(w)
                        snippet = msg[idx:idx + 20].strip()
                        if snippet not in prv_facts:
                            prv_facts.append(snippet)
                if len(prv_facts) > self.max_private:
                    prv_facts = prv_facts[-self.max_private:]
                await self._save_private(sender, prv_facts)

        except Exception:
            pass

    # ----- 工具：查别人聊过什么(只给公开话题) -----
    @filter.llm_tool(name="what_did_they_talk_about")
    async def tool_check_user(self, event: AstrMessageEvent, who: str):
        """有人问「XX之前跟你聊了什么」，只返回不涉及隐私的公开话题。

        Args:
            who(string): 被问的人的名字
        """
        data = await self.get_kv_data("__all_users__") or "[]"
        all_users = json.loads(data)

        target_id = None
        for uid, name in all_users:
            if who in name or who == uid:
                target_id = uid
                break

        if not target_id:
            yield event.plain_result("唔…不记得这人跟我聊过诶")
            return

        pub = await self._get_public(target_id)
        if not pub:
            yield event.plain_result("就跟" + who + "随便聊了几句~")
            return

        yield event.plain_result(who + "跟我聊过：" + "、".join(pub) + "~")

    async def terminate(self):
        pass
