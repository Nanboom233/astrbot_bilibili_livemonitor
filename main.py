import asyncio
import os

from astrbot.api import AstrBotConfig
from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

from .bilibili import BilibiliLiveRoom
from .templates import MessageTemplates
from typing import Optional


@register(
    "astrbot_bilibili_livemonitor",
    "Dayanshifu,Nanboom233",
    "bilibili开播下播提醒",
    "1.3",
    "https://github.com/Nanboom233/astrbot_bilibili_livemonitor"
)
class BilibiliLiveMonitor(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        self.rooms = {}
        self.check_interval = config.get("time", 60)

        # 集中管理模板配置
        MessageTemplates.update_templates(config)
        self.running = True

    @filter.on_astrbot_loaded()
    async def load_subs(self):
        subs = await self.get_kv_data("subs", {})
        for live_id, data in subs.items():
            self.rooms[live_id] = BilibiliLiveRoom(live_id, data.get("anchor_name", live_id))
        
        asyncio.create_task(self.monitor_task())

    async def monitor_task(self):
        while self.running:
            try:
                for room_id, room in self.rooms.items():
                    result = await room.update_info()
                    if not result:
                        continue

                    if result["is_new_live"]:
                        save_path = await room.download_cover()

                        msg_text = MessageTemplates.msg_live_start.render(
                            anchor_name=room.anchor_name,
                            room_title=room.room_title,
                            room_url=room.room_url,
                            room_id=room.room_id
                        )

                        message = MessageChain().message(msg_text)
                        if save_path and os.path.exists(save_path):
                            message.file_image(save_path)
                        else:
                            message.message("<获取封面失败>")

                        subs = await self.get_kv_data("subs", {})
                        sids = subs.get(room_id, {}).get("sids", [])
                        
                        for sid in sids:
                            try:
                                await self.context.send_message(sid, message)
                                logger.info(f"已向会话 {sid} 发送 {room.anchor_name} 开播通知")
                            except Exception as e:
                                logger.error(f"向会话 {sid} 发送开播通知失败: {e}")

                        room.has_sent_live_notice = True
                        logger.info(f"直播间{room_id}({room.anchor_name})开播，已发送通知")

                    elif result["is_new_offline"]:
                        msg_text = MessageTemplates.msg_live_end.render(
                            anchor_name=room.anchor_name,
                            room_id=room.room_id
                        )

                        message = MessageChain().message(msg_text)
                        
                        subs = await self.get_kv_data("subs", {})
                        sids = subs.get(room_id, {}).get("sids", [])
                        
                        for sid in sids:
                            try:
                                await self.context.send_message(sid, message)
                                logger.info(f"已向会话 {sid} 发送 {room.anchor_name} 下播通知")
                            except Exception as e:
                                logger.error(f"向会话 {sid} 发送下播通知失败: {e}")
                                
                        logger.info(f"直播间{room_id}({room.anchor_name})已下播")

            except Exception as e:
                logger.error(f"监控任务出错: {str(e)}")

            await asyncio.sleep(self.check_interval)

    @filter.command("live_sub")
    async def live_sub_command(self, event: AstrMessageEvent, sid: str, live_id: str, anchor_name: str = ""):
        """订阅直播间通知。参数: sid 直播间ID [主播名称]"""
        if not anchor_name:
            anchor_name = live_id

        subs = await self.get_kv_data("subs", {})
        
        if live_id not in subs:
            subs[live_id] = {"sids": [], "anchor_name": anchor_name}
            self.rooms[live_id] = BilibiliLiveRoom(live_id, anchor_name)
            
        if sid not in subs[live_id]["sids"]:
            subs[live_id]["sids"].append(sid)
            await self.put_kv_data("subs", subs)
            yield event.plain_result(f"已为会话 {sid} 订阅直播间 {live_id}({anchor_name})")
        else:
            yield event.plain_result(f"会话 {sid} 已订阅过该直播间")
            
    @filter.command("live_unsub")
    async def live_unsub_command(self, event: AstrMessageEvent, sid: str, live_id: str):
        """取消订阅直播间通知。参数: sid 直播间ID"""
        subs = await self.get_kv_data("subs", {})
        if live_id in subs and sid in subs[live_id]["sids"]:
            subs[live_id]["sids"].remove(sid)
            if not subs[live_id]["sids"]:
                del subs[live_id]
                if live_id in self.rooms:
                    del self.rooms[live_id]
            await self.put_kv_data("subs", subs)
            yield event.plain_result(f"已取消会话 {sid} 对直播间 {live_id} 的订阅")
        else:
            yield event.plain_result(f"未找到对应的订阅记录")

    async def get_live_info(self, room_id=None):

        if room_id and room_id in self.rooms:
            return await self.rooms[room_id].get_formatted_info()
        else:
            if not self.rooms:
                return "当前暂无订阅任何直播间"
            all_info = []
            for room in self.rooms.values():
                all_info.append(await room.get_formatted_info())
            return "所有直播间状态\n\n" + "\n\n".join(all_info)

    @filter.command("live_info")
    async def liveinfo_command(self, event: AstrMessageEvent, room_id: Optional[str] = None):
        """获取直播间信息。可选参数: 直播间ID"""
        info = await self.get_live_info(room_id)
        yield event.plain_result(info)

    async def terminate(self):
        self.running = False
        await BilibiliLiveRoom.close_session()
        logger.info("直播间监控插件已停止")
