import asyncio
import os
import yaml

from astrbot.api import AstrBotConfig
from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

from .bilibili import BilibiliLiveRoom
from .templates import MessageTemplates
from typing import Optional


def load_metadata():
    yaml_path = os.path.join(os.path.dirname(__file__), "metadata.yaml")
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"metadata.yaml 未找到: {yaml_path}")
        
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    if not data:
        raise ValueError("metadata.yaml 为空或格式错误")
        
    required_keys = ["name", "author", "desc", "version", "repo"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"metadata.yaml 缺少必要字段: {key}")
            
    return data

PLUGIN_META = load_metadata()

@register(
    PLUGIN_META["name"],
    PLUGIN_META["author"],
    PLUGIN_META["desc"],
    str(PLUGIN_META["version"]).lstrip("v"),
    PLUGIN_META["repo"]
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

    async def update_and_notify_room(self, room_id: str, room: BilibiliLiveRoom) -> dict | None:
        result = await room.update_info()
        if not result:
            return None

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
                message.message(MessageTemplates.msg_cover_fail.render())

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

        return result

    async def monitor_task(self):
        while self.running:
            try:
                for room_id, room in self.rooms.items():
                    await self.update_and_notify_room(room_id, room)

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
            yield event.plain_result(MessageTemplates.msg_sub_success.render(
                sid=sid, live_id=live_id, anchor_name=anchor_name
            ))
        else:
            yield event.plain_result(MessageTemplates.msg_sub_exist.render(
                sid=sid, live_id=live_id
            ))
            
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
            yield event.plain_result(MessageTemplates.msg_unsub_success.render(
                sid=sid, live_id=live_id
            ))
        else:
            yield event.plain_result(MessageTemplates.msg_unsub_fail.render(
                sid=sid, live_id=live_id
            ))

    async def get_live_info(self, room_id=None):
        subs = await self.get_kv_data("subs", {})

        if room_id and room_id in self.rooms:
            room = self.rooms[room_id]
            result = await self.update_and_notify_room(room_id, room)
            info = room.get_formatted_info(result)
            
            sids = subs.get(room_id, {}).get("sids", [])
            sids_str = ", ".join(sids) if sids else "无"
            info += MessageTemplates.msg_sub_list.render(sids_str=sids_str)
            
            return info
        else:
            if not self.rooms:
                return MessageTemplates.msg_no_subs.render()
            all_info = []
            for r_id, room in self.rooms.items():
                result = await self.update_and_notify_room(r_id, room)
                info = room.get_formatted_info(result)
                
                sids = subs.get(r_id, {}).get("sids", [])
                sids_str = ", ".join(sids) if sids else "无"
                info += MessageTemplates.msg_sub_list.render(sids_str=sids_str)
                
                all_info.append(info)
            return MessageTemplates.msg_all_info_header.render() + "\n\n".join(all_info)

    @filter.command("live_info")
    async def live_info_command(self, event: AstrMessageEvent, room_id: str = ""):
        """获取直播间信息。可选参数: 直播间ID"""
        target_id = room_id.strip() if room_id else None
        info = await self.get_live_info(target_id)
        yield event.plain_result(info)

    async def terminate(self):
        self.running = False
        await BilibiliLiveRoom.close_session()
        logger.info("直播间监控插件已停止")
